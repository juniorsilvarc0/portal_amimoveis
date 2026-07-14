"""Router de agências bancárias."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import agencias_repo
from app.schemas.agencia import AgenciaCreate, AgenciaUpdate, AgenciaRead
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/agencias", tags=["Agências"])


@router.get("", response_model=PagedResponse[AgenciaRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    cidade_id: int | None = None,
    user=Depends(require_permission("cad_agencias", "ver")),
):
    rows, total = agencias_repo.listar(page=page, per_page=per_page, search=search, cidade_id=cidade_id)
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    }


@router.get("/{agencia_id}", response_model=AgenciaRead)
async def obter(agencia_id: int, user=Depends(require_permission("cad_agencias", "ver"))):
    a = agencias_repo.obter(agencia_id)
    if not a:
        raise HTTPException(404, "Agência não encontrada")
    return a


@router.post("", response_model=AgenciaRead, status_code=201)
async def criar(body: AgenciaCreate, user=Depends(require_permission("cad_agencias", "criar"))):
    try:
        new_id = agencias_repo.criar(body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Agência já cadastrada")
        raise HTTPException(500, f"Erro ao criar agência: {e}")
    return agencias_repo.obter(new_id)


@router.put("/{agencia_id}", response_model=AgenciaRead)
async def atualizar(agencia_id: int, body: AgenciaUpdate, user=Depends(require_permission("cad_agencias", "editar"))):
    ok = agencias_repo.atualizar(agencia_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Agência não encontrada")
    return agencias_repo.obter(agencia_id)


@router.delete("/{agencia_id}", response_model=MessageResponse)
async def deletar(agencia_id: int, user=Depends(require_permission("cad_agencias", "excluir"))):
    try:
        ok = agencias_repo.deletar(agencia_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Agência em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Agência não encontrada")
    return {"mensagem": "Agência removida"}
