import time
from collections import defaultdict
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from app.auth.dependencies import get_current_user
from app.auth.jwt import create_access_token, verify_password
from app.auth.permissions import get_user_permissions

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# In-memory rate limiter: max 10 attempts per IP within a 60-second window.
# ---------------------------------------------------------------------------
_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW = 60  # seconds

# {ip: [timestamp, ...]}
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW
    attempts = [t for t in _login_attempts[ip] if t > window_start]
    _login_attempts[ip] = attempts
    if len(attempts) >= _RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente em 60 segundos.",
        )
    _login_attempts[ip].append(now)


# ---------------------------------------------------------------------------
# Schemas (local, lightweight — Agente C owns app/schemas/)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    role_id: Optional[int] = None
    role_nome: Optional[str] = None
    is_admin: bool = False
    permissoes: dict = {}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Helper: lazy import of Agente B's db module
# ---------------------------------------------------------------------------

def _get_usuarios_repo():
    try:
        import app.db.usuarios_repo as repo
        return repo
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de banco de dados indisponível.",
        ) from exc


def _resolve_role(role_id):
    """Retorna (role_nome, is_admin) para um role_id (None-safe)."""
    if not role_id:
        return None, False
    try:
        from app.db import rbac_repo
        role = rbac_repo.obter_role(role_id)
    except Exception:
        role = None
    if not role:
        return None, False
    return role.get("nome"), bool(role.get("is_system"))


def _token_claims(usuario: dict, role_nome, is_admin) -> dict:
    return {
        "sub": str(usuario["id"]),
        "nome": usuario["nome"],
        "email": usuario["email"],
        "perfil": usuario["perfil"],
        "role_id": usuario.get("role_id"),
        "role_nome": role_nome,
        "is_admin": is_admin,
    }


def _usuario_out(usuario: dict, role_nome, is_admin) -> "UsuarioOut":
    perms = get_user_permissions({"is_admin": is_admin, "role_id": usuario.get("role_id")})
    return UsuarioOut(
        id=usuario["id"],
        nome=usuario["nome"],
        email=usuario["email"],
        perfil=usuario["perfil"],
        role_id=usuario.get("role_id"),
        role_nome=role_nome,
        is_admin=is_admin,
        permissoes=perms,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    """Authenticate with email + senha. Returns a JWT access token."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    repo = _get_usuarios_repo()
    usuario = repo.obter_por_email(body.email)

    if usuario is None or not verify_password(body.senha, usuario["senha_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    if not usuario.get("ativo", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo.",
        )

    role_nome, is_admin = _resolve_role(usuario.get("role_id"))
    token = create_access_token(_token_claims(usuario, role_nome, is_admin))

    return TokenResponse(
        access_token=token,
        usuario=_usuario_out(usuario, role_nome, is_admin),
    )


@router.get("/me", response_model=UsuarioOut)
async def me(current_user: Annotated[dict, Depends(get_current_user)]):
    """Return information about the currently authenticated user (com permissões)."""
    # Resolve a partir do role atual no banco para refletir mudanças de permissão na hora.
    role_nome, is_admin = _resolve_role(current_user.get("role_id"))
    if current_user.get("is_admin"):
        is_admin = True  # respeita token de admin mesmo se role_id ausente
    return _usuario_out(current_user, role_nome or current_user.get("role_nome"), is_admin)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(current_user: Annotated[dict, Depends(get_current_user)]):
    """Issue a new access token for an already-authenticated user."""
    role_nome, is_admin = _resolve_role(current_user.get("role_id"))
    if current_user.get("is_admin"):
        is_admin = True
    token = create_access_token(_token_claims(current_user, role_nome, is_admin))
    return RefreshResponse(access_token=token)
