"""Testes do cliente uazapi — foco na leitura DEFENSIVA de campos aninhados.

Regressão do bug de produção: o QR real chega em `instance.qrcode`, não no topo,
e a tela dizia "a uazapi não devolveu QR". Sem pytest-asyncio: usamos asyncio.run().
"""
import asyncio

from app.services import uazapi_client as uc


def test_conectar_le_qr_aninhado_em_instance(monkeypatch):
    # a uazapi REAL devolve o QR dentro de `instance` (spincode.uazapi.com)
    async def fake_post(api_url, token, rota, body=None):
        return {"instance": {"status": "connecting", "qrcode": "AAAABBBBCCCC"}}
    monkeypatch.setattr(uc, "_post", fake_post)

    r = asyncio.run(uc.conectar("https://spincode.uazapi.com", "tok"))
    assert r["qrcode"] == "data:image/png;base64,AAAABBBBCCCC", "não leu instance.qrcode"
    assert r["connected"] is False


def test_conectar_le_qr_no_topo_tambem(monkeypatch):
    async def fake_post(api_url, token, rota, body=None):
        return {"connected": False, "qrcode": "data:image/png;base64,XYZ", "paircode": "12345"}
    monkeypatch.setattr(uc, "_post", fake_post)
    r = asyncio.run(uc.conectar("https://x.uazapi.com", "tok"))
    assert r["qrcode"] == "data:image/png;base64,XYZ"
    assert r["paircode"] == "12345"


def test_status_le_owner_e_estado_aninhados(monkeypatch):
    async def fake_get(api_url, token, rota):
        return {"instance": {"status": "open", "owner": "5586999998888@s.whatsapp.net", "connected": True}}
    monkeypatch.setattr(uc, "_get", fake_get)
    r = asyncio.run(uc.status("https://x.uazapi.com", "tok"))
    assert r["connected"] is True
    assert r["estado"] == "open"
    assert r["owner"] == "5586999998888@s.whatsapp.net"


def test_conectar_detecta_ja_conectado(monkeypatch):
    async def fake_post(api_url, token, rota, body=None):
        return {"instance": {"status": "connected"}}
    monkeypatch.setattr(uc, "_post", fake_post)
    r = asyncio.run(uc.conectar("https://x.uazapi.com", "tok"))
    assert r["connected"] is True


def test_pick_caminho_pontuado():
    assert uc._pick({"a": {"b": {"c": 7}}}, "a.b.c") == 7
    assert uc._pick({"a": {}}, "a.b.c") is None
    assert uc._pick({}, "x") is None
