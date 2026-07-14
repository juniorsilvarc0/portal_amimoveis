"""Repositório de agências bancárias."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND a.nome ILIKE %s"
        params.append(f"%{search}%")

    cidade_id = filters.get("cidade_id")
    if cidade_id:
        where += " AND a.cidade_id = %s"
        params.append(cidade_id)

    count_sql = f"SELECT COUNT(*) FROM agencias a {where}"
    list_sql = (
        f"SELECT a.*, c.nome AS cidade_nome, c.uf AS cidade_uf "
        f"FROM agencias a "
        f"LEFT JOIN cidades c ON c.id = a.cidade_id "
        f"{where} ORDER BY a.nome ASC LIMIT %s OFFSET %s"
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
            SELECT a.*, c.nome AS cidade_nome, c.uf AS cidade_uf
            FROM agencias a
            LEFT JOIN cidades c ON c.id = a.cidade_id
            WHERE a.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO agencias (nome, bairro, numero, cidade_id)
            VALUES (%(nome)s, %(bairro)s, %(numero)s, %(cidade_id)s)
            RETURNING id
            """,
            {
                "nome": dados["nome"],
                "bairro": dados.get("bairro"),
                "numero": dados.get("numero"),
                "cidade_id": dados["cidade_id"],
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE agencias SET
                nome = %(nome)s, bairro = %(bairro)s,
                numero = %(numero)s, cidade_id = %(cidade_id)s,
                updated_at = NOW()
            WHERE id = %(id)s
            """,
            {
                "nome": dados["nome"],
                "bairro": dados.get("bairro"),
                "numero": dados.get("numero"),
                "cidade_id": dados["cidade_id"],
                "id": id,
            },
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM agencias WHERE id = %s", (id,))
        return cur.rowcount > 0
