"""Router de correspondentes bancários."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import correspondentes_repo
from app.schemas.correspondente import CorrespondenteCreate, CorrespondenteUpdate, CorrespondenteRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/correspondentes", tags=["Correspondentes"])


@router.get("", response_model=PagedResponse[CorrespondenteRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    cidade_id: int | None = None,
    user=Depends(require_permission("cad_correspondentes", "ver")),
):
    rows, total = correspondentes_repo.listar(
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


@router.get("/{correspondente_id}", response_model=CorrespondenteRead)
async def obter(correspondente_id: int, user=Depends(require_permission("cad_correspondentes", "ver"))):
    c = correspondentes_repo.obter(correspondente_id)
    if not c:
        raise HTTPException(404, "Correspondente não encontrado")
    return c


@router.post("", response_model=CorrespondenteRead, status_code=201)
async def criar(body: CorrespondenteCreate, user=Depends(require_permission("cad_correspondentes", "criar"))):
    try:
        new_id = correspondentes_repo.criar(body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Correspondente já cadastrado")
        raise HTTPException(500, f"Erro ao criar correspondente: {e}")
    return correspondentes_repo.obter(new_id)


@router.put("/{correspondente_id}", response_model=CorrespondenteRead)
async def atualizar(correspondente_id: int, body: CorrespondenteUpdate, user=Depends(require_permission("cad_correspondentes", "editar"))):
    ok = correspondentes_repo.atualizar(correspondente_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Correspondente não encontrado")
    return correspondentes_repo.obter(correspondente_id)


@router.delete("/{correspondente_id}", response_model=MessageResponse)
async def deletar(correspondente_id: int, user=Depends(require_permission("cad_correspondentes", "excluir"))):
    try:
        ok = correspondentes_repo.deletar(correspondente_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Correspondente em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Correspondente não encontrado")
    return {"mensagem": "Correspondente removido"}
