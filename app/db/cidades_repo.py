"""Repositório de cidades."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (nome ILIKE %s OR uf ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]

    uf = filters.get("uf")
    if uf:
        where += " AND uf = %s"
        params.append(uf.upper())

    count_sql = f"SELECT COUNT(*) FROM cidades {where}"
    list_sql = (
        f"SELECT * FROM cidades {where} "
        f"ORDER BY nome ASC LIMIT %s OFFSET %s"
    )

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM cidades WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO cidades (nome, uf) VALUES (%(nome)s, %(uf)s) RETURNING id",
            {"nome": dados["nome"], "uf": dados["uf"].upper()},
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE cidades SET nome = %s, uf = %s, updated_at = NOW() WHERE id = %s",
            (dados["nome"], dados["uf"].upper(), id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM cidades WHERE id = %s", (id,))
        return cur.rowcount > 0
