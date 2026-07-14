"""Repositório de financiamentos com JOINs para nomes de FK."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (cl.nome ILIKE %s OR cl.cpf ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]

    cliente_id = filters.get("cliente_id")
    if cliente_id:
        where += " AND f.cliente_id = %s"
        params.append(cliente_id)

    analise = filters.get("analise")
    if analise:
        where += " AND f.analise = %s"
        params.append(analise)

    modalidade = filters.get("modalidade")
    if modalidade:
        where += " AND f.modalidade = %s"
        params.append(modalidade)

    count_sql = (
        f"SELECT COUNT(*) FROM financiamentos f "
        f"JOIN clientes cl ON cl.id = f.cliente_id {where}"
    )
    list_sql = (
        f"SELECT f.*, "
        f"cl.nome AS cliente_nome, cl.cpf AS cliente_cpf, "
        f"ci.nome AS cidade_nome, ci.uf AS cidade_uf, "
        f"g.nome AS gerente_nome, "
        f"p.nome AS parceiro_nome, p.tipo AS parceiro_tipo, "
        f"co.nome AS correspondente_nome "
        f"FROM financiamentos f "
        f"JOIN clientes cl ON cl.id = f.cliente_id "
        f"LEFT JOIN imoveis im ON im.id = f.imovel_id "
        f"LEFT JOIN cidades ci ON ci.id = im.cidade_id "
        f"LEFT JOIN gerentes g ON g.id = f.gerente_id "
        f"LEFT JOIN parceiros p ON p.id = f.parceiro_id "
        f"LEFT JOIN correspondentes co ON co.id = f.correspondente_id "
        f"{where} ORDER BY f.created_at DESC LIMIT %s OFFSET %s"
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
            SELECT f.*,
                cl.nome AS cliente_nome, cl.cpf AS cliente_cpf,
                im.nome AS imovel_nome,
                g.nome AS gerente_nome,
                p.nome AS parceiro_nome, p.tipo AS parceiro_tipo,
                co.nome AS correspondente_nome
            FROM financiamentos f
            JOIN clientes cl ON cl.id = f.cliente_id
            LEFT JOIN imoveis im ON im.id = f.imovel_id
            LEFT JOIN gerentes g ON g.id = f.gerente_id
            LEFT JOIN parceiros p ON p.id = f.parceiro_id
            LEFT JOIN correspondentes co ON co.id = f.correspondente_id
            WHERE f.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


_CAMPOS = [
    "cliente_id", "imovel_id", "gerente_id", "parceiro_id", "correspondente_id",
    "modalidade", "renda", "valor_financiamento", "analise", "observacoes",
]


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    sql = f"INSERT INTO financiamentos ({cols}) VALUES ({placeholders}) RETURNING id"
    params = {c: dados.get(c) for c in _CAMPOS}
    if "analise" not in dados or not dados.get("analise"):
        params["analise"] = "PENDENTE"
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    campos_upd = [c for c in _CAMPOS if c != "cliente_id"]
    sets = ", ".join(f"{c} = %({c})s" for c in campos_upd)
    sql = f"UPDATE financiamentos SET {sets}, updated_at = NOW() WHERE id = %(id)s"
    params = {c: dados.get(c) for c in campos_upd}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM financiamentos WHERE id = %s", (id,))
        return cur.rowcount > 0
