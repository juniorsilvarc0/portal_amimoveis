from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_token

_bearer = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> dict:
    """Decode the Bearer JWT and return the user payload.

    Returns a dict with keys: id, nome, email, perfil.
    Raises HTTP 401 if the token is missing, expired, or otherwise invalid.
    """
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Validate required claims are present.
    for field in ("sub", "nome", "email", "perfil"):
        if field not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token com dados incompletos.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    # Campos RBAC. Tokens antigos (pré-RBAC) não têm role_id/is_admin:
    # derivamos is_admin do perfil legado (tokens expiram em 24h → migração natural).
    is_admin = payload.get("is_admin")
    if is_admin is None:
        is_admin = payload.get("perfil") == "admin"

    return {
        "id": int(payload["sub"]),
        "nome": payload["nome"],
        "email": payload["email"],
        "perfil": payload["perfil"],
        "role_id": payload.get("role_id"),
        "role_nome": payload.get("role_nome"),
        "is_admin": bool(is_admin),
    }


def require_role(*roles: str):
    """Return a FastAPI dependency that checks whether the current user has one of the given roles.

    Usage::

        @router.get("/admin/stuff")
        async def stuff(user=Depends(require_role("admin"))):
            ...

    Raises HTTP 403 if the user's profile is not in the allowed roles.
    """

    def _check(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if current_user["perfil"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso restrito a: {', '.join(roles)}.",
            )
        return current_user

    return _check
