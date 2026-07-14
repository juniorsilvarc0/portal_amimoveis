"""Repositório de fichas habitacionais v2 (habitacao_fichas)."""
from .connection import cursor

# SELECT completo com todos os campos que o PDF service precisa.
# h.construtora_nome tem o texto livre (migrado do legado); quando houver
# construtora_id, preferimos o nome do parceiro.
_SELECT_FULL = """
SELECT h.*,
       cl.nome                AS cliente_nome,
       cl.cpf                 AS cliente_cpf,
       cl.email               AS cliente_email,
       cl.whatsapp1           AS cliente_whatsapp1,
       cl.whatsapp2           AS cliente_whatsapp2,
       cl.telefone_fixo       AS cliente_telefone_fixo,
       cl.nacionalidade       AS cliente_nacionalidade,
       cl.estado_civil        AS cliente_estado_civil,
       cl.regime_bens         AS cliente_regime_bens,
       cl.nascimento          AS cliente_nascimento,
       cl.profissao           AS cliente_profissao,
       cl.rg                  AS cliente_rg,
       cl.rg_orgao            AS cliente_rg_orgao,
       cl.endereco            AS cliente_endereco,
       cl.bairro              AS cliente_bairro,
       cl.cep                 AS cliente_cep,
       ci.nome                AS cliente_cidade_nome,
       ci.uf                  AS cliente_cidade_uf,
       COALESCE(p.nome, h.construtora_nome) AS construtora_nome
  FROM habitacao_fichas h
  JOIN clientes  cl ON cl.id = h.cliente_id
  LEFT JOIN cidades  ci ON ci.id = cl.cidade_id
  LEFT JOIN parceiros p  ON p.id = h.construtora_id
"""


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (cl.nome ILIKE %s OR cl.cpf ILIKE %s OR h.empreendimento ILIKE %s)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]

    cliente_id = filters.get("cliente_id")
    if cliente_id:
        where += " AND h.cliente_id = %s"
        params.append(cliente_id)

    empreendimento = filters.get("empreendimento")
    if empreendimento:
        where += " AND h.empreendimento ILIKE %s"
        params.append(f"%{empreendimento}%")

    count_sql = (
        "SELECT COUNT(*) FROM habitacao_fichas h "
        "JOIN clientes cl ON cl.id = h.cliente_id " + where
    )
    list_sql = f"{_SELECT_FULL} {where} ORDER BY h.created_at DESC LIMIT %s OFFSET %s"

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE h.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


_CAMPOS = [
    "cliente_id", "empreendimento", "imovel_id", "idade_snapshot", "dependentes",
    "coobrigado_nome",
    "titular_funcao", "titular_empresa", "titular_admissao",
    "titular_renda_bruta", "titular_renda_liquida", "titular_extras",
    "conjuge_nome", "conjuge_cpf",
    "conjuge_funcao", "conjuge_empresa", "conjuge_admissao",
    "conjuge_renda_bruta", "conjuge_renda_liquida", "conjuge_extras",
    "emprestimos", "moradia_tipo", "transportes",
    "conta", "conta_salario", "open_finance", "opt_in",
    "biometria", "cartao_credito", "crot",
    "valor_total", "subsidio", "entrada", "negociacao",
    "financiado", "parcela", "prazo", "amortizacao", "utilizar_fgts",
    "endereco_imovel", "proprietarios", "construtora_id", "construtora_nome",
    "proprietarios_construtora", "taxa_vista_contrato", "seguridade",
]


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    sql = f"INSERT INTO habitacao_fichas ({cols}) VALUES ({placeholders}) RETURNING id"
    params = {c: dados.get(c) for c in _CAMPOS}
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    sets = ", ".join(f"{c} = %({c})s" for c in _CAMPOS if c != "cliente_id")
    sql = f"UPDATE habitacao_fichas SET {sets}, updated_at = NOW() WHERE id = %(id)s"
    params = {c: dados.get(c) for c in _CAMPOS if c != "cliente_id"}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(sql, params)
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM habitacao_fichas WHERE id = %s", (id,))
        return cur.rowcount > 0
