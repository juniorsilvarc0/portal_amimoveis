"""Repositório de clientes com suporte a CPF pendente e cônjuge aninhado."""
import re
from .connection import cursor


def _norm_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


_SELECT_FULL = """
    SELECT c.*,
           ci.nome  AS cidade_nome,
           ci.uf    AS cidade_uf,
           up.email AS proprietario_email,
           ucr.email AS criado_por_email,
           umd.email AS modificado_por_email
      FROM clientes c
      LEFT JOIN cidades ci  ON ci.id = c.cidade_id
      LEFT JOIN usuarios up ON up.id = c.proprietario_id
      LEFT JOIN usuarios ucr ON ucr.id = c.criado_por_id
      LEFT JOIN usuarios umd ON umd.id = c.modificado_por_id
"""


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (c.nome ILIKE %s OR c.cpf ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]

    cidade_id = filters.get("cidade_id")
    if cidade_id:
        where += " AND c.cidade_id = %s"
        params.append(cidade_id)

    count_sql = f"SELECT COUNT(*) FROM clientes c {where}"
    list_sql = f"{_SELECT_FULL} {where} ORDER BY c.created_at DESC LIMIT %s OFFSET %s"

    with cursor() as cur:
        cur.execute(count_sql, params)
        total = cur.fetchone()["count"]
        cur.execute(list_sql, params + [per_page, offset])
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE c.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def obter_por_cpf(cpf: str):
    """Retorna cliente + cônjuge (aninhado em 'conjuge') ou None."""
    cpf = _norm_cpf(cpf)
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE c.cpf = %s ORDER BY c.id DESC LIMIT 1", (cpf,))
        row = cur.fetchone()
        if not row:
            return None
        cliente = dict(row)

        cur.execute(
            "SELECT * FROM conjuges WHERE cliente_id = %s",
            (cliente["id"],),
        )
        conj = cur.fetchone()
        cliente["conjuge"] = dict(conj) if conj else None

    return cliente


_ALLOWED_FIELDS = [
    # Core
    "cpf", "cpf_pendente", "nome", "rg", "rg_orgao", "nascimento",
    "nacionalidade", "estado_civil", "regime_bens", "profissao",
    "email", "telefone_fixo", "whatsapp1", "whatsapp2",
    "endereco", "bairro", "cep", "cidade_id", "observacoes",
    # Expansão Salesforce-like
    "sexo", "ativo", "tipo_pessoa", "naturalidade", "escolaridade",
    "nome_mae", "nome_pai", "numero_pis", "titulo_eleitor",
    "categoria", "codigo_sap", "codigo_crm", "cargo",
    "proprietario_id", "criado_por_id", "modificado_por_id",
]


def criar(dados: dict) -> int:
    dados = dict(dados)
    dados["cpf"] = _norm_cpf(dados.get("cpf", ""))
    # Default ativo=True se ausente
    if "ativo" not in dados:
        dados["ativo"] = True
    cols = [f for f in _ALLOWED_FIELDS if f in dados or f in ("cpf", "cpf_pendente", "nome", "ativo")]
    # Garante cpf_pendente NÃO-NULO. Checar presença da chave não basta: ClienteCreate a declara
    # como Optional[bool] = None, então model_dump() sempre a inclui — valendo None quando o
    # cliente da API a omite. O INSERT nomeia a coluna, e aí o DEFAULT false do schema não se
    # aplica (default só vale para coluna omitida), estourando o NOT NULL.
    if dados.get("cpf_pendente") is None:
        dados["cpf_pendente"] = False
    params = {c: dados.get(c) for c in cols}
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f"%({c})s" for c in cols)
    with cursor() as cur:
        cur.execute(
            f"INSERT INTO clientes ({col_sql}) VALUES ({val_sql}) RETURNING id",
            params,
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    """Update PARCIAL: só atualiza colunas presentes no dict `dados`.

    Importante: NÃO nulifica campos ausentes. Valores explicitamente None
    são aceitos (o caller pode zerar um campo passando None). Campos que
    não aparecem em `dados` ficam intocados.
    """
    dados = dict(dados)
    if "cpf" in dados and dados.get("cpf"):
        dados["cpf"] = _norm_cpf(dados["cpf"])

    # Só inclui no SET os campos que vieram no dict
    campos_presentes = [f for f in _ALLOWED_FIELDS if f in dados]
    if not campos_presentes:
        return False

    sets = ", ".join(f"{c} = %({c})s" for c in campos_presentes)
    params = {c: dados.get(c) for c in campos_presentes}
    params["id"] = id

    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE clientes SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM clientes WHERE id = %s", (id,))
        return cur.rowcount > 0


def upsert_por_cpf(dados: dict) -> int:
    """Cria cliente se CPF não existir, atualiza se existir. Retorna id."""
    dados = dict(dados)
    dados["cpf"] = _norm_cpf(dados.get("cpf", ""))

    with cursor() as cur:
        cur.execute(
            "SELECT id FROM clientes WHERE cpf = %s ORDER BY id DESC LIMIT 1",
            (dados["cpf"],),
        )
        row = cur.fetchone()

    if row:
        atualizar(row["id"], dados)
        return row["id"]
    else:
        return criar(dados)
