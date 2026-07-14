"""Router de Financiamentos.

Endpoints:
  GET    /api/v1/financiamentos        — lista paginada
  GET    /api/v1/financiamentos/{id}   — obter
  POST   /api/v1/financiamentos        — criar (com cliente embutido opcional)
  PUT    /api/v1/financiamentos/{id}   — atualizar
  DELETE /api/v1/financiamentos/{id}   — deletar
"""
from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import financiamentos_repo, clientes_repo, conjuges_repo

router = APIRouter(prefix="/api/v1/financiamentos", tags=["Financiamento"])


def _paged(rows, total, page, per_page):
    return {
        "data": rows,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, math.ceil(total / per_page)),
        },
    }


def _resolve_cliente_id(body: dict) -> int:
    """Obtém/cria cliente_id a partir do body."""
    cliente_id = body.get("cliente_id")
    if cliente_id:
        return int(cliente_id)

    cliente_data = body.get("cliente")
    if not cliente_data:
        raise HTTPException(status_code=422, detail="cliente_id ou bloco 'cliente' com cpf são obrigatórios.")

    cpf = cliente_data.get("cpf", "")
    if not cpf:
        raise HTTPException(status_code=422, detail="cpf é obrigatório no bloco 'cliente'.")

    cliente_id = clientes_repo.upsert_por_cpf(cliente_data)

    conjuge_data = body.get("conjuge")
    if conjuge_data and conjuge_data.get("nome"):
        conjuge_data["cliente_id"] = cliente_id
        try:
            conjuges_repo.upsert_por_cliente(cliente_id, conjuge_data)
        except Exception:
            pass

    return cliente_id


# ---------------------------------------------------------------------------
# Listar
# ---------------------------------------------------------------------------

@router.get("")
async def listar(
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    cliente_id: Optional[int] = None,
    analise: Optional[str] = None,
    modalidade: Optional[str] = None,
    cidade_id: Optional[int] = None,
    parceiro_id: Optional[int] = None,
    user: dict = Depends(require_permission("financiamento", "ver")),
):
    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    filters = {}
    if cliente_id is not None:
        filters["cliente_id"] = cliente_id
    if analise:
        filters["analise"] = analise
    if modalidade:
        filters["modalidade"] = modalidade
    if cidade_id is not None:
        filters["cidade_id"] = cidade_id
    if parceiro_id is not None:
        filters["parceiro_id"] = parceiro_id
    rows, total = financiamentos_repo.listar(page=page, per_page=per_page, search=search, **filters)
    return _paged(rows, total, page, per_page)


# ---------------------------------------------------------------------------
# Obter
# ---------------------------------------------------------------------------

@router.get("/{id}")
async def obter(
    id: int,
    user: dict = Depends(require_permission("financiamento", "ver")),
):
    fin = financiamentos_repo.obter(id)
    if not fin:
        raise HTTPException(status_code=404, detail="Financiamento não encontrado.")
    return fin


# ---------------------------------------------------------------------------
# Criar
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def criar(
    body: dict,
    user: dict = Depends(require_permission("financiamento", "criar")),
):
    cliente_id = _resolve_cliente_id(body)
    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge")}
    dados["cliente_id"] = cliente_id

    try:
        fid = financiamentos_repo.criar(dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return financiamentos_repo.obter(fid)


# ---------------------------------------------------------------------------
# Atualizar
# ---------------------------------------------------------------------------

@router.put("/{id}")
async def atualizar(
    id: int,
    body: dict,
    user: dict = Depends(require_permission("financiamento", "editar")),
):
    if not financiamentos_repo.obter(id):
        raise HTTPException(status_code=404, detail="Financiamento não encontrado.")

    if body.get("cliente") or body.get("conjuge"):
        try:
            _resolve_cliente_id(body)
        except HTTPException:
            pass

    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge")}

    try:
        financiamentos_repo.atualizar(id, dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return financiamentos_repo.obter(id)


# ---------------------------------------------------------------------------
# Deletar
# ---------------------------------------------------------------------------

@router.delete("/{id}")
async def deletar(
    id: int,
    user: dict = Depends(require_permission("financiamento", "excluir")),
):
    if not financiamentos_repo.obter(id):
        raise HTTPException(status_code=404, detail="Financiamento não encontrado.")
    try:
        financiamentos_repo.deletar(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"mensagem": "Financiamento excluído com sucesso."}
