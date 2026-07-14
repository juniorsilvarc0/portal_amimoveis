"""Normalização do webhook de entrada da uazapi.

O formato aqui é o REAL (confirmado contra instância uazapi em produção no projeto de
origem), não o que a documentação de ENVIO sugere.

Envelope:
    {EventType, message?, event?, chat?, owner, instanceName, token}

  EventType "messages"        -> mensagem nova, em `payload["message"]`
  EventType "messages_update" -> status/mídia, em `payload["event"]`  (NÃO em "message")

Este módulo é PURO (sem I/O, sem banco): é onde os testes pegam regressão de verdade.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

# Emojis, bandeiras e o "~" que o WhatsApp prefixa em pushname auto-atualizado.
_LIXO_NOME = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️‍]+"
)


def tipo_evento(payload: dict) -> str:
    return str(payload.get("EventType") or "")


def get_mensagem(payload: dict) -> dict | None:
    for chave in ("message", "data"):
        v = payload.get(chave)
        if isinstance(v, dict):
            return v
    return None


def _jid_para_telefone(jid: str | None) -> str | None:
    """'5586999991234@s.whatsapp.net' -> '5586999991234'."""
    if not jid or not isinstance(jid, str):
        return None
    digitos = re.sub(r"\D", "", jid.split("@", 1)[0])
    return digitos or None


def _eh_jid_grupo(jid: str | None) -> bool:
    return isinstance(jid, str) and jid.endswith("@g.us")


def limpar_nome_contato(nome: str | None) -> str | None:
    if not nome or not isinstance(nome, str):
        return None
    limpo = _LIXO_NOME.sub("", nome).lstrip("~").strip()
    return limpo or None


def _mapear_tipo(bruto: str | None) -> str:
    """messageType vem em CamelCase: 'Conversation', 'AudioMessage', 'ImageMessage'..."""
    t = (bruto or "").lower()
    if "image" in t:
        return "imagem"
    if "sticker" in t:
        return "sticker"
    if "audio" in t or "ptt" in t or "voice" in t:
        return "audio"
    if "ptv" in t or "video" in t:
        return "video"
    if "document" in t:
        return "documento"
    if "contact" in t or "vcard" in t:
        return "contato"
    return "texto"


def _extrair_conteudo(m: dict) -> str | None:
    for chave in ("text", "caption"):
        v = m.get(chave)
        if isinstance(v, str) and v:
            return v
    conteudo = m.get("content")
    if isinstance(conteudo, dict):
        for chave in ("text", "caption", "body", "conversation"):
            v = conteudo.get(chave)
            if isinstance(v, str) and v:
                return v
    return None


def _para_datetime(ts) -> datetime:
    try:
        n = int(ts)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if n <= 0:
        return datetime.now(timezone.utc)
    # A uazapi manda segundos; alguns eventos vêm em milissegundos.
    segundos = n / 1000 if n > 1e12 else n
    try:
        return datetime.fromtimestamp(segundos, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return datetime.now(timezone.utc)


def normalizar_mensagem(payload: dict) -> dict | None:
    """Normaliza um evento "messages". Devolve None quando a mensagem deve ser ignorada.

    >>> A CONVERSA É CHAVEADA PELO `chatid` (o CONTRAPARTE), NUNCA pelo `sender_pn`. <<<

    Em mensagens `fromMe` (as que o dono manda, inclusive do próprio celular), o
    `sender_pn`/`senderName` são o DONO da instância. Chavear por eles criaria uma
    "conversa com você mesmo" em vez de gravar na conversa do contato.
    """
    evento = tipo_evento(payload)
    if evento and evento not in ("messages", "message"):
        return None

    m = get_mensagem(payload)
    if not m:
        return None

    chat_jid = m.get("chatid") or ""
    # Grupos ficam fora do escopo — e são descartados ANTES de tocar o banco,
    # senão cada grupo viraria um lead lixo no CRM.
    if m.get("isGroup") is True or _eh_jid_grupo(chat_jid):
        return None

    telefone = (
        _jid_para_telefone(m.get("chatid"))
        or _jid_para_telefone(m.get("sender_pn"))
        or _jid_para_telefone(m.get("sender"))
    )
    if not telefone:
        return None

    external_id = m.get("messageid") or m.get("id")
    if not external_id:
        return None

    from_me = bool(m.get("fromMe"))
    chat = payload.get("chat") if isinstance(payload.get("chat"), dict) else {}
    avatar = chat.get("imagePreview") or chat.get("image")

    return {
        "external_id": str(external_id),
        "direcao": "saida" if from_me else "entrada",
        "tipo": _mapear_tipo(m.get("messageType") or m.get("type")),
        "conteudo": _extrair_conteudo(m),
        # Em fromMe o senderName é o DONO — usar como nome do contato renomearia o
        # contato para o nome do próprio dono da instância.
        "contato_nome": None if from_me else limpar_nome_contato(m.get("senderName") or m.get("pushName")),
        "contato_telefone": telefone,
        "chat_jid": chat_jid or None,
        "contato_avatar_url": avatar,
        "mensagem_em": _para_datetime(m.get("messageTimestamp") or m.get("timestamp")),
        "track_id": m.get("track_id"),
    }


# --------------------------------------------------------------------------- status

# Ticks são MONÓTONOS: só avançam. Um webhook fora de ordem (o "Delivered" chegando
# depois do "Read") não pode fazer a mensagem regredir de lida para entregue.
# O valor é a lista de status que o novo status TEM permissão de sobrescrever.
_SOBRESCREVIVEIS: dict[str, list[str]] = {
    "failed":    ["pending"],
    "sent":      ["pending"],
    "delivered": ["pending", "sent"],
    "read":      ["pending", "sent", "delivered"],
}


def sobrescreviveis_de(novo_status: str) -> list[str]:
    return _SOBRESCREVIVEIS.get(novo_status, [])


def _mapear_status(tipo: str | None) -> str | None:
    t = (tipo or "").lower()
    if "error" in t or "fail" in t:
        return "failed"
    if "read" in t or "played" in t:
        return "read"
    if "deliver" in t:
        return "delivered"
    if "sent" in t or "server" in t:
        return "sent"
    return None  # "FileDownloaded" cai aqui: é MÍDIA, não status.


def extrair_status(payload: dict) -> list[dict]:
    """Extrai as atualizações de tick de um evento "messages_update".

    Os dados vêm em `payload["event"]` (NÃO em "message") e casam por `MessageIDs`,
    que são os `external_id` das nossas mensagens.
    """
    if tipo_evento(payload) != "messages_update":
        return []

    evt = payload.get("event")
    if not isinstance(evt, dict):
        return []

    status = _mapear_status(evt.get("Type"))
    if not status:
        return []

    ids = evt.get("MessageIDs")
    if not isinstance(ids, list):
        return []

    return [
        {"external_id": str(i), "status": status}
        for i in ids
        if isinstance(i, str) and i
    ]
