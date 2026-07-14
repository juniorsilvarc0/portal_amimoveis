"""Repositório de propostas v2 com pagamentos aninhados."""
from .connection import cursor, conn


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (cl.nome ILIKE %s OR cl.cpf ILIKE %s OR p.empreendimento ILIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    cliente_id = filters.get("cliente_id")
    if cliente_id:
        where += " AND p.cliente_id = %s"
        params.append(cliente_id)

    count_sql = f"SELECT COUNT(*) FROM propostas p JOIN clientes cl ON cl.id = p.cliente_id {where}"
    list_sql = (
        f"SELECT p.id, p.created_at, p.updated_at, p.empreendimento, p.unidade, "
        f"p.valor_total, p.validade, p.imovel_id, p.corretor_id, "
        f"COALESCE(im.nome, p.empreendimento) AS imovel_nome, "
        f"COALESCE(co.nome, p.corretor_nome) AS corretor_nome, "
        f"COALESCE(co.creci, p.corretor_creci) AS corretor_creci, "
        f"cl.nome AS cliente_nome, cl.cpf AS cliente_cpf "
        f"FROM propostas p "
        f"JOIN clientes cl ON cl.id = p.cliente_id "
        f"LEFT JOIN imoveis im ON im.id = p.imovel_id "
        f"LEFT JOIN corretores co ON co.id = p.corretor_id "
        f"{where} ORDER BY p.created_at DESC LIMIT %s OFFSET %s"
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
            SELECT p.*,
                   cl.nome AS cliente_nome,
                   cl.cpf AS cliente_cpf,
                   cl.nacionalidade  AS cliente_nacionalidade,
                   cl.estado_civil   AS cliente_estado_civil,
                   cl.regime_bens    AS cliente_regime_bens,
                   cl.nascimento     AS cliente_nascimento,
                   cl.profissao      AS cliente_profissao,
                   cl.rg             AS cliente_rg,
                   cl.rg_orgao       AS cliente_rg_orgao,
                   cl.endereco       AS cliente_endereco,
                   cl.bairro         AS cliente_bairro,
                   cl.cep            AS cliente_cep,
                   cl.telefone_fixo  AS cliente_telefone_fixo,
                   cl.whatsapp1      AS cliente_whatsapp1,
                   cl.whatsapp2      AS cliente_whatsapp2,
                   cl.email          AS cliente_email,
                   ci.nome           AS cliente_cidade_nome,
                   ci.uf             AS cliente_cidade_uf,
                   cj.nome           AS conjuge_nome,
                   cj.cpf            AS conjuge_cpf,
                   cj.nacionalidade  AS conjuge_nacionalidade,
                   cj.estado_civil   AS conjuge_estado_civil,
                   cj.nascimento     AS conjuge_nascimento,
                   cj.profissao      AS conjuge_profissao,
                   cj.rg             AS conjuge_rg,
                   cj.rg_orgao       AS conjuge_rg_orgao,
                   cj.email          AS conjuge_email,
                   cj.whatsapp       AS conjuge_whatsapp,
                   cj.fixo           AS conjuge_fixo,
                   im.nome           AS imovel_nome,
                   COALESCE(co.nome,  p.corretor_nome)  AS corretor_nome,
                   COALESCE(co.creci, p.corretor_creci) AS corretor_creci
            FROM propostas p
            JOIN clientes cl        ON cl.id = p.cliente_id
            LEFT JOIN cidades ci    ON ci.id = cl.cidade_id
            LEFT JOIN conjuges cj   ON cj.cliente_id = cl.id
            LEFT JOIN imoveis im    ON im.id = p.imovel_id
            LEFT JOIN corretores co ON co.id = p.corretor_id
            WHERE p.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def obter_com_pagamentos(id: int):
    """Retorna proposta + lista de pagamentos ordenados por `ordem`."""
    proposta = obter(id)
    if not proposta:
        return None

    with cursor() as cur:
        cur.execute(
            "SELECT * FROM proposta_pagamentos WHERE proposta_id = %s ORDER BY ordem",
            (id,),
        )
        proposta["pagamentos"] = [dict(r) for r in cur.fetchall()]

    return proposta


_CAMPOS_PROPOSTA = [
    "cliente_id", "imovel_id", "corretor_id",
    "empreendimento", "unidade", "valor_total",
    "observacoes", "validade", "corretor_nome", "corretor_creci",
    "data_dia", "data_mes", "data_ano",
]

_CAMPOS_PAGAMENTO = [
    "proposta_id", "ordem", "descricao", "quantidade",
    "valor_parcela", "valor_total", "forma", "vencimento",
]


def _inserir_pagamentos(cur, proposta_id: int, pagamentos: list[dict]):
    for pag in pagamentos:
        pag = dict(pag)
        pag["proposta_id"] = proposta_id
        cols = ", ".join(_CAMPOS_PAGAMENTO)
        placeholders = ", ".join(f"%({c})s" for c in _CAMPOS_PAGAMENTO)
        cur.execute(
            f"INSERT INTO proposta_pagamentos ({cols}) VALUES ({placeholders})",
            {c: pag.get(c) for c in _CAMPOS_PAGAMENTO},
        )


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS_PROPOSTA)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS_PROPOSTA)
    sql = f"INSERT INTO propostas ({cols}) VALUES ({placeholders}) RETURNING id"
    with cursor() as cur:
        cur.execute(sql, {c: dados.get(c) for c in _CAMPOS_PROPOSTA})
        return cur.fetchone()["id"]


def criar_com_pagamentos(dados: dict, pagamentos: list[dict]) -> int:
    """Cria proposta + pagamentos em uma única transação."""
    cols = ", ".join(_CAMPOS_PROPOSTA)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS_PROPOSTA)
    sql = f"INSERT INTO propostas ({cols}) VALUES ({placeholders}) RETURNING id"

    with conn() as c:
        with c.cursor(cursor_factory=__import__("psycopg2.extras", fromlist=["RealDictCursor"]).RealDictCursor) as cur:
            cur.execute(sql, {c_: dados.get(c_) for c_ in _CAMPOS_PROPOSTA})
            proposta_id = cur.fetchone()["id"]
            _inserir_pagamentos(cur, proposta_id, pagamentos)

    return proposta_id


def atualizar(id: int, dados: dict) -> bool:
    sets = ", ".join(f"{c} = %({c})s" for c in _CAMPOS_PROPOSTA if c != "cliente_id")
    sql = f"UPDATE propostas SET {sets}, updated_at = NOW() WHERE id = %(id)s"
    params = {c: dados.get(c) for c in _CAMPOS_PROPOSTA if c != "cliente_id"}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


def atualizar_com_pagamentos(id: int, dados: dict, pagamentos: list[dict]) -> bool:
    """Atualiza proposta e substitui todos os pagamentos (replace-all)."""
    sets = ", ".join(f"{c} = %({c})s" for c in _CAMPOS_PROPOSTA if c != "cliente_id")
    sql_upd = f"UPDATE propostas SET {sets}, updated_at = NOW() WHERE id = %(id)s"
    params = {c: dados.get(c) for c in _CAMPOS_PROPOSTA if c != "cliente_id"}
    params["id"] = id

    import psycopg2.extras

    with conn() as c:
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_upd, params)
            updated = cur.rowcount > 0
            if updated:
                cur.execute("DELETE FROM proposta_pagamentos WHERE proposta_id = %s", (id,))
                _inserir_pagamentos(cur, id, pagamentos)

    return updated


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM propostas WHERE id = %s", (id,))
        return cur.rowcount > 0
