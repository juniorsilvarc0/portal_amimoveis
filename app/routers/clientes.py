"""Router de Clientes — CRUD completo + lookup por CPF.

Endpoints:
  GET    /api/v1/clientes                  — lista paginada (ou lookup se ?cpf= fornecido)
  GET    /api/v1/clientes/por-cpf/{cpf}    — lookup direto por CPF (usado cross-módulo)
  GET    /api/v1/clientes/{id}             — obter cliente com cônjuge
  POST   /api/v1/clientes                  — criar (com cônjuge opcional no body)
  PUT    /api/v1/clientes/{id}             — atualizar (com cônjuge opcional)
  DELETE /api/v1/clientes/{id}             — deletar
"""
from __future__ import annotations

import math
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission, user_can
from app.db import clientes_repo, conjuges_repo, cliente_notas_repo
from app.db.connection import cursor as db_cursor
from app.schemas.cliente import ClienteCreate, ClienteUpdate
from app.schemas.conjuge import ConjugeBase

router = APIRouter(prefix="/api/v1/clientes", tags=["Clientes"])


# ---------------------------------------------------------------------------
# Schema inline para body com cônjuge embutido
# ---------------------------------------------------------------------------

class ConjugeInline(ConjugeBase):
    """ConjugeBase sem exigir cliente_id (será preenchido automaticamente)."""
    cliente_id: int = 0  # ignorado, será sobrescrito


class ClienteComConjuge(ClienteCreate):
    conjuge: Optional[ConjugeInline] = None


class ClienteComConjugeUpdate(ClienteUpdate):
    conjuge: Optional[ConjugeInline] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def listar_ou_lookup(
    cpf: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
    search: Optional[str] = None,
    cidade_id: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    """Lista clientes com paginação.

    Se o query param ``cpf`` for fornecido com 11+ dígitos, funciona como
    lookup: retorna o objeto cliente (com cônjuge aninhado) ou HTTP 404.
    Isso suporta o ``cpf_lookup.js`` do frontend.
    """
    if cpf is not None:
        # Modo lookup por CPF — liberado a qualquer autenticado (usado cross-módulo).
        cpf_clean = _norm_cpf(cpf)
        if len(cpf_clean) < 11:
            raise HTTPException(status_code=400, detail="CPF incompleto (mínimo 11 dígitos).")
        cliente = clientes_repo.obter_por_cpf(cpf_clean)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não cadastrado.")
        return cliente  # objeto único, não paginado

    # Modo listagem — exige permissão de visualizar clientes.
    if not user_can(user, "clientes", "ver"):
        raise HTTPException(status_code=403, detail="Acesso negado: sem permissão para ver clientes.")

    filters = {}
    if cidade_id is not None:
        filters["cidade_id"] = cidade_id

    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    rows, total = clientes_repo.listar(page=page, per_page=per_page, search=search, **filters)
    return _paged(rows, total, page, per_page)


@router.get("/por-cpf/{cpf}")
async def por_cpf(
    cpf: str,
    user: dict = Depends(get_current_user),
):
    """Lookup direto por CPF — endpoint canônico para uso cross-módulo.

    Aceita CPF com ou sem máscara. Retorna cliente + cônjuge aninhado.
    """
    cpf_clean = _norm_cpf(cpf)
    if len(cpf_clean) < 11:
        raise HTTPException(status_code=400, detail="CPF incompleto (mínimo 11 dígitos).")
    cliente = clientes_repo.obter_por_cpf(cpf_clean)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return cliente


@router.get("/{id}")
async def obter(
    id: int,
    user: dict = Depends(require_permission("clientes", "ver")),
):
    """Retorna um cliente pelo ID (sem cônjuge aninhado; use /por-cpf para aninhado)."""
    cliente = clientes_repo.obter(id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return cliente


@router.post("", status_code=201)
async def criar(
    body: ClienteComConjuge,
    user: dict = Depends(require_permission("clientes", "criar")),
):
    """Cria cliente. Cônjuge é opcional — incluído no body como ``conjuge: {...}``."""
    payload = body.model_dump()
    conjuge_data = payload.pop("conjuge", None)
    payload["cpf"] = _norm_cpf(payload.get("cpf", ""))

    try:
        cid = clientes_repo.criar(payload)
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(status_code=409, detail="CPF já cadastrado.")
        raise HTTPException(status_code=500, detail=str(e))

    if conjuge_data and conjuge_data.get("nome"):
        conjuge_data["cliente_id"] = cid
        try:
            conjuges_repo.upsert_por_cliente(cid, conjuge_data)
        except Exception:
            pass  # cônjuge falhou mas cliente foi criado — log em produção

    return clientes_repo.obter(cid)


@router.put("/{id}")
async def atualizar(
    id: int,
    body: ClienteComConjugeUpdate,
    user: dict = Depends(require_permission("clientes", "editar")),
):
    """Atualiza cliente. Cônjuge é opcional — incluído no body como ``conjuge: {...}``."""
    # Verifica existência
    if not clientes_repo.obter(id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    # exclude_unset=True garante que campos NÃO enviados pelo cliente
    # NÃO sejam passados ao repo (update parcial real — preserva dados existentes).
    payload = body.model_dump(exclude_unset=True)
    conjuge_data = payload.pop("conjuge", None)
    if "cpf" in payload:
        payload["cpf"] = _norm_cpf(payload.get("cpf") or "")

    try:
        clientes_repo.atualizar(id, payload)
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "duplicate" in msg:
            raise HTTPException(status_code=409, detail="CPF já cadastrado.")
        raise HTTPException(status_code=500, detail=str(e))

    if conjuge_data and conjuge_data.get("nome"):
        conjuge_data["cliente_id"] = id
        try:
            conjuges_repo.upsert_por_cliente(id, conjuge_data)
        except Exception:
            pass

    return clientes_repo.obter(id)


@router.delete("/{id}")
async def deletar(
    id: int,
    user: dict = Depends(require_permission("clientes", "excluir")),
):
    """Deleta cliente. Retorna HTTP 409 se houver registros vinculados."""
    if not clientes_repo.obter(id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    try:
        clientes_repo.deletar(id)
    except Exception as e:
        msg = str(e).lower()
        if "foreign key" in msg or "violates" in msg or "fk_" in msg:
            raise HTTPException(
                status_code=409,
                detail="Cliente possui habitações, propostas ou financiamentos vinculados e não pode ser excluído.",
            )
        raise HTTPException(status_code=500, detail=str(e))
    return {"mensagem": "Cliente excluído com sucesso."}


# ---------------------------------------------------------------------------
# Detail (Salesforce-like) — endpoint enriquecido + inline edit + notas
# ---------------------------------------------------------------------------

@router.get("/{id}/full")
async def obter_full(id: int, user: dict = Depends(require_permission("clientes", "ver"))):
    """Retorna cliente + cônjuge + listas relacionadas (oportunidades, propostas,
    habitações, financiamentos, atividades, notas)."""
    cliente = clientes_repo.obter(id)
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado.")

    # Cônjuge
    with db_cursor() as cur:
        cur.execute("SELECT * FROM conjuges WHERE cliente_id = %s", (id,))
        conj = cur.fetchone()
        cliente["conjuge"] = dict(conj) if conj else None

    # Oportunidades
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT o.id, o.nome, o.valor, o.status, o.data_previsao,
                       s.nome AS stage_nome, s.cor AS stage_cor
                  FROM crm_opportunities o
                  JOIN crm_stages s ON s.id = o.stage_id
                 WHERE o.cliente_id = %s
                 ORDER BY o.created_at DESC LIMIT 20
            """, (id,))
            cliente["oportunidades"] = [dict(r) for r in cur.fetchall()]
    except Exception:
        cliente["oportunidades"] = []

    # Propostas
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, empreendimento, unidade, valor_total, created_at
                  FROM propostas WHERE cliente_id = %s
                  ORDER BY created_at DESC LIMIT 20
            """, (id,))
            cliente["propostas"] = [dict(r) for r in cur.fetchall()]
    except Exception:
        cliente["propostas"] = []

    # Habitações
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, empreendimento, created_at
                  FROM habitacao_fichas WHERE cliente_id = %s
                  ORDER BY created_at DESC LIMIT 20
            """, (id,))
            cliente["habitacao"] = [dict(r) for r in cur.fetchall()]
    except Exception:
        cliente["habitacao"] = []

    # Financiamentos
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, valor_financiamento, analise, created_at
                  FROM financiamentos WHERE cliente_id = %s
                  ORDER BY created_at DESC LIMIT 20
            """, (id,))
            cliente["financiamentos"] = [dict(r) for r in cur.fetchall()]
    except Exception:
        cliente["financiamentos"] = []

    # Recibos
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT id, numero_contrato, valor_recebido, data_recibo
                  FROM recibos WHERE cliente_id = %s
                  ORDER BY created_at DESC LIMIT 20
            """, (id,))
            cliente["recibos"] = [dict(r) for r in cur.fetchall()]
    except Exception:
        cliente["recibos"] = []

    # Atividades (CRM)
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT a.*, u.email AS proprietario_email
                  FROM crm_activities a
                  LEFT JOIN usuarios u ON u.id = a.proprietario_id
                 WHERE a.cliente_id = %s
                 ORDER BY COALESCE(a.data_atividade, a.created_at) DESC LIMIT 30
            """, (id,))
            cliente["activities"] = [dict(r) for r in cur.fetchall()]
    except Exception:
        cliente["activities"] = []

    # Leads histórico (todos os leads vinculados a este cliente — Cliente:N Leads)
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT l.id, l.nome, l.status, l.origem, l.created_at, l.data_conversao,
                       c.nome AS campaign_nome
                  FROM crm_leads l
                  LEFT JOIN crm_campaigns c ON c.id = l.campaign_id
                 WHERE l.cliente_id = %s
                 ORDER BY l.created_at DESC
                 LIMIT 50
            """, (id,))
            cliente["leads"] = [dict(r) for r in cur.fetchall()]
            # primeiro lead = "lead vinculado" (compatibilidade com UI antiga)
            cliente["lead_vinculado"] = cliente["leads"][0] if cliente["leads"] else None
    except Exception:
        cliente["leads"] = []
        cliente["lead_vinculado"] = None

    # Notas (Chatter)
    cliente["notas"] = cliente_notas_repo.listar_por_cliente(id)

    return cliente


@router.patch("/{id}")
async def patch_cliente(id: int, body: dict, user: dict = Depends(require_permission("clientes", "editar"))):
    """Inline update — só atualiza os campos enviados."""
    if not clientes_repo.obter(id):
        raise HTTPException(404, "Cliente não encontrado.")
    body["modificado_por_id"] = user.get("id")
    try:
        clientes_repo.atualizar(id, body)
    except Exception as e:
        raise HTTPException(500, str(e))
    return clientes_repo.obter(id)


# Notas (Chatter)
@router.get("/{id}/notas")
async def listar_notas_cliente(id: int, user: dict = Depends(require_permission("clientes", "ver"))):
    return cliente_notas_repo.listar_por_cliente(id)


@router.post("/{id}/notas", status_code=201)
async def criar_nota_cliente(id: int, body: dict, user: dict = Depends(require_permission("clientes", "editar"))):
    if not body.get("corpo"):
        raise HTTPException(422, "corpo é obrigatório")
    if not clientes_repo.obter(id):
        raise HTTPException(404, "Cliente não encontrado.")
    nota_id = cliente_notas_repo.criar({
        "cliente_id": id,
        "corpo": body["corpo"],
        "criado_por_id": user.get("id"),
    })
    return cliente_notas_repo.obter(nota_id)


@router.delete("/notas/{nota_id}")
async def deletar_nota_cliente(nota_id: int, user: dict = Depends(require_permission("clientes", "editar"))):
    if not cliente_notas_repo.deletar(nota_id):
        raise HTTPException(404, "Nota não encontrada.")
    return {"mensagem": "Nota excluída."}
