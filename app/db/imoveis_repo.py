"""Repositório de imóveis/empreendimentos."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND i.nome ILIKE %s"
        params.append(f"%{search}%")

    cidade_id = filters.get("cidade_id")
    if cidade_id:
        where += " AND i.cidade_id = %s"
        params.append(cidade_id)

    construtora_id = filters.get("construtora_id")
    if construtora_id:
        where += " AND i.construtora_id = %s"
        params.append(construtora_id)

    count_sql = f"SELECT COUNT(*) FROM imoveis i {where}"
    list_sql = (
        f"SELECT i.*, c.nome AS cidade_nome, c.uf AS cidade_uf, "
        f"p.nome AS construtora_nome "
        f"FROM imoveis i "
        f"LEFT JOIN cidades c ON c.id = i.cidade_id "
        f"LEFT JOIN parceiros p ON p.id = i.construtora_id "
        f"{where} ORDER BY i.nome ASC LIMIT %s OFFSET %s"
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
            SELECT i.*, c.nome AS cidade_nome, c.uf AS cidade_uf,
                   p.nome AS construtora_nome
            FROM imoveis i
            LEFT JOIN cidades c ON c.id = i.cidade_id
            LEFT JOIN parceiros p ON p.id = i.construtora_id
            WHERE i.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO imoveis (nome, construtora_id, cidade_id)
            VALUES (%(nome)s, %(construtora_id)s, %(cidade_id)s)
            RETURNING id
            """,
            {
                "nome": dados["nome"],
                "construtora_id": dados.get("construtora_id"),
                "cidade_id": dados["cidade_id"],
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE imoveis SET
                nome = %s, construtora_id = %s, cidade_id = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (dados["nome"], dados.get("construtora_id"), dados["cidade_id"], id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM imoveis WHERE id = %s", (id,))
        return cur.rowcount > 0
