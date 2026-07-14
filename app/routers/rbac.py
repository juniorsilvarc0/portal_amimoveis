"""Router de Perfis de Acesso (RBAC).

Endpoints sob /api/v1/perfis:
  GET    /perfis            — lista perfis (+ contagem de usuários)
  GET    /perfis/recursos   — catálogo de recursos p/ montar a matriz no front
  GET    /perfis/{id}       — perfil + matriz de permissões
  POST   /perfis            — cria perfil
  PUT    /perfis/{id}       — atualiza perfil (bloqueia perfil de sistema)
  DELETE /perfis/{id}       — exclui perfil (bloqueia sistema / com usuários)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.auth.recursos import ACOES, RECURSOS
from app.db import rbac_repo
from app.schemas.rbac import RoleCreate, RoleUpdate

router = APIRouter(prefix="/api/v1/perfis", tags=["Perfis de Acesso"])


def _serialize_role(role: dict, permissoes: list[dict] | None = None) -> dict:
    out = {
        "id": role["id"],
        "nome": role["nome"],
        "descricao": role.get("descricao"),
        "is_system": role.get("is_system", False),
        "ativo": role.get("ativo", True),
        "usuarios_count": role.get("usuarios_count"),
        "created_at": role.get("created_at"),
        "updated_at": role.get("updated_at"),
    }
    if permissoes is not None:
        out["permissoes"] = permissoes
    return out


@router.get("")
async def listar(user=Depends(require_permission("usuarios", "ver"))):
    return {"data": [_serialize_role(r) for r in rbac_repo.listar_roles()]}


@router.get("/recursos")
async def recursos(user=Depends(get_current_user)):
    """Catálogo de recursos e ações para montar a matriz de permissões."""
    return {"recursos": RECURSOS, "acoes": list(ACOES)}


@router.get("/{role_id}")
async def obter(role_id: int, user=Depends(require_permission("usuarios", "ver"))):
    role = rbac_repo.obter_role(role_id)
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    perms_rows = {p["recurso"]: p for p in rbac_repo.get_permissions_for_role(role_id)}
    # Devolve uma linha por recurso do catálogo (preenche faltantes com False).
    permissoes = []
    for r in RECURSOS:
        row = perms_rows.get(r["key"], {})
        permissoes.append({
            "recurso": r["key"],
            "ver": bool(row.get("ver")),
            "criar": bool(row.get("criar")),
            "editar": bool(row.get("editar")),
            "excluir": bool(row.get("excluir")),
        })
    return _serialize_role(role, permissoes)


@router.post("", status_code=201)
async def criar(body: RoleCreate, user=Depends(require_permission("usuarios", "criar"))):
    nome = (body.nome or "").strip()
    if not nome:
        raise HTTPException(422, "Nome do perfil é obrigatório.")
    if rbac_repo.obter_role_por_nome(nome):
        raise HTTPException(409, "Já existe um perfil com esse nome.")
    perms = [p.model_dump() for p in body.permissoes]
    try:
        rid = rbac_repo.criar_role(nome, body.descricao, perms)
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar perfil: {e}")
    return await obter(rid, user)


@router.put("/{role_id}")
async def atualizar(role_id: int, body: RoleUpdate, user=Depends(require_permission("usuarios", "editar"))):
    role = rbac_repo.obter_role(role_id)
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    if role.get("is_system"):
        raise HTTPException(403, "O perfil Administrador é protegido e não pode ser editado.")
    nome = (body.nome or "").strip()
    if not nome:
        raise HTTPException(422, "Nome do perfil é obrigatório.")
    existente = rbac_repo.obter_role_por_nome(nome)
    if existente and existente["id"] != role_id:
        raise HTTPException(409, "Já existe um perfil com esse nome.")
    perms = [p.model_dump() for p in body.permissoes]
    try:
        rbac_repo.atualizar_role(role_id, nome, body.descricao, perms)
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar perfil: {e}")
    return await obter(role_id, user)


@router.delete("/{role_id}")
async def deletar(role_id: int, user=Depends(require_permission("usuarios", "excluir"))):
    role = rbac_repo.obter_role(role_id)
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    if role.get("is_system"):
        raise HTTPException(403, "O perfil Administrador é protegido e não pode ser excluído.")
    if rbac_repo.contar_usuarios(role_id) > 0:
        raise HTTPException(409, "Há usuários vinculados a este perfil. Reatribua-os antes de excluir.")
    rbac_repo.deletar_role(role_id)
    return {"mensagem": "Perfil excluído com sucesso."}
