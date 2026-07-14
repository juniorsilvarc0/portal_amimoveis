"""Repositório da integração de WhatsApp (uazapi).

Single-tenant: existe NO MÁXIMO uma integração ativa (índice único parcial em
`chat_integracoes(provider) WHERE ativo`). O id é estável entre reconexões — é isso
que impede as conversas de duplicarem quando o usuário lê o QR de novo.
"""
import secrets

from .connection import cursor

PROVIDER = "uazapi"


def obter_ativa() -> dict | None:
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM chat_integracoes WHERE provider = %s AND ativo = TRUE LIMIT 1",
            (PROVIDER,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def obter(id: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM chat_integracoes WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar(api_url: str, token: str, criado_por_id: int | None = None) -> int:
    """Cria a integração ativa. O webhook_secret é gerado aqui e nunca sai da API."""
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_integracoes (provider, api_url, token, webhook_secret, criado_por_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (PROVIDER, api_url.rstrip("/"), token, secrets.token_hex(32), criado_por_id),
        )
        return cur.fetchone()["id"]


def atualizar_estado(id: int, conectado: bool, estado: str,
                     telefone_dono: str | None = None, erro: str | None = None) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE chat_integracoes
               SET conectado = %s,
                   estado = %s,
                   -- COALESCE: uma consulta de status que não devolve o owner não pode
                   -- APAGAR o telefone que já sabíamos.
                   telefone_dono = COALESCE(%s, telefone_dono),
                   ultimo_erro = %s,
                   updated_at = NOW()
             WHERE id = %s
            """,
            (conectado, estado, telefone_dono, erro, id),
        )
        return cur.rowcount > 0


def atualizar_webhook(id: int, webhook_url: str) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE chat_integracoes SET webhook_url = %s, updated_at = NOW() WHERE id = %s",
            (webhook_url, id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    """Remove a integração. O CASCADE leva conversas e mensagens; LEADS ficam intactos."""
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM chat_integracoes WHERE id = %s", (id,))
        return cur.rowcount > 0
