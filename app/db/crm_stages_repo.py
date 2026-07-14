"""Repositório de etapas (stages) do CRM."""
from .connection import cursor


def listar_por_pipeline(pipeline_id: int):
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM crm_stages WHERE pipeline_id = %s ORDER BY ordem, id",
            (pipeline_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def listar_todas():
    with cursor() as cur:
        cur.execute(
            """SELECT s.*, p.nome AS pipeline_nome
                 FROM crm_stages s
                 JOIN crm_pipelines p ON p.id = s.pipeline_id
                 ORDER BY p.is_default DESC, p.nome, s.ordem, s.id"""
        )
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM crm_stages WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(dados: dict) -> int:
    with cursor() as cur:
        ordem = dados.get("ordem")
        if not ordem:  # None ou 0 -> anexa ao fim do funil (evita empates de ordem)
            cur.execute(
                "SELECT COALESCE(MAX(ordem), 0) + 1 AS prox FROM crm_stages WHERE pipeline_id = %s",
                (dados["pipeline_id"],),
            )
            ordem = cur.fetchone()["prox"]
        cur.execute(
            """INSERT INTO crm_stages
                   (pipeline_id, nome, ordem, probabilidade, cor, tipo,
                    sla_dias, auto_tarefa_assunto, auto_tarefa_descricao,
                    auto_tarefa_tipo, auto_tarefa_prazo_dias, auto_notificar)
               VALUES (%(pipeline_id)s, %(nome)s, %(ordem)s, %(probabilidade)s, %(cor)s, %(tipo)s,
                    %(sla_dias)s, %(auto_tarefa_assunto)s, %(auto_tarefa_descricao)s,
                    %(auto_tarefa_tipo)s, %(auto_tarefa_prazo_dias)s, %(auto_notificar)s)
               RETURNING id""",
            {
                "pipeline_id": dados["pipeline_id"],
                "nome": dados["nome"],
                "ordem": ordem,
                "probabilidade": dados.get("probabilidade", 0),
                "cor": dados.get("cor", "#065676"),
                "tipo": dados.get("tipo", "aberto"),
                "sla_dias": dados.get("sla_dias"),
                "auto_tarefa_assunto": dados.get("auto_tarefa_assunto") or None,
                "auto_tarefa_descricao": dados.get("auto_tarefa_descricao") or None,
                "auto_tarefa_tipo": dados.get("auto_tarefa_tipo") or "tarefa",
                "auto_tarefa_prazo_dias": dados.get("auto_tarefa_prazo_dias"),
                "auto_notificar": dados.get("auto_notificar", True),
            },
        )
        return cur.fetchone()["id"]


_CAMPOS_EDIT = (
    "nome", "ordem", "probabilidade", "cor", "tipo", "sla_dias",
    "auto_tarefa_assunto", "auto_tarefa_descricao", "auto_tarefa_tipo",
    "auto_tarefa_prazo_dias", "auto_notificar",
)


def atualizar(id: int, dados: dict) -> bool:
    """Update PARCIAL: grava só as colunas presentes em ``dados``."""
    campos = [c for c in _CAMPOS_EDIT if c in dados]
    if not campos:
        return False
    sets = ", ".join(f"{c} = %({c})s" for c in campos)
    params = {c: dados.get(c) for c in campos}
    params["id"] = id
    with cursor() as cur:
        cur.execute(f"UPDATE crm_stages SET {sets} WHERE id = %(id)s", params)
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM crm_stages WHERE id = %s", (id,))
        return cur.rowcount > 0


def reordenar(pipeline_id: int, ids_ordem: list):
    """Reordena stages de um pipeline. ids_ordem é uma lista de IDs na ordem desejada."""
    with cursor() as cur:
        for i, stage_id in enumerate(ids_ordem, start=1):
            cur.execute(
                "UPDATE crm_stages SET ordem = %s WHERE id = %s AND pipeline_id = %s",
                (i, stage_id, pipeline_id),
            )
