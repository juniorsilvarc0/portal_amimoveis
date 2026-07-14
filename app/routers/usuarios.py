"""Router de usuários (gestão sob o recurso RBAC 'usuarios')."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.permissions import require_permission
from app.auth.jwt import hash_password
from app.db import usuarios_repo, rbac_repo
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/usuarios", tags=["Usuários"])

_ver    = require_permission("usuarios", "ver")
_criar  = require_permission("usuarios", "criar")
_editar = require_permission("usuarios", "editar")
_excluir = require_permission("usuarios", "excluir")


def _sync_perfil_por_role(dados: dict) -> None:
    """Mantém o campo legado `perfil` coerente com o role escolhido:
    perfil='admin' se o role for de sistema (Administrador), senão 'usuario'."""
    role_id = dados.get("role_id")
    if not role_id:
        return
    role = rbac_repo.obter_role(role_id)
    if not role:
        raise HTTPException(422, "Perfil de acesso inválido.")
    dados["perfil"] = "admin" if role.get("is_system") else "usuario"


@router.get("", response_model=PagedResponse[UsuarioRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    perfil: str | None = None,
    role_id: int | None = None,
    ativo: bool | None = None,
    user=Depends(_ver),
):
    rows, total = usuarios_repo.listar(
        page=page, per_page=per_page, search=search, perfil=perfil,
        role_id=role_id, ativo=ativo,
    )
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    }


@router.get("/{usuario_id}", response_model=UsuarioRead)
async def obter(usuario_id: int, user=Depends(_ver)):
    u = usuarios_repo.obter(usuario_id)
    if not u:
        raise HTTPException(404, "Usuário não encontrado")
    return u


@router.post("", response_model=UsuarioRead, status_code=201)
async def criar(body: UsuarioCreate, user=Depends(_criar)):
    dados = body.model_dump()
    senha_plain = dados.pop("senha")
    dados["senha_hash"] = hash_password(senha_plain)
    _sync_perfil_por_role(dados)
    try:
        new_id = usuarios_repo.criar(dados)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "E-mail já cadastrado")
        raise HTTPException(500, f"Erro ao criar usuário: {e}")
    return usuarios_repo.obter(new_id)


@router.put("/{usuario_id}", response_model=UsuarioRead)
async def atualizar(usuario_id: int, body: UsuarioUpdate, user=Depends(_editar)):
    dados = body.model_dump(exclude_unset=True)
    senha_plain = dados.pop("senha", None)
    if senha_plain:
        dados["senha_hash"] = hash_password(senha_plain)
    _sync_perfil_por_role(dados)
    ok = usuarios_repo.atualizar(usuario_id, dados)
    if not ok:
        raise HTTPException(404, "Usuário não encontrado")
    return usuarios_repo.obter(usuario_id)


@router.delete("/{usuario_id}", response_model=MessageResponse)
async def deletar(usuario_id: int, user=Depends(_excluir)):
    ok = usuarios_repo.deletar(usuario_id)
    if not ok:
        raise HTTPException(404, "Usuário não encontrado")
    return {"mensagem": "Usuário desativado"}
