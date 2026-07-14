"""Router de Recibos.

Endpoints:
  GET    /api/v1/recibos           — lista paginada
  GET    /api/v1/recibos/{id}      — obter recibo
  POST   /api/v1/recibos           — criar (com cliente embutido opcional)
  PUT    /api/v1/recibos/{id}      — atualizar
  DELETE /api/v1/recibos/{id}      — deletar
  GET    /api/v1/recibos/{id}/pdf  — gera PDF
"""
from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import recibos_repo, clientes_repo, conjuges_repo, logos_repo

router = APIRouter(prefix="/api/v1/recibos", tags=["Recibos"])


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
    user: dict = Depends(require_permission("recibo", "ver")),
):
    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    filters = {}
    if cliente_id is not None:
        filters["cliente_id"] = cliente_id
    rows, total = recibos_repo.listar(page=page, per_page=per_page, search=search, **filters)
    return _paged(rows, total, page, per_page)


# ---------------------------------------------------------------------------
# Obter
# ---------------------------------------------------------------------------

@router.get("/{id}")
async def obter(id: int, user: dict = Depends(require_permission("recibo", "ver"))):
    recibo = recibos_repo.obter(id)
    if not recibo:
        raise HTTPException(status_code=404, detail="Recibo não encontrado.")
    return recibo


# ---------------------------------------------------------------------------
# Criar
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def criar(body: dict, user: dict = Depends(require_permission("recibo", "criar"))):
    # cliente_id é opcional para recibos
    cliente_id = None
    if body.get("cliente_id") or body.get("cliente"):
        try:
            cliente_id = _resolve_cliente_id(body)
        except HTTPException:
            pass
    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge")}
    dados["cliente_id"] = cliente_id

    try:
        rid = recibos_repo.criar(dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return recibos_repo.obter(rid)


# ---------------------------------------------------------------------------
# Atualizar
# ---------------------------------------------------------------------------

@router.put("/{id}")
async def atualizar(id: int, body: dict, user: dict = Depends(require_permission("recibo", "editar"))):
    if not recibos_repo.obter(id):
        raise HTTPException(status_code=404, detail="Recibo não encontrado.")

    if body.get("cliente") or body.get("conjuge"):
        try:
            _resolve_cliente_id(body)
        except HTTPException:
            pass

    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge")}

    try:
        recibos_repo.atualizar(id, dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return recibos_repo.obter(id)


# ---------------------------------------------------------------------------
# Deletar
# ---------------------------------------------------------------------------

@router.delete("/{id}")
async def deletar(id: int, user: dict = Depends(require_permission("recibo", "excluir"))):
    if not recibos_repo.obter(id):
        raise HTTPException(status_code=404, detail="Recibo não encontrado.")
    try:
        recibos_repo.deletar(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"mensagem": "Recibo excluído com sucesso."}


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@router.get("/{id}/pdf")
async def gerar_pdf(id: int, user: dict = Depends(require_permission("recibo", "ver"))):
    recibo = recibos_repo.obter(id)
    if not recibo:
        raise HTTPException(status_code=404, detail="Recibo não encontrado.")

    # Se tem logo_id, buscar a imagem para passar ao template
    logo_bytes = None
    logo_content_type = None
    if recibo.get("logo_id"):
        result = logos_repo.obter_imagem(recibo["logo_id"])
        if result:
            logo_bytes, logo_content_type = result

    from app.services.pdf_service import gerar_pdf_recibo
    try:
        pdf_bytes = gerar_pdf_recibo(recibo, logo_bytes=logo_bytes, logo_content_type=logo_content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {e}")

    nome = (recibo.get("cliente_nome") or "recibo").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_{nome}_{id}.pdf"'},
    )
