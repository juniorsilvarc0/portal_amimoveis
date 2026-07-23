"""Router de imóveis/empreendimentos."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import imoveis_repo, imovel_unidades_repo
from app.schemas.imovel import (
    ImovelCreate, ImovelUpdate, ImovelRead,
    UnidadeCreate, UnidadeUpdate, UnidadeRead,
)
from app.schemas.common import PagedResponse, MessageResponse

router = APIRouter(prefix="/api/v1/imoveis", tags=["Imóveis"])


@router.get("", response_model=PagedResponse[ImovelRead])
async def listar(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=500),
    search: str | None = None,
    cidade_id: int | None = None,
    construtora_id: int | None = None,
    user=Depends(require_permission("cad_imoveis", "ver")),
):
    rows, total = imoveis_repo.listar(
        page=page, per_page=per_page, search=search,
        cidade_id=cidade_id, construtora_id=construtora_id,
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


# ---------------------------------------------------------------------------
# Unidades de um imóvel (Apto 302, Casa 15...). Sob a mesma permissão cad_imoveis.
# Declaradas ANTES de /{imovel_id} para "unidades" não ser capturado como id.
# ---------------------------------------------------------------------------

@router.get("/{imovel_id}/unidades", response_model=list[UnidadeRead])
async def listar_unidades(imovel_id: int, user=Depends(require_permission("cad_imoveis", "ver"))):
    if not imoveis_repo.obter(imovel_id):
        raise HTTPException(404, "Imóvel não encontrado")
    return imovel_unidades_repo.listar_por_imovel(imovel_id)


@router.post("/{imovel_id}/unidades", response_model=UnidadeRead, status_code=201)
async def criar_unidade(imovel_id: int, body: UnidadeCreate,
                        user=Depends(require_permission("cad_imoveis", "criar"))):
    if not imoveis_repo.obter(imovel_id):
        raise HTTPException(404, "Imóvel não encontrado")
    try:
        new_id = imovel_unidades_repo.criar(imovel_id, body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Já existe uma unidade com esse identificador neste imóvel.")
        raise HTTPException(500, f"Erro ao criar unidade: {e}")
    return imovel_unidades_repo.obter(new_id)


@router.put("/unidades/{unidade_id}", response_model=UnidadeRead)
async def atualizar_unidade(unidade_id: int, body: UnidadeUpdate,
                            user=Depends(require_permission("cad_imoveis", "editar"))):
    try:
        ok = imovel_unidades_repo.atualizar(unidade_id, body.model_dump(exclude_unset=True))
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Já existe uma unidade com esse identificador neste imóvel.")
        raise
    if not ok:
        raise HTTPException(404, "Unidade não encontrada")
    return imovel_unidades_repo.obter(unidade_id)


@router.delete("/unidades/{unidade_id}", response_model=MessageResponse)
async def deletar_unidade(unidade_id: int, user=Depends(require_permission("cad_imoveis", "excluir"))):
    if not imovel_unidades_repo.deletar(unidade_id):
        raise HTTPException(404, "Unidade não encontrada")
    return {"mensagem": "Unidade removida"}


@router.get("/{imovel_id}", response_model=ImovelRead)
async def obter(imovel_id: int, user=Depends(require_permission("cad_imoveis", "ver"))):
    i = imoveis_repo.obter(imovel_id)
    if not i:
        raise HTTPException(404, "Imóvel não encontrado")
    return i


@router.post("", response_model=ImovelRead, status_code=201)
async def criar(body: ImovelCreate, user=Depends(require_permission("cad_imoveis", "criar"))):
    try:
        new_id = imoveis_repo.criar(body.model_dump())
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, "Imóvel já cadastrado")
        raise HTTPException(500, f"Erro ao criar imóvel: {e}")
    return imoveis_repo.obter(new_id)


@router.put("/{imovel_id}", response_model=ImovelRead)
async def atualizar(imovel_id: int, body: ImovelUpdate, user=Depends(require_permission("cad_imoveis", "editar"))):
    ok = imoveis_repo.atualizar(imovel_id, body.model_dump(exclude_unset=True))
    if not ok:
        raise HTTPException(404, "Imóvel não encontrado")
    return imoveis_repo.obter(imovel_id)


@router.delete("/{imovel_id}", response_model=MessageResponse)
async def deletar(imovel_id: int, user=Depends(require_permission("cad_imoveis", "excluir"))):
    try:
        ok = imoveis_repo.deletar(imovel_id)
    except Exception as e:
        if "violates foreign key" in str(e).lower():
            raise HTTPException(409, "Imóvel em uso por outras entidades; remova dependências primeiro")
        raise
    if not ok:
        raise HTTPException(404, "Imóvel não encontrado")
    return {"mensagem": "Imóvel removido"}
