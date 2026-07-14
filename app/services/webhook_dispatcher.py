"""Dispatcher de webhooks CRM (envio assíncrono via thread, com HMAC-SHA256 e log)."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
from datetime import datetime
from typing import Any

import httpx

from app.db import crm_webhooks_repo

logger = logging.getLogger("webhook")


def _assinar(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _enviar_webhook(webhook: dict, evento: str, dados: dict) -> None:
    payload = {
        "evento": evento,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": dados,
    }
    payload_bytes = json.dumps(payload, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AMImoveis-CRM-Webhook/1.0",
        "X-CRM-Event": evento,
    }
    if webhook.get("secret"):
        headers["X-CRM-Signature"] = _assinar(payload_bytes, webhook["secret"])

    status_code = None
    response_body = None
    erro = None
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(webhook["url"], content=payload_bytes, headers=headers)
            status_code = r.status_code
            response_body = r.text[:2000]
    except Exception as exc:  # captura amplamente: rede, DNS, timeout, etc.
        erro = str(exc)[:500]
        logger.warning("Webhook %s falhou: %s", webhook["url"], erro)

    try:
        crm_webhooks_repo.registrar_log(
            webhook["id"], evento, payload,
            status_code=status_code, response_body=response_body, erro=erro,
        )
    except Exception as log_exc:
        logger.error("Falha ao gravar log de webhook: %s", log_exc)


def disparar(evento: str, dados: dict) -> None:
    """Dispara um evento para todos os webhooks ativos cadastrados.

    Eventos suportados (convenção):
      - lead.created
      - lead.updated
      - lead.converted
      - lead.deleted
      - opportunity.created
      - opportunity.updated
      - opportunity.stage_changed
      - opportunity.won
      - opportunity.lost
      - opportunity.deleted
      - activity.created
      - activity.completed
    """
    try:
        webhooks = crm_webhooks_repo.listar_ativos_por_evento(evento)
    except Exception as exc:
        logger.warning("Não foi possível listar webhooks para %s: %s", evento, exc)
        return

    for wh in webhooks:
        # Dispara em thread daemon para não bloquear a request
        t = threading.Thread(
            target=_enviar_webhook, args=(wh, evento, dados), daemon=True
        )
        t.start()
