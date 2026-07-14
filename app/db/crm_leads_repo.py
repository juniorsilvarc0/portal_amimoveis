"""Repositório de leads do CRM.

Modelo: Cliente é central; Lead é um EVENTO de captação.
- Lead com CPF que já existe em Clientes → auto-vincula `cliente_id`
- Cliente pode ter múltiplos Leads (cada campanha que ele responde)
- Status `convertido` = primeira vez que virou cliente
- Status `reativado` = lead novo de cliente que já existia
"""
import re
from .connection import cursor


def _norm_cpf_cnpj(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def buscar_cliente_por_cpf(cpf_cnpj: str):
    """Retorna {id, nome, cpf} do cliente se já existir, senão None."""
    raw = _norm_cpf_cnpj(cpf_cnpj)
    if not raw or len(raw) < 11:
        return None
    with cursor() as cur:
        cur.execute(
            "SELECT id, nome, cpf FROM clientes WHERE cpf = %s AND cpf_pendente = false ORDER BY id DESC LIMIT 1",
            (raw,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

_SELECT_FULL = """
SELECT l.*,
       c.nome AS campaign_nome,
       ci.nome AS cidade_nome,
       ci.uf   AS cidade_uf,
       u.email AS proprietario_email,
       cl.nome AS cliente_nome,
       im.nome AS imovel_nome
  FROM crm_leads l
  LEFT JOIN crm_campaigns c ON c.id = l.campaign_id
  LEFT JOIN cidades ci      ON ci.id = l.cidade_id
  LEFT JOIN usuarios u      ON u.id = l.proprietario_id
  LEFT JOIN clientes cl     ON cl.id = l.cliente_id
  LEFT JOIN imoveis im      ON im.id = l.imovel_interesse_id
"""

_CAMPOS = [
    "nome", "email", "telefone", "whatsapp", "cpf_cnpj", "cidade_id",
    "origem", "campaign_id", "status", "score", "interesse",
    "imovel_interesse_id", "valor_estimado", "proprietario_id",
    "cliente_id", "observacoes", "data_conversao",
]


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (l.nome ILIKE %s OR l.email ILIKE %s OR l.telefone ILIKE %s OR l.whatsapp ILIKE %s)"
        s = f"%{search}%"
        params += [s, s, s, s]

    for f in ("status", "campaign_id", "proprietario_id", "origem"):
        v = filters.get(f)
        if v not in (None, ""):
            where += f" AND l.{f} = %s"
            params.append(v)

    with cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM crm_leads l {where}", params
        )
        total = cur.fetchone()["count"]
        cur.execute(
            f"{_SELECT_FULL} {where} ORDER BY l.created_at DESC LIMIT %s OFFSET %s",
            params + [per_page, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]
    return rows, total


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE l.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    """Cria lead. Se CPF/CNPJ corresponder a cliente existente, auto-vincula."""
    dados = dict(dados)
    # Normaliza CPF/CNPJ
    if dados.get("cpf_cnpj"):
        dados["cpf_cnpj"] = _norm_cpf_cnpj(dados["cpf_cnpj"])
    # Auto-link a cliente existente por CPF
    cliente_match = None
    if dados.get("cpf_cnpj") and not dados.get("cliente_id"):
        cliente_match = buscar_cliente_por_cpf(dados["cpf_cnpj"])
        if cliente_match:
            dados["cliente_id"] = cliente_match["id"]
            # Se já é cliente, status default é "reativado" (não "novo")
            if not dados.get("status") or dados.get("status") == "novo":
                dados["status"] = "reativado"

    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    params = {c: dados.get(c) for c in _CAMPOS}
    if not params.get("status"):
        params["status"] = "novo"
    with cursor() as cur:
        cur.execute(
            f"INSERT INTO crm_leads ({cols}) VALUES ({placeholders}) RETURNING id",
            params,
        )
        return cur.fetchone()["id"]


def listar_por_cliente(cliente_id: int):
    """Histórico de leads de um cliente, ordenado mais recente primeiro."""
    with cursor() as cur:
        cur.execute(
            f"{_SELECT_FULL} WHERE l.cliente_id = %s ORDER BY l.created_at DESC",
            (cliente_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def atualizar(id: int, dados: dict) -> bool:
    """Update PARCIAL: grava só as colunas presentes em ``dados``.

    Colunas de ``_CAMPOS`` ausentes do dict NÃO são tocadas — evita zerar
    ``cliente_id`` (auto-vinculado), ``data_conversao`` e outros campos que o
    formulário de edição não reenvia. Nenhum dado é perdido por omissão.
    """
    campos = [c for c in _CAMPOS if c in dados]
    if not campos:
        return False
    sets = ", ".join(f"{c} = %({c})s" for c in campos)
    params = {c: dados.get(c) for c in campos}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE crm_leads SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM crm_leads WHERE id = %s", (id,))
        return cur.rowcount > 0


def marcar_convertido(lead_id: int, cliente_id: int):
    """Marca um lead como convertido em cliente."""
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """UPDATE crm_leads
                  SET status = 'convertido',
                      cliente_id = %s,
                      data_conversao = NOW(),
                      updated_at = NOW()
                WHERE id = %s""",
            (cliente_id, lead_id),
        )
        return cur.rowcount > 0


def metricas():
    """Métricas agregadas para dashboard."""
    with cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'novo')         AS novos,
                COUNT(*) FILTER (WHERE status = 'contatado')    AS contatados,
                COUNT(*) FILTER (WHERE status = 'qualificado')  AS qualificados,
                COUNT(*) FILTER (WHERE status = 'convertido')   AS convertidos,
                COUNT(*) FILTER (WHERE status = 'descartado')   AS descartados,
                COUNT(*)                                        AS total
              FROM crm_leads
        """)
        return dict(cur.fetchone())


def upsert_por_telefone_whatsapp(telefone: str, nome: str | None) -> int | None:
    """Lead automático a partir de uma mensagem recebida no WhatsApp.

    O inbound do WhatsApp só traz NÚMERO — não traz CPF. Por isso a dedup aqui é por
    `telefone_normalizado` (coluna gerada), e não pelo `cpf_cnpj` usado no resto do repo.

    NÃO sobrescreve dado curado: se o lead já existe, só toca a recência. O nome que o
    time editou à mão, a etapa do funil e o proprietário ficam intactos — senão cada
    "oi" do cliente desfaria o trabalho de quem cuidou do lead.

    Devolve o id do lead, ou None se o telefone for curto demais para ser real.
    """
    norm = re.sub(r"\D", "", telefone or "")
    if len(norm) < 10:
        return None

    with cursor() as cur:
        # O Gunicorn roda 2 workers: duas mensagens do MESMO número chegando juntas
        # criariam dois leads (não há UNIQUE em telefone_normalizado — leads legados
        # podem ter telefone repetido). O advisory lock serializa por número; sendo
        # _xact_, ele é liberado sozinho no commit desta mesma transação.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"wa_lead:{norm}",))

        cur.execute(
            "SELECT id FROM crm_leads WHERE telefone_normalizado = %s "
            "ORDER BY id DESC LIMIT 1",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE crm_leads SET updated_at = NOW() WHERE id = %s", (row["id"],))
            return row["id"]

        # crm_leads.nome é NOT NULL: sem pushName, o próprio número vira o nome.
        cur.execute(
            "INSERT INTO crm_leads (nome, whatsapp, origem, status) "
            "VALUES (%s, %s, 'whatsapp', 'novo') RETURNING id",
            (nome or norm, norm),
        )
        return cur.fetchone()["id"]
