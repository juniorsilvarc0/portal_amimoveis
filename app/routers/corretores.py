"""Router de corretores.

POST é PÚBLICO (cadastro aberto via /corretor/cadastro). Listagem,
edição e exclusão exigem perfil admin (gerência via /cadastros/corretores).
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import corretores_repo, settings_repo
from app.schemas.corretor import CorretorCreate, CorretorUpdate, CorretorRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/corretores", tags=["Corretores"])


@router.get("", response_model=PagedResponse[CorretorRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    cidade_id: int | None = None,
    user=Depends(require_permission("cad_corretores", "ver")),
):
    rows, total = corretores_repo.listar(
        page=page, per_page=per_page, search=search, cidade_id=cidade_id
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


@router.get("/{corretor_id}", response_model=CorretorRead)
async def obter(corretor_id: int, user=Depends(require_permission("cad_corretores", "ver"))):
    c = corretores_repo.obter(corretor_id)
    if not c:
        raise HTTPException(404, "Corretor não encontrado")
    return c


# POST é PÚBLICO — qualquer um pode se cadastrar via /corretor/cadastro,
# desde que o admin tenha o flag `corretores_publico_ativo` ligado.
@router.post("", response_model=CorretorRead, status_code=201)
async def criar(body: CorretorCreate):
    if not settings_repo.get_bool("corretores_publico_ativo", default=True):
        raise HTTPException(403, "Cadastro público de corretores está desativado.")
    try:
        new_id = corretores_repo.criar(body.model_dump(exclude_unset=True))
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Corretor já cadastrado")
        raise HTTPException(500, f"Erro ao criar corretor: {e}")
    return corretores_repo.obter(new_id)


@router.put("/{corretor_id}", response_model=CorretorRead)
async def atualizar(corretor_id: int, body: CorretorUpdate, user=Depends(require_permission("cad_corretores", "editar"))):
    ok = corretores_repo.atualizar(corretor_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Corretor não encontrado")
    return corretores_repo.obter(corretor_id)


@router.delete("/{corretor_id}", response_model=MessageResponse)
async def deletar(corretor_id: int, user=Depends(require_permission("cad_corretores", "excluir"))):
    try:
        ok = corretores_repo.deletar(corretor_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Corretor em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Corretor não encontrado")
    return {"mensagem": "Corretor removido"}
