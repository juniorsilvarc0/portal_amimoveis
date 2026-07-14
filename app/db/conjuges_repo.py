"""Repositório de cônjuges (1:1 com clientes)."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND cj.nome ILIKE %s"
        params.append(f"%{search}%")

    cliente_id = filters.get("cliente_id")
    if cliente_id:
        where += " AND cj.cliente_id = %s"
        params.append(cliente_id)

    count_sql = f"SELECT COUNT(*) FROM conjuges cj {where}"
    list_sql = (
        f"SELECT cj.*, cl.nome AS cliente_nome FROM conjuges cj "
        f"LEFT JOIN clientes cl ON cl.id = cj.cliente_id "
        f"{where} ORDER BY cj.id DESC LIMIT %s OFFSET %s"
    )

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM conjuges WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO conjuges (
                cliente_id, nome, cpf, rg, rg_orgao, nascimento,
                nacionalidade, estado_civil, profissao, email, whatsapp, fixo
            ) VALUES (
                %(cliente_id)s, %(nome)s, %(cpf)s, %(rg)s, %(rg_orgao)s, %(nascimento)s,
                %(nacionalidade)s, %(estado_civil)s, %(profissao)s,
                %(email)s, %(whatsapp)s, %(fixo)s
            ) RETURNING id
            """,
            {
                "cliente_id": dados["cliente_id"],
                "nome": dados["nome"],
                "cpf": dados.get("cpf"),
                "rg": dados.get("rg"),
                "rg_orgao": dados.get("rg_orgao"),
                "nascimento": dados.get("nascimento"),
                "nacionalidade": dados.get("nacionalidade"),
                "estado_civil": dados.get("estado_civil"),
                "profissao": dados.get("profissao"),
                "email": dados.get("email"),
                "whatsapp": dados.get("whatsapp"),
                "fixo": dados.get("fixo"),
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE conjuges SET
                nome = %(nome)s, cpf = %(cpf)s, rg = %(rg)s, rg_orgao = %(rg_orgao)s,
                nascimento = %(nascimento)s, nacionalidade = %(nacionalidade)s,
                estado_civil = %(estado_civil)s, profissao = %(profissao)s,
                email = %(email)s, whatsapp = %(whatsapp)s, fixo = %(fixo)s,
                updated_at = NOW()
            WHERE id = %(id)s
            """,
            {
                "nome": dados["nome"],
                "cpf": dados.get("cpf"),
                "rg": dados.get("rg"),
                "rg_orgao": dados.get("rg_orgao"),
                "nascimento": dados.get("nascimento"),
                "nacionalidade": dados.get("nacionalidade"),
                "estado_civil": dados.get("estado_civil"),
                "profissao": dados.get("profissao"),
                "email": dados.get("email"),
                "whatsapp": dados.get("whatsapp"),
                "fixo": dados.get("fixo"),
                "id": id,
            },
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM conjuges WHERE id = %s", (id,))
        return cur.rowcount > 0


def upsert_por_cliente(cliente_id: int, dados: dict) -> int:
    """Cria ou substitui cônjuge para um dado cliente_id. Retorna id."""
    dados = dict(dados)
    dados["cliente_id"] = cliente_id

    with cursor() as cur:
        cur.execute(
            "SELECT id FROM conjuges WHERE cliente_id = %s",
            (cliente_id,),
        )
        row = cur.fetchone()

    if row:
        atualizar(row["id"], dados)
        return row["id"]
    else:
        return criar(dados)
