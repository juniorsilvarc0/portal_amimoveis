"""Repositório de conversas de WhatsApp."""
from .connection import cursor


def listar(page: int = 1, per_page: int = 50, search: str = None, status: str = None):
    offset = (page - 1) * per_page
    where = "WHERE 1=1"
    params: list = []

    if search:
        where += " AND (c.contato_nome ILIKE %s OR c.contato_telefone ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]
    if status:
        where += " AND c.status = %s"
        params.append(status)

    with cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM chat_conversas c {where}", params)
        total = cur.fetchone()["count"]
        cur.execute(
            f"""
            SELECT c.*, l.nome AS lead_nome
              FROM chat_conversas c
              LEFT JOIN crm_leads l ON l.id = c.lead_id
              {where}
             ORDER BY c.ultima_mensagem_em DESC NULLS LAST, c.id DESC
             LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def obter(id: int) -> dict | None:
    with cursor() as cur:
        cur.execute(
            """
            SELECT c.*, l.nome AS lead_nome
              FROM chat_conversas c
              LEFT JOIN crm_leads l ON l.id = c.lead_id
             WHERE c.id = %s
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def upsert(integracao_id: int, dados: dict, incremento_nao_lidas: int = 0) -> dict:
    """Cria ou atualiza a conversa do contato, e devolve id/status/lead_id.

    Duas sutilezas que, se erradas, corrompem dados:

    1. COALESCE em contato_nome/avatar/chat_jid: o echo `fromMe` chega SEM nome de
       contato (lá o senderName é o dono). Um UPDATE cru gravaria NULL por cima do nome
       que já tínhamos, e o contato "perderia o nome" toda vez que respondêssemos.

    2. nao_lidas é incrementado com `+ %s` no próprio SQL, não lido-e-escrito na app:
       o Gunicorn roda 2 workers, e dois webhooks simultâneos com read-modify-write
       perderiam uma contagem.
    """
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_conversas (
                integracao_id, external_id, chat_jid, contato_nome, contato_telefone,
                contato_avatar_url, nao_lidas, ultima_mensagem_em, ultima_mensagem_previa
            ) VALUES (
                %(integracao_id)s, %(external_id)s, %(chat_jid)s, %(contato_nome)s,
                %(contato_telefone)s, %(contato_avatar_url)s, %(incremento)s,
                %(mensagem_em)s, %(previa)s
            )
            ON CONFLICT (integracao_id, external_id) DO UPDATE SET
                contato_nome       = COALESCE(EXCLUDED.contato_nome, chat_conversas.contato_nome),
                contato_avatar_url = COALESCE(EXCLUDED.contato_avatar_url, chat_conversas.contato_avatar_url),
                chat_jid           = COALESCE(EXCLUDED.chat_jid, chat_conversas.chat_jid),
                ultima_mensagem_em = GREATEST(
                    COALESCE(chat_conversas.ultima_mensagem_em, EXCLUDED.ultima_mensagem_em),
                    EXCLUDED.ultima_mensagem_em
                ),
                ultima_mensagem_previa = EXCLUDED.ultima_mensagem_previa,
                nao_lidas  = chat_conversas.nao_lidas + %(incremento)s,
                updated_at = NOW()
            RETURNING id, status, lead_id, nao_lidas
            """,
            {
                "integracao_id": integracao_id,
                "external_id": dados["contato_telefone"],
                "chat_jid": dados.get("chat_jid"),
                "contato_nome": dados.get("contato_nome"),
                "contato_telefone": dados["contato_telefone"],
                "contato_avatar_url": dados.get("contato_avatar_url"),
                "incremento": incremento_nao_lidas,
                "mensagem_em": dados.get("mensagem_em"),
                "previa": (dados.get("conteudo") or "")[:200] or None,
            },
        )
        return dict(cur.fetchone())


def zerar_nao_lidas(id: int) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE chat_conversas SET nao_lidas = 0, updated_at = NOW() WHERE id = %s",
            (id,),
        )
        return cur.rowcount > 0


def vincular_lead(id: int, lead_id: int) -> bool:
    """Vincula o lead só se ainda não houver um (não rouba vínculo curado à mão)."""
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE chat_conversas SET lead_id = %s, updated_at = NOW() "
            "WHERE id = %s AND lead_id IS NULL",
            (lead_id, id),
        )
        return cur.rowcount > 0


def deletar(id: int) -> bool:
    """Apaga uma conversa. As mensagens vão junto (FK ON DELETE CASCADE).

    NÃO toca no lead vinculado: chat_conversas.lead_id é só uma referência, e o lead
    é dado de CRM — apagar o histórico de conversa não pode apagar a captação.
    """
    with cursor(dict_cursor=False) as cur:
        cur.execute("DELETE FROM chat_conversas WHERE id = %s", (id,))
        return cur.rowcount > 0


def deletar_todas() -> dict:
    """Limpa TODO o histórico: apaga todas as conversas (mensagens vão por CASCADE).

    Preserva deliberadamente:
      - `chat_integracoes` -> a instância do WhatsApp continua CONECTADA (não exige QR novo);
      - `crm_leads`        -> os leads captados pelo chat permanecem no funil.
    Devolve quantas linhas foram apagadas, para o chamador poder auditar.
    """
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM chat_mensagens")
        msgs = cur.fetchone()["n"]
        cur.execute("DELETE FROM chat_conversas")
        return {"conversas": cur.rowcount, "mensagens": msgs}


def tocar_previa(id: int, previa: str, mensagem_em) -> bool:
    """Atualiza a prévia após um envio nosso (o outbound não passa pelo upsert)."""
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE chat_conversas
               SET ultima_mensagem_previa = %s,
                   ultima_mensagem_em = GREATEST(COALESCE(ultima_mensagem_em, %s), %s),
                   updated_at = NOW()
             WHERE id = %s
            """,
            (previa[:200], mensagem_em, mensagem_em, id),
        )
        return cur.rowcount > 0
