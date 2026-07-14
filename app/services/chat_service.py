"""Orquestração do webhook de entrada da uazapi.

A ORDEM das etapas aqui não é estética — é o que separa "funciona" de "duplica tudo".
Ela é fiel à implementação de origem, validada contra uma instância real.
"""
from __future__ import annotations

import json
import logging

from app.db import (
    chat_conversas_repo,
    chat_integracoes_repo,
    chat_mensagens_repo,
    crm_leads_repo,
)
from app.services.uazapi_normalizer import (
    extrair_status,
    get_mensagem,
    normalizar_mensagem,
    sobrescreviveis_de,
    tipo_evento,
)

logger = logging.getLogger("portal.chat")


def processar_webhook(payload: dict) -> dict:
    integ = chat_integracoes_repo.obter_ativa()
    if not integ:
        return {"ok": False, "motivo": "sem_integracao"}

    evento = tipo_evento(payload)

    # 1) messages_update -> só ticks de entrega.
    #    (FileDownloaded também chega aqui, mas é MÍDIA e a v1 não trata: extrair_status
    #     devolve [] para ele, então cai fora sozinho.)
    if evento == "messages_update":
        atualizados = 0
        for s in extrair_status(payload):
            if chat_mensagens_repo.atualizar_status(
                s["external_id"], s["status"], sobrescreviveis_de(s["status"])
            ):
                atualizados += 1
        return {"ok": True, "status_atualizados": atualizados}

    msg = get_mensagem(payload)

    # 2) ECHO: a mensagem que NÓS enviamos volta pelo webhook como fromMe, carregando o
    #    track_id que mandamos. Reconcilia e RETORNA AQUI. Se seguisse adiante, a etapa 3
    #    a inseriria de novo e ela apareceria DUAS VEZES no chat.
    if msg and msg.get("fromMe") and msg.get("track_id"):
        try:
            nosso_id = int(msg["track_id"])
        except (TypeError, ValueError):
            nosso_id = None
        if nosso_id:
            messageid = msg.get("messageid") or msg.get("id")
            if messageid:
                chat_mensagens_repo.reconciliar_echo(nosso_id, str(messageid))
            return {"ok": True, "motivo": "echo_reconciliado"}

    # 3) Mensagem nova: inbound, OU fromMe enviada do próprio celular do dono (que não
    #    tem track_id, porque não passou por nós).
    n = normalizar_mensagem(payload)
    if not n:
        logger.info("[chat/webhook] payload não reconhecido: %s", json.dumps(payload)[:400])
        return {"ok": True, "motivo": "ignorado"}

    conv = chat_conversas_repo.upsert(
        integ["id"], n,
        incremento_nao_lidas=1 if n["direcao"] == "entrada" else 0,
    )

    # Mensagem recebida já nasce 'delivered' (ela chegou até nós, afinal).
    chat_mensagens_repo.inserir_dedup(conv["id"], {
        **n,
        "delivery_status": "delivered" if n["direcao"] == "entrada" else "sent",
    })

    # 4) Lead automático — SÓ no inbound. Um fromMe não é captação de lead.
    if n["direcao"] == "entrada":
        lead_id = crm_leads_repo.upsert_por_telefone_whatsapp(
            n["contato_telefone"], n.get("contato_nome")
        )
        if lead_id and not conv.get("lead_id"):
            chat_conversas_repo.vincular_lead(conv["id"], lead_id)

    # GANCHO (v1 não implementa): relay do payload cru para uma automação/IA externa
    # enquanto a conversa estiver em modo bot.

    return {"ok": True}
