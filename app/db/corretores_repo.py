"""Repositório de corretores."""
import re
from .connection import cursor

_ALLOWED = [
    "nome", "cpf", "nascimento", "telefone", "email", "creci", "cidade_id",
    "tamanho_camisa", "chocolate_preferido", "bebida_preferida",
]


def _norm_cpf(cpf):
    return re.sub(r"\D", "", cpf or "") or None


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (co.nome ILIKE %s OR co.cpf ILIKE %s OR co.creci ILIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    cidade_id = filters.get("cidade_id")
    if cidade_id:
        where += " AND co.cidade_id = %s"
        params.append(cidade_id)

    count_sql = f"SELECT COUNT(*) FROM corretores co {where}"
    list_sql = (
        f"SELECT co.*, c.nome AS cidade_nome, c.uf AS cidade_uf "
        f"FROM corretores co "
        f"LEFT JOIN cidades c ON c.id = co.cidade_id "
        f"{where} ORDER BY co.nome ASC LIMIT %s OFFSET %s"
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
            SELECT co.*, c.nome AS cidade_nome, c.uf AS cidade_uf
            FROM corretores co
            LEFT JOIN cidades c ON c.id = co.cidade_id
            WHERE co.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    dados = dict(dados)
    if "cpf" in dados:
        dados["cpf"] = _norm_cpf(dados.get("cpf"))

    cols = [c for c in _ALLOWED if c in dados]
    placeholders = ", ".join(f"%({c})s" for c in cols)
    sql = f"INSERT INTO corretores ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id"
    params = {c: dados.get(c) for c in cols}

    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    """Update parcial — só atualiza campos presentes."""
    dados = dict(dados)
    if "cpf" in dados:
        dados["cpf"] = _norm_cpf(dados.get("cpf"))

    campos_presentes = [f for f in _ALLOWED if f in dados]
    if not campos_presentes:
        return False

    sets = ", ".join(f"{c} = %({c})s" for c in campos_presentes)
    params = {c: dados.get(c) for c in campos_presentes}
    params["id"] = id

    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE corretores SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM corretores WHERE id = %s", (id,))
        return cur.rowcount > 0
