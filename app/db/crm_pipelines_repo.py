"""Repositório de pipelines de CRM."""
from .connection import cursor


def listar(ativo: bool = None):
    sql = "SELECT * FROM crm_pipelines"
    params = []
    if ativo is not None:
        sql += " WHERE ativo = %s"
        params.append(ativo)
    sql += " ORDER BY is_default DESC, nome"
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM crm_pipelines WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def obter_default():
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM crm_pipelines WHERE is_default = TRUE AND ativo = TRUE LIMIT 1"
        )
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        if dados.get("is_default"):
            cur.execute("UPDATE crm_pipelines SET is_default = FALSE")
        cur.execute(
            """INSERT INTO crm_pipelines (nome, descricao, is_default, ativo, tipo, pipeline_pos_venda_id)
               VALUES (%(nome)s, %(descricao)s, %(is_default)s, %(ativo)s, %(tipo)s, %(pipeline_pos_venda_id)s) RETURNING id""",
            {
                "nome": dados.get("nome"),
                "descricao": dados.get("descricao"),
                "is_default": bool(dados.get("is_default", False)),
                "ativo": bool(dados.get("ativo", True)),
                "tipo": dados.get("tipo") or "generico",
                "pipeline_pos_venda_id": dados.get("pipeline_pos_venda_id") or None,
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor() as cur:
        if dados.get("is_default"):
            cur.execute("UPDATE crm_pipelines SET is_default = FALSE WHERE id <> %s", (id,))
        cur.execute(
            """UPDATE crm_pipelines
                  SET nome = COALESCE(%(nome)s, nome),
                      descricao = %(descricao)s,
                      is_default = COALESCE(%(is_default)s, is_default),
                      ativo = COALESCE(%(ativo)s, ativo),
                      tipo = COALESCE(%(tipo)s, tipo),
                      pipeline_pos_venda_id = %(pipeline_pos_venda_id)s,
                      updated_at = NOW()
                WHERE id = %(id)s""",
            {
                "id": id,
                "nome": dados.get("nome"),
                "descricao": dados.get("descricao"),
                "is_default": dados.get("is_default"),
                "ativo": dados.get("ativo"),
                "tipo": dados.get("tipo"),
                "pipeline_pos_venda_id": dados.get("pipeline_pos_venda_id") if "pipeline_pos_venda_id" in dados else None,
            },
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM crm_pipelines WHERE id = %s", (id,))
        return cur.rowcount > 0
