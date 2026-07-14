"""Repositório de gerentes de agências."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND g.nome ILIKE %s"
        params.append(f"%{search}%")

    agencia_id = filters.get("agencia_id")
    if agencia_id:
        where += " AND g.agencia_id = %s"
        params.append(agencia_id)

    count_sql = f"SELECT COUNT(*) FROM gerentes g {where}"
    list_sql = (
        f"SELECT g.*, a.nome AS agencia_nome "
        f"FROM gerentes g "
        f"LEFT JOIN agencias a ON a.id = g.agencia_id "
        f"{where} ORDER BY g.nome ASC LIMIT %s OFFSET %s"
    )

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(
            """
            SELECT g.*, a.nome AS agencia_nome
            FROM gerentes g
            LEFT JOIN agencias a ON a.id = g.agencia_id
            WHERE g.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO gerentes (nome, agencia_id) VALUES (%(nome)s, %(agencia_id)s) RETURNING id",
            {"nome": dados["nome"], "agencia_id": dados["agencia_id"]},
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE gerentes SET nome = %s, agencia_id = %s, updated_at = NOW() WHERE id = %s",
            (dados["nome"], dados["agencia_id"], id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM gerentes WHERE id = %s", (id,))
        return cur.rowcount > 0
