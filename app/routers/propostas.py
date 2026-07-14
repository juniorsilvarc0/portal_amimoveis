"""Router de Propostas v2.

Endpoints:
  GET    /api/v1/propostas        — lista paginada
  GET    /api/v1/propostas/{id}   — obter proposta com pagamentos
  POST   /api/v1/propostas        — criar (com cliente embutido + pagamentos)
  PUT    /api/v1/propostas/{id}   — atualizar (substitui pagamentos)
  DELETE /api/v1/propostas/{id}   — deletar
  GET    /api/v1/propostas/{id}/pdf — gera PDF
"""
from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import propostas_repo, clientes_repo, conjuges_repo

router = APIRouter(prefix="/api/v1/propostas", tags=["Proposta"])


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
    user: dict = Depends(require_permission("proposta", "ver")),
):
    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    filters = {}
    if cliente_id is not None:
        filters["cliente_id"] = cliente_id
    rows, total = propostas_repo.listar(page=page, per_page=per_page, search=search, **filters)
    return _paged(rows, total, page, per_page)


# ---------------------------------------------------------------------------
# Obter
# ---------------------------------------------------------------------------

@router.get("/{id}")
async def obter(
    id: int,
    user: dict = Depends(require_permission("proposta", "ver")),
):
    proposta = propostas_repo.obter_com_pagamentos(id)
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")
    return proposta


# ---------------------------------------------------------------------------
# Criar
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def criar(
    body: dict,
    user: dict = Depends(require_permission("proposta", "criar")),
):
    cliente_id = _resolve_cliente_id(body)
    pagamentos = body.get("pagamentos") or []
    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge", "pagamentos")}
    dados["cliente_id"] = cliente_id

    try:
        pid = propostas_repo.criar_com_pagamentos(dados, pagamentos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return propostas_repo.obter_com_pagamentos(pid)


# ---------------------------------------------------------------------------
# Atualizar
# ---------------------------------------------------------------------------

@router.put("/{id}")
async def atualizar(
    id: int,
    body: dict,
    user: dict = Depends(require_permission("proposta", "editar")),
):
    if not propostas_repo.obter(id):
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")

    if body.get("cliente") or body.get("conjuge"):
        try:
            _resolve_cliente_id(body)
        except HTTPException:
            pass

    pagamentos = body.get("pagamentos") or []
    dados = {k: v for k, v in body.items() if k not in ("cliente", "conjuge", "pagamentos")}

    try:
        propostas_repo.atualizar_com_pagamentos(id, dados, pagamentos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return propostas_repo.obter_com_pagamentos(id)


# ---------------------------------------------------------------------------
# Deletar
# ---------------------------------------------------------------------------

@router.delete("/{id}")
async def deletar(
    id: int,
    user: dict = Depends(require_permission("proposta", "excluir")),
):
    if not propostas_repo.obter(id):
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")
    try:
        propostas_repo.deletar(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"mensagem": "Proposta excluída com sucesso."}


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@router.get("/{id}/pdf")
async def gerar_pdf(
    id: int,
    user: dict = Depends(require_permission("proposta", "ver")),
):
    proposta = propostas_repo.obter_com_pagamentos(id)
    if not proposta:
        raise HTTPException(status_code=404, detail="Proposta não encontrada.")

    # Enriquece com dados do cliente para o mapeamento do template
    try:
        cliente = clientes_repo.obter(proposta["cliente_id"])
        if cliente:
            for campo in (
                "nacionalidade", "estado_civil", "regime_bens", "nascimento",
                "profissao", "rg", "rg_orgao", "endereco", "bairro",
                "cep", "telefone_fixo", "whatsapp1", "whatsapp2", "email",
            ):
                proposta.setdefault(f"cliente_{campo}", cliente.get(campo))
            proposta.setdefault("cliente_cidade_nome", cliente.get("cidade_nome"))
    except Exception:
        pass

    from app.services.pdf_service import gerar_pdf_proposta
    try:
        pdf_bytes = gerar_pdf_proposta(proposta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar PDF: {e}")

    nome = (proposta.get("cliente_nome") or "proposta").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="proposta_{nome}_{id}.pdf"'},
    )
