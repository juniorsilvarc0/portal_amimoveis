"""Router de gerentes de agências."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import gerentes_repo
from app.schemas.gerente import GerenteCreate, GerenteUpdate, GerenteRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/gerentes", tags=["Gerentes"])


@router.get("", response_model=PagedResponse[GerenteRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    agencia_id: int | None = None,
    user=Depends(require_permission("cad_gerentes", "ver")),
):
    rows, total = gerentes_repo.listar(page=page, per_page=per_page, search=search, agencia_id=agencia_id)
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    }


@router.get("/{gerente_id}", response_model=GerenteRead)
async def obter(gerente_id: int, user=Depends(require_permission("cad_gerentes", "ver"))):
    g = gerentes_repo.obter(gerente_id)
    if not g:
        raise HTTPException(404, "Gerente não encontrado")
    return g


@router.post("", response_model=GerenteRead, status_code=201)
async def criar(body: GerenteCreate, user=Depends(require_permission("cad_gerentes", "criar"))):
    try:
        new_id = gerentes_repo.criar(body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Gerente já cadastrado")
        raise HTTPException(500, f"Erro ao criar gerente: {e}")
    return gerentes_repo.obter(new_id)


@router.put("/{gerente_id}", response_model=GerenteRead)
async def atualizar(gerente_id: int, body: GerenteUpdate, user=Depends(require_permission("cad_gerentes", "editar"))):
    ok = gerentes_repo.atualizar(gerente_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Gerente não encontrado")
    return gerentes_repo.obter(gerente_id)


@router.delete("/{gerente_id}", response_model=MessageResponse)
async def deletar(gerente_id: int, user=Depends(require_permission("cad_gerentes", "excluir"))):
    try:
        ok = gerentes_repo.deletar(gerente_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Gerente em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Gerente não encontrado")
    return {"mensagem": "Gerente removido"}
