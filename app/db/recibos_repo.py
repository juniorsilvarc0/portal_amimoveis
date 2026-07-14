"""Repositório de recibos."""
import json

from psycopg2.extras import Json

from .connection import cursor

_SELECT_FULL = """
SELECT r.*,
       cl.nome                AS cliente_nome,
       cl.cpf                 AS cliente_cpf,
       ci.nome                AS cidade_nome,
       ci.uf                  AS cidade_uf,
       l.nome                 AS logo_nome
  FROM recibos r
  LEFT JOIN clientes  cl ON cl.id = r.cliente_id
  LEFT JOIN cidades   ci ON ci.id = r.cidade_id
  LEFT JOIN logos     l  ON l.id  = r.logo_id
"""


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (cl.nome ILIKE %s OR cl.cpf ILIKE %s OR r.numero_contrato ILIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    cliente_id = filters.get("cliente_id")
    if cliente_id:
        where += " AND r.cliente_id = %s"
        params.append(cliente_id)

    count_sql = (
        "SELECT COUNT(*) FROM recibos r "
        "LEFT JOIN clientes cl ON cl.id = r.cliente_id " + where
    )
    list_sql = f"{_SELECT_FULL} {where} ORDER BY r.created_at DESC LIMIT %s OFFSET %s"

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE r.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


_CAMPOS = [
    "cliente_id", "logo_id", "cidade_id", "numero_contrato",
    "data_recibo", "valor_recebido",
    "nome_pagador", "doc_pagador",
    "forma_pagamento", "formas_pagamento", "descricao_referencia",
    "data_local",
    "assinatura_nome", "doc_recebedor",
    "rodape_texto", "observacoes",
]


def _params(dados: dict, campos) -> dict:
    """Monta os params nomeados, adaptando formas_pagamento (lista) para JSONB."""
    params = {}
    for c in campos:
        v = dados.get(c)
        if c == "formas_pagamento":
            v = Json(v) if v else None
        params[c] = v
    return params


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    sql = f"INSERT INTO recibos ({cols}) VALUES ({placeholders}) RETURNING id"
    params = _params(dados, _CAMPOS)
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    campos = [c for c in _CAMPOS if c != "cliente_id"]
    sets = ", ".join(f"{c} = %({c})s" for c in campos)
    sql = f"UPDATE recibos SET {sets}, updated_at = NOW() WHERE id = %(id)s"
    params = _params(dados, campos)
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM recibos WHERE id = %s", (id,))
        return cur.rowcount > 0
