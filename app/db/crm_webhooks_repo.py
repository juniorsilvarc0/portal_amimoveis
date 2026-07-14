"""Repositório de webhooks de saída do CRM."""
import json
from .connection import cursor


def listar():
    with cursor() as cur:
        cur.execute("SELECT * FROM crm_webhooks ORDER BY created_at DESC")
        return [dict(r) for r in cur.fetchall()]


def obter(id: int):
    with cursor() as cur:
        cur.execute("SELECT * FROM crm_webhooks WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def listar_ativos_por_evento(evento: str):
    """Retorna webhooks ativos que escutam um evento específico."""
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM crm_webhooks WHERE ativo = TRUE AND eventos ILIKE %s",
            (f"%{evento}%",),
        )
        rows = [dict(r) for r in cur.fetchall()]
        # filtro fino (evita substring de outro evento)
        result = []
        for r in rows:
            eventos = [e.strip() for e in (r.get("eventos") or "").split(",")]
            if evento in eventos or "*" in eventos:
                result.append(r)
        return result


def criar(dados: dict) -> int:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO crm_webhooks (nome, url, eventos, secret, ativo)
               VALUES (%(nome)s, %(url)s, %(eventos)s, %(secret)s, %(ativo)s) RETURNING id""",
            {
                "nome": dados["nome"],
                "url": dados["url"],
                "eventos": dados["eventos"],
                "secret": dados.get("secret"),
                "ativo": bool(dados.get("ativo", True)),
            },
        )
        return cur.fetchone()["id"]


def atualizar(id: int, dados: dict) -> bool:
    with cursor() as cur:
        cur.execute(
            """UPDATE crm_webhooks
                  SET nome = COALESCE(%(nome)s, nome),
                      url = COALESCE(%(url)s, url),
                      eventos = COALESCE(%(eventos)s, eventos),
                      secret = %(secret)s,
                      ativo = COALESCE(%(ativo)s, ativo),
                      updated_at = NOW()
                WHERE id = %(id)s""",
            {
                "id": id,
                "nome": dados.get("nome"),
                "url": dados.get("url"),
                "eventos": dados.get("eventos"),
                "secret": dados.get("secret"),
                "ativo": dados.get("ativo"),
            },
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM crm_webhooks WHERE id = %s", (id,))
        return cur.rowcount > 0


def registrar_log(webhook_id: int, evento: str, payload: dict,
                  status_code: int = None, response_body: str = None, erro: str = None):
    with cursor() as cur:
        cur.execute(
            """INSERT INTO crm_webhook_logs
                 (webhook_id, evento, payload, status_code, response_body, erro)
               VALUES (%s, %s, %s::jsonb, %s, %s, %s)""",
            (webhook_id, evento, json.dumps(payload, default=str),
             status_code, response_body, erro),
        )


def listar_logs(webhook_id: int = None, limit: int = 100):
    sql = "SELECT * FROM crm_webhook_logs"
    params = []
    if webhook_id:
        sql += " WHERE webhook_id = %s"
        params.append(webhook_id)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
