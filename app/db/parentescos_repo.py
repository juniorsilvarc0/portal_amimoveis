"""Repositório de Termos de Parentesco (declaração CAIXA)."""
from .connection import cursor

_SELECT_FULL = """
SELECT p.*,
       cl.nome           AS cliente_nome,
       cl.cpf            AS cliente_cpf,
       cl.estado_civil   AS cliente_estado_civil,
       cl.endereco       AS cliente_endereco,
       cl.bairro         AS cliente_bairro,
       cl.cep            AS cliente_cep,
       ci.nome           AS cliente_cidade_nome,
       ci.uf             AS cliente_cidade_uf
  FROM parentescos p
  JOIN clientes cl ON cl.id = p.cliente_id
  LEFT JOIN cidades ci ON ci.id = cl.cidade_id
"""


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (cl.nome ILIKE %s OR cl.cpf ILIKE %s OR p.parente_nome ILIKE %s OR p.parente_cpf ILIKE %s)"
        like = f"%{search}%"
        params += [like, like, like, like]

    cliente_id = filters.get("cliente_id")
    if cliente_id:
        where += " AND p.cliente_id = %s"
        params.append(cliente_id)

    count_sql = (
        "SELECT COUNT(*) FROM parentescos p "
        "JOIN clientes cl ON cl.id = p.cliente_id " + where
    )
    list_sql = f"{_SELECT_FULL} {where} ORDER BY p.created_at DESC LIMIT %s OFFSET %s"

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE p.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


_CAMPOS = [
    "cliente_id",
    "parente_nome",
    "parente_cpf",
    "parente_estado_civil",
    "grau_parentesco",
    "conjuge_parente_nome",
    "data_declaracao",
]


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    sql = f"INSERT INTO parentescos ({cols}) VALUES ({placeholders}) RETURNING id"
    params = {c: dados.get(c) for c in _CAMPOS}
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    sets = ", ".join(f"{c} = %({c})s" for c in _CAMPOS if c != "cliente_id")
    sql = f"UPDATE parentescos SET {sets}, updated_at = NOW() WHERE id = %(id)s"
    params = {c: dados.get(c) for c in _CAMPOS if c != "cliente_id"}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM parentescos WHERE id = %s", (id,))
        return cur.rowcount > 0
