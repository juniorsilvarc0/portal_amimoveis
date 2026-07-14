"""Repositório de campanhas de marketing/origem de leads."""
import math
from .connection import cursor


_CAMPOS = ["nome", "tipo", "status", "data_inicio", "data_fim",
           "orcamento", "descricao", "ativo"]


def listar(page: int = 1, per_page: int = 25, search: str = None, ativo: bool = None):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []
    if search:
        where += " AND nome ILIKE %s"
        params.append(f"%{search}%")
    if ativo is not None:
        where += " AND ativo = %s"
        params.append(ativo)

    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM crm_campaigns {where}", params)
        total = cur.fetchone()["count"]
        cur.execute(
            f"SELECT * FROM crm_campaigns {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]
    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM crm_campaigns WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    params = {c: dados.get(c) for c in _CAMPOS}
    if params.get("ativo") is None:
        params["ativo"] = True
    with cursor() as cur:
        cur.execute(
            f"INSERT INTO crm_campaigns ({cols}) VALUES ({placeholders}) RETURNING id",
            params,
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    sets = ", ".join(f"{c} = COALESCE(%({c})s, {c})" for c in _CAMPOS)
    params = {c: dados.get(c) for c in _CAMPOS}
    params["id"] = id
    with cursor() as cur:
        cur.execute(
            f"UPDATE crm_campaigns SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM crm_campaigns WHERE id = %s", (id,))
        return cur.rowcount > 0
