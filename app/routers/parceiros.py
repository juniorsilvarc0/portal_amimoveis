"""Router de parceiros (construtoras, imobiliárias, autônomos)."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import parceiros_repo
from app.schemas.parceiro import ParceiroCreate, ParceiroUpdate, ParceiroRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/parceiros", tags=["Parceiros"])


@router.get("", response_model=PagedResponse[ParceiroRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    tipo: str | None = None,
    cidade_id: int | None = None,
    user=Depends(require_permission("cad_parceiros", "ver")),
):
    rows, total = parceiros_repo.listar(
        page=page, per_page=per_page, search=search, tipo=tipo, cidade_id=cidade_id
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


@router.get("/{parceiro_id}", response_model=ParceiroRead)
async def obter(parceiro_id: int, user=Depends(require_permission("cad_parceiros", "ver"))):
    p = parceiros_repo.obter(parceiro_id)
    if not p:
        raise HTTPException(404, "Parceiro não encontrado")
    return p


@router.post("", response_model=ParceiroRead, status_code=201)
async def criar(body: ParceiroCreate, user=Depends(require_permission("cad_parceiros", "criar"))):
    try:
        new_id = parceiros_repo.criar(body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Parceiro já cadastrado")
        raise HTTPException(500, f"Erro ao criar parceiro: {e}")
    return parceiros_repo.obter(new_id)


@router.put("/{parceiro_id}", response_model=ParceiroRead)
async def atualizar(parceiro_id: int, body: ParceiroUpdate, user=Depends(require_permission("cad_parceiros", "editar"))):
    ok = parceiros_repo.atualizar(parceiro_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Parceiro não encontrado")
    return parceiros_repo.obter(parceiro_id)


@router.delete("/{parceiro_id}", response_model=MessageResponse)
async def deletar(parceiro_id: int, user=Depends(require_permission("cad_parceiros", "excluir"))):
    try:
        ok = parceiros_repo.deletar(parceiro_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Parceiro em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Parceiro não encontrado")
    return {"mensagem": "Parceiro removido"}
