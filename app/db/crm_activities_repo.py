"""Repositório de atividades do CRM."""
from .connection import cursor

_SELECT_FULL = """
SELECT a.*,
       l.nome  AS lead_nome,
       o.nome  AS opportunity_nome,
       cl.nome AS cliente_nome,
       u.email AS proprietario_email,
       uc.email AS criado_por_email
  FROM crm_activities a
  LEFT JOIN crm_leads         l  ON l.id  = a.lead_id
  LEFT JOIN crm_opportunities o  ON o.id  = a.opportunity_id
  LEFT JOIN clientes          cl ON cl.id = a.cliente_id
  LEFT JOIN usuarios          u  ON u.id  = a.proprietario_id
  LEFT JOIN usuarios          uc ON uc.id = a.criado_por_id
"""

_CAMPOS = [
    "tipo", "assunto", "descricao", "data_atividade", "data_conclusao",
    "status", "prioridade", "lead_id", "opportunity_id", "cliente_id",
    "proprietario_id", "criado_por_id", "stage_id", "auto",
]


def listar(page: int = 1, per_page: int = 25, search: str = None, **filters):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (a.assunto ILIKE %s OR a.descricao ILIKE %s)"
        s = f"%{search}%"
        params += [s, s]

    for f in ("tipo", "status", "prioridade", "lead_id", "opportunity_id",
              "cliente_id", "proprietario_id"):
        v = filters.get(f)
        if v not in (None, ""):
            where += f" AND a.{f} = %s"
            params.append(v)

    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM crm_activities a {where}", params)
        total = cur.fetchone()["count"]
        cur.execute(
            f"{_SELECT_FULL} {where} ORDER BY COALESCE(a.data_atividade, a.created_at) DESC LIMIT %s OFFSET %s",
            params + [per_page, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]
    return rows, total


def timeline(entidade: str, entidade_id: int):
    """Retorna histórico de atividades de uma entidade (lead, opportunity, cliente)."""
    if entidade not in ("lead", "opportunity", "cliente"):
        raise ValueError("entidade inválida")
    col = {"lead": "lead_id", "opportunity": "opportunity_id", "cliente": "cliente_id"}[entidade]
    with cursor() as cur:
        cur.execute(
            f"{_SELECT_FULL} WHERE a.{col} = %s ORDER BY COALESCE(a.data_atividade, a.created_at) DESC",
            (entidade_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute(f"{_SELECT_FULL} WHERE a.id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    cols = ", ".join(_CAMPOS)
    placeholders = ", ".join(f"%({c})s" for c in _CAMPOS)
    params = {c: dados.get(c) for c in _CAMPOS}
    if not params.get("status"):
        params["status"] = "pendente"
    if not params.get("prioridade"):
        params["prioridade"] = "normal"
    with cursor() as cur:
        cur.execute(
            f"INSERT INTO crm_activities ({cols}) VALUES ({placeholders}) RETURNING id",
            params,
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    """Update PARCIAL: grava só as colunas presentes em ``dados``.

    Colunas de ``_CAMPOS`` ausentes do dict NÃO são tocadas — evita zerar
    vínculos polimórficos (lead_id/opportunity_id/cliente_id) e demais campos
    não reenviados. Nenhum dado é perdido por omissão.
    """
    campos = [c for c in _CAMPOS if c in dados]
    if not campos:
        return False
    sets = ", ".join(f"{c} = %({c})s" for c in campos)
    params = {c: dados.get(c) for c in campos}
    params["id"] = id
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            f"UPDATE crm_activities SET {sets}, updated_at = NOW() WHERE id = %(id)s",
            params,
        )
        return cur.rowcount > 0


def concluir(id: int):
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """UPDATE crm_activities
                  SET status = 'concluida', data_conclusao = NOW(), updated_at = NOW()
                WHERE id = %s""",
            (id,),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM crm_activities WHERE id = %s", (id,))
        return cur.rowcount > 0
