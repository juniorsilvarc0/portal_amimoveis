"""Router de cidades."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import cidades_repo
from app.schemas.cidade import CidadeCreate, CidadeUpdate, CidadeRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/cidades", tags=["Cidades"])


@router.get("", response_model=PagedResponse[CidadeRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    uf: str | None = None,
    user=Depends(require_permission("cad_cidades", "ver")),
):
    rows, total = cidades_repo.listar(page=page, per_page=per_page, search=search, uf=uf)
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    }


@router.get("/{cidade_id}", response_model=CidadeRead)
async def obter(cidade_id: int, user=Depends(require_permission("cad_cidades", "ver"))):
    c = cidades_repo.obter(cidade_id)
    if not c:
        raise HTTPException(404, "Cidade não encontrada")
    return c


@router.post("", response_model=CidadeRead, status_code=201)
async def criar(body: CidadeCreate, user=Depends(require_permission("cad_cidades", "criar"))):
    try:
        new_id = cidades_repo.criar(body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Cidade já cadastrada (nome+UF)")
        raise HTTPException(500, f"Erro ao criar cidade: {e}")
    return cidades_repo.obter(new_id)


@router.put("/{cidade_id}", response_model=CidadeRead)
async def atualizar(cidade_id: int, body: CidadeUpdate, user=Depends(require_permission("cad_cidades", "editar"))):
    ok = cidades_repo.atualizar(cidade_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Cidade não encontrada")
    return cidades_repo.obter(cidade_id)


@router.delete("/{cidade_id}", response_model=MessageResponse)
async def deletar(cidade_id: int, user=Depends(require_permission("cad_cidades", "excluir"))):
    try:
        ok = cidades_repo.deletar(cidade_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Cidade em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Cidade não encontrada")
    return {"mensagem": "Cidade removida"}
