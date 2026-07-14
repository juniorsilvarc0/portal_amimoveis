"""Router de Fichas Habitacionais v2.

Endpoints:
  GET    /api/v1/habitacao        — lista paginada
  GET    /api/v1/habitacao/{id}   — obter ficha
  POST   /api/v1/habitacao        — criar (com cliente embutido opcional)
  PUT    /api/v1/habitacao/{id}   — atualizar
  DELETE /api/v1/habitacao/{id}   — deletar
  GET    /api/v1/habitacao/{id}/pdf — gera PDF
"""
from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import habitacao_repo, clientes_repo, conjuges_repo

router = APIRouter(prefix="/api/v1/habitacao", tags=["Habitação"])


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
    """Obtém/cria cliente_id a partir do body.

    Precedência:
    1. cliente_id explícito no body.
    2. upsert via body['cliente']['cpf'].
    """
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
    empreendimento: Optional[str] = None,
    user: dict = Depends(require_permission("habitacao", "ver")),
):
    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    filters = {}
    if cliente_id is not None:
        filters["cliente_id"] = cliente_id
    if empreendimento:
        filters["empreendimento"] = empreendimento
    rows, total = habitacao_repo.listar(page=page, per_page=per_page, search=search, **filters)
    return _paged(rows, total, page, per_page)


# ---------------------------------------------------------------------------
# Obter
# ---------------------------------------------------------------------------

@router.get("/{id}")
async def obter(
    id: int,
    user: dict = Depends(require_permission("habitacao", "ver")),
):
    ficha = habitacao_repo.obter(id)
    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada.")
    return ficha


# ---------------------------------------------------------------------------
# Criar
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def criar(
    body: dict,
    user: dict = Depends(require_permission("habitacao", "criar")),
):
    cliente_id = _resolve_cliente_id(body)
    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge")}
    dados["cliente_id"] = cliente_id

    try:
        fid = habitacao_repo.criar(dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    ficha = habitacao_repo.obter(fid)
    return ficha


# ---------------------------------------------------------------------------
# Atualizar
# ---------------------------------------------------------------------------

@router.put("/{id}")
async def atualizar(
    id: int,
    body: dict,
    user: dict = Depends(require_permission("habitacao", "editar")),
):
    if not habitacao_repo.obter(id):
        raise HTTPException(status_code=404, detail="Ficha não encontrada.")

    # Opcionalmente sincroniza cliente/cônjuge se vieram no body
    if body.get("cliente") or body.get("conjuge"):
        try:
            _resolve_cliente_id(body)
        except HTTPException:
            pass

    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge")}

    try:
        habitacao_repo.atualizar(id, dados)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return habitacao_repo.obter(id)


# ---------------------------------------------------------------------------
# Deletar
# ---------------------------------------------------------------------------

@router.delete("/{id}")
async def deletar(
    id: int,
    user: dict = Depends(require_permission("habitacao", "excluir")),
):
    if not habitacao_repo.obter(id):
        raise HTTPException(status_code=404, detail="Ficha não encontrada.")
    try:
        habitacao_repo.deletar(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"mensagem": "Ficha excluída com sucesso."}


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@router.get("/{id}/pdf")
async def gerar_pdf(
    id: int,
    user: dict = Depends(require_permission("habitacao", "ver")),
):
    ficha = habitacao_repo.obter(id)
    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada.")

    # Enriquece com dados do cliente para o mapeamento do template
    try:
        cliente = clientes_repo.obter(ficha["cliente_id"])
        if cliente:
            ficha.setdefault("cliente_whatsapp1", cliente.get("whatsapp1"))
            ficha.setdefault("cliente_email", cliente.get("email"))
    except Exception:
        pass

    from app.services.pdf_service import gerar_pdf_habitacao
    try:
        pdf_bytes = gerar_pdf_habitacao(ficha)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {e}")

    nome = (ficha.get("cliente_nome") or "ficha").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ficha_{nome}_{id}.pdf"'},
    )


# ---------------------------------------------------------------------------
# XLSX (mesma estrutura da ficha do PDF)
# ---------------------------------------------------------------------------

@router.get("/{id}/xlsx")
async def gerar_xlsx(
    id: int,
    user: dict = Depends(require_permission("habitacao", "ver")),
):
    ficha = habitacao_repo.obter(id)
    if not ficha:
        raise HTTPException(status_code=404, detail="Ficha não encontrada.")

    # Mesmo enriquecimento do PDF para não perder telefone/email do cliente
    try:
        cliente = clientes_repo.obter(ficha["cliente_id"])
        if cliente:
            ficha.setdefault("cliente_whatsapp1", cliente.get("whatsapp1"))
            ficha.setdefault("cliente_email", cliente.get("email"))
    except Exception:
        pass

    from app.services.excel_service import gerar_xlsx_habitacao
    try:
        xlsx_bytes = gerar_xlsx_habitacao(ficha)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar XLSX: {e}")

    nome = (ficha.get("cliente_nome") or "ficha").replace(" ", "_")
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="ficha_{nome}_{id}.xlsx"'},
    )
