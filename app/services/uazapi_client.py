"""Cliente HTTP da uazapi.

ASSÍNCRONO por obrigação, não por estilo: os endpoints do Portal são `async def`, e um
`httpx.Client` (síncrono) aqui dentro travaria o event loop por até 20s a cada chamada,
derrubando o polling do chat de TODOS os usuários daquele worker. O
`webhook_dispatcher.py` usa o client síncrono, mas dentro de uma thread — aquele padrão
não vale aqui.

Autenticação: header `token: <token>` — NÃO é `Authorization: Bearer`.
A base URL é por integração (vem de `chat_integracoes.api_url`) e passa SEMPRE pelo
guard de SSRF, porque é digitada pelo usuário.
"""
from __future__ import annotations

import re

import httpx

from app.services.ssrf_guard import base_url_segura

TIMEOUT = 20.0


class UazapiError(Exception):
    """Falha ao falar com a uazapi (rede, timeout ou resposta não-2xx)."""

    def __init__(self, mensagem: str, status_code: int | None = None):
        super().__init__(mensagem)
        self.status_code = status_code


def normalizar_numero(telefone: str) -> str:
    """DDI + dígitos, sem '+' e sem máscara."""
    return re.sub(r"\D", "", telefone or "")


def _primeiro_texto(d: dict, *chaves: str) -> str | None:
    """Leitura DEFENSIVA: a uazapi muda o nome dos campos entre versões."""
    for k in chaves:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _como_data_uri(qr: str | None) -> str | None:
    """A uazapi ora devolve data URI pronta, ora base64 cru. A UI precisa da data URI."""
    if not qr:
        return None
    if qr.startswith("data:"):
        return qr
    return f"data:image/png;base64,{qr}"


async def _post(api_url: str, token: str, rota: str, body: dict | None = None) -> dict:
    base = base_url_segura(api_url)  # levanta ValueError se a URL for insegura
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{base}{rota}",
                json=body or {},
                headers={"token": token, "Content-Type": "application/json"},
            )
    except httpx.HTTPError as e:
        raise UazapiError(f"falha de rede ao chamar {rota}: {e}") from e
    if r.status_code >= 400:
        raise UazapiError(f"{rota} devolveu {r.status_code}: {r.text[:200]}", r.status_code)
    try:
        return r.json() if r.content else {}
    except ValueError:
        return {}


async def _get(api_url: str, token: str, rota: str) -> dict:
    base = base_url_segura(api_url)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{base}{rota}", headers={"token": token})
    except httpx.HTTPError as e:
        raise UazapiError(f"falha de rede ao chamar {rota}: {e}") from e
    if r.status_code >= 400:
        raise UazapiError(f"{rota} devolveu {r.status_code}: {r.text[:200]}", r.status_code)
    try:
        return r.json() if r.content else {}
    except ValueError:
        return {}


# --------------------------------------------------------------------------- conexão

async def conectar(api_url: str, token: str, phone: str | None = None) -> dict:
    """POST /instance/connect — gera o QR (ou o código de pareamento, se `phone`).

    ATENÇÃO: cada chamada REINICIA o socket de pareamento na uazapi. Chamar isto no
    mesmo ritmo do polling de status (3s) impediria o QR de ser lido. Renove só a cada
    ~25s (o TTL do QR).
    """
    body = {"phone": normalizar_numero(phone)} if phone else {}
    d = await _post(api_url, token, "/instance/connect", body)
    instancia = d.get("instance") if isinstance(d.get("instance"), dict) else {}
    return {
        "connected": bool(d.get("connected") or instancia.get("status") == "connected"),
        "qrcode": _como_data_uri(_primeiro_texto(d, "qrcode", "base64", "qr")),
        "paircode": _primeiro_texto(d, "paircode", "pairCode", "code"),
    }


async def status(api_url: str, token: str) -> dict:
    """GET /instance/status — estado da conexão + dono da instância."""
    d = await _get(api_url, token, "/instance/status")
    st = d.get("status") if isinstance(d.get("status"), dict) else {}
    instancia = d.get("instance") if isinstance(d.get("instance"), dict) else {}
    estado = _primeiro_texto(instancia, "status") or _primeiro_texto(d, "status") or "unknown"
    conectado = bool(st.get("connected") or d.get("connected") or estado in ("open", "connected"))
    return {
        "connected": conectado,
        "estado": estado if estado in ("open", "connecting", "close", "connected") else "unknown",
        "owner": _primeiro_texto(instancia, "owner", "phone") or _primeiro_texto(d, "owner"),
    }


async def registrar_webhook(api_url: str, token: str, webhook_url: str,
                            eventos: list[str] | None = None) -> None:
    """POST /webhook — manda a uazapi entregar os eventos na nossa URL.

    `webhook_url` já vem com `?s=<secret>`: a uazapi não envia headers customizados, então
    o segredo só tem como viajar na query string.
    """
    await _post(api_url, token, "/webhook", {
        "enabled": True,
        "url": webhook_url,
        "events": eventos or ["messages", "messages_update"],
    })


async def desconectar(api_url: str, token: str) -> None:
    """POST /instance/disconnect — logout do celular. As credenciais seguem válidas."""
    await _post(api_url, token, "/instance/disconnect", {})


# --------------------------------------------------------------------------- envio

async def enviar_texto(api_url: str, token: str, numero: str, texto: str,
                       track_id: str | None = None) -> dict:
    """POST /send/text.

    `track_id` é o id da NOSSA mensagem: é ele que volta no echo `fromMe` e permite
    reconciliar em vez de duplicar.
    """
    body: dict = {"number": normalizar_numero(numero), "text": texto}
    if track_id:
        body["track_id"] = str(track_id)
        body["track_source"] = "portal-ami"
    d = await _post(api_url, token, "/send/text", body)
    return {"messageid": _primeiro_texto(d, "messageid", "id", "key")}
