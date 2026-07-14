"""Repositório de parceiros (construtoras, imobiliárias, autônomos)."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND p.nome ILIKE %s"
        params.append(f"%{search}%")

    tipo = filters.get("tipo")
    if tipo:
        where += " AND p.tipo = %s"
        params.append(tipo)

    cidade_id = filters.get("cidade_id")
    if cidade_id:
        where += " AND p.cidade_id = %s"
        params.append(cidade_id)

    count_sql = f"SELECT COUNT(*) FROM parceiros p {where}"
    list_sql = (
        f"SELECT p.*, c.nome AS cidade_nome, c.uf AS cidade_uf "
        f"FROM parceiros p "
        f"LEFT JOIN cidades c ON c.id = p.cidade_id "
        f"{where} ORDER BY p.nome ASC LIMIT %s OFFSET %s"
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
            SELECT p.*, c.nome AS cidade_nome, c.uf AS cidade_uf
            FROM parceiros p
            LEFT JOIN cidades c ON c.id = p.cidade_id
            WHERE p.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO parceiros (nome, tipo, cidade_id)
            VALUES (%(nome)s, %(tipo)s, %(cidade_id)s)
            RETURNING id
            """,
            {
                "nome": dados["nome"],
                "tipo": dados["tipo"],
                "cidade_id": dados["cidade_id"],
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE parceiros SET
                nome = %s, tipo = %s, cidade_id = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (dados["nome"], dados["tipo"], dados["cidade_id"], id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM parceiros WHERE id = %s", (id,))
        return cur.rowcount > 0
