"""Repositório de mensagens de WhatsApp."""
from .connection import cursor


def listar(conversa_id: int, limit: int = 50) -> list[dict]:
    """Últimas N mensagens, devolvidas em ordem cronológica (mais antiga primeiro)."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT * FROM (
                SELECT * FROM chat_mensagens
                 WHERE conversa_id = %s
                 ORDER BY id DESC
                 LIMIT %s
            ) t ORDER BY t.id ASC
            """,
            (conversa_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def obter(id: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM chat_mensagens WHERE id = %s", (id,))
        row = cur.fetchone()
        return dict(row) if row else None


def criar_pendente(conversa_id: int, conteudo: str, enviado_por_id: int | None) -> int:
    """Grava a mensagem ANTES de falar com a uazapi. O id devolvido vira o `track_id`.

    É esse id que volta no echo `fromMe` e permite reconciliar em vez de duplicar.
    Fica com `external_id` NULL (e por isso não colide na UNIQUE: no Postgres, NULLs
    não colidem — várias pendentes coexistem).
    """
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_mensagens (conversa_id, direcao, tipo, conteudo,
                                        delivery_status, enviado_por_id)
            VALUES (%s, 'saida', 'texto', %s, 'pending', %s)
            RETURNING id
            """,
            (conversa_id, conteudo, enviado_por_id),
        )
        return cur.fetchone()["id"]


def inserir_dedup(conversa_id: int, dados: dict) -> int | None:
    """Insere a mensagem vinda do webhook. Devolve None se já existia (dedup).

    O DO NOTHING sobre a UNIQUE (conversa_id, external_id) é a rede de segurança final
    contra o echo duplicado, caso a reconciliação por track_id não tenha acontecido.
    """
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_mensagens (conversa_id, external_id, direcao, tipo,
                                        conteudo, delivery_status, mensagem_em)
            VALUES (%(conversa_id)s, %(external_id)s, %(direcao)s, %(tipo)s,
                    %(conteudo)s, %(delivery_status)s, %(mensagem_em)s)
            ON CONFLICT ON CONSTRAINT chat_mensagens_dedup DO NOTHING
            RETURNING id
            """,
            {
                "conversa_id": conversa_id,
                "external_id": dados["external_id"],
                "direcao": dados["direcao"],
                "tipo": dados.get("tipo") or "texto",
                "conteudo": dados.get("conteudo"),
                "delivery_status": dados.get("delivery_status") or "pending",
                "mensagem_em": dados.get("mensagem_em"),
            },
        )
        row = cur.fetchone()
        return row["id"] if row else None


def marcar_enviada(id: int, external_id: str | None) -> bool:
    """Após o /send/text: grava o messageid e avança para 'sent'.

    O CASE preserva a monotonia: se o webhook já tiver trazido 'delivered' antes de nós
    gravarmos o retorno do envio (acontece — a uazapi é rápida), não regredimos para 'sent'.
    """
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE chat_mensagens
               SET external_id = COALESCE(external_id, %s),
                   delivery_status = CASE WHEN delivery_status = 'pending'
                                          THEN 'sent' ELSE delivery_status END,
                   updated_at = NOW()
             WHERE id = %s
            """,
            (external_id, id),
        )
        return cur.rowcount > 0


def marcar_falha(id: int, erro: str) -> bool:
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE chat_mensagens SET delivery_status = 'failed', erro = %s, updated_at = NOW() "
            "WHERE id = %s AND delivery_status = 'pending'",
            (erro[:500], id),
        )
        return cur.rowcount > 0


def reconciliar_echo(id: int, external_id: str) -> bool:
    """Casa o echo `fromMe` com a mensagem que NÓS gravamos (via track_id).

    Só reconcilia uma mensagem ainda pendente (external_id NULL) E se aquele external_id
    já não pertencer a outra mensagem da MESMA conversa. Sem o NOT EXISTS, um id repetido
    estouraria a UNIQUE (conversa_id, external_id) e derrubaria o webhook em 500 — e a
    uazapi reenviaria o evento em loop. Já reconciliado ou duplicado => no-op seguro.
    """
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            """
            UPDATE chat_mensagens m
               SET external_id = %(ext)s, updated_at = NOW()
             WHERE m.id = %(id)s
               AND m.external_id IS NULL
               AND NOT EXISTS (
                   SELECT 1 FROM chat_mensagens o
                    WHERE o.conversa_id = m.conversa_id
                      AND o.external_id = %(ext)s
               )
            """,
            {"ext": external_id, "id": id},
        )
        return cur.rowcount > 0


def atualizar_status(external_id: str, novo_status: str, sobrescreviveis: list[str]) -> bool:
    """Avança o tick. O `IN (sobrescreviveis)` é o que garante a MONOTONIA:
    um 'Delivered' que chega atrasado não consegue rebaixar uma mensagem já 'read'."""
    if not sobrescreviveis:
        return False
    with cursor(dict_cursor=False) as cur:
        cur.execute(
            "UPDATE chat_mensagens SET delivery_status = %s, updated_at = NOW() "
            "WHERE external_id = %s AND delivery_status = ANY(%s)",
            (novo_status, external_id, sobrescreviveis),
        )
        return cur.rowcount > 0
