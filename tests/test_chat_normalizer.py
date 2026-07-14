"""Testes do normalizador do webhook da uazapi.

Cada teste aqui trava uma armadilha que o projeto de origem pagou caro para descobrir.
São funções puras: rodam sem banco e sem rede.
"""
from app.services.uazapi_normalizer import (
    extrair_status,
    limpar_nome_contato,
    normalizar_mensagem,
    sobrescreviveis_de,
)


def _envelope_msg(**over) -> dict:
    msg = {
        "messageid": "MSG1",
        "chatid": "5586999991234@s.whatsapp.net",
        "sender_pn": "5586999991234@s.whatsapp.net",
        "senderName": "Maria",
        "isGroup": False,
        "fromMe": False,
        "messageType": "Conversation",
        "text": "oi",
        "messageTimestamp": 1750000000,
    }
    msg.update(over)
    return {"EventType": "messages", "message": msg, "chat": {"imagePreview": "http://x/a.png"}}


# --------------------------------------------------------------------------- inbound

def test_inbound_basico():
    n = normalizar_mensagem(_envelope_msg())
    assert n["direcao"] == "entrada"
    assert n["contato_telefone"] == "5586999991234"
    assert n["conteudo"] == "oi"
    assert n["tipo"] == "texto"
    assert n["contato_nome"] == "Maria"
    assert n["external_id"] == "MSG1"


def test_conversa_e_chaveada_pelo_chatid_nao_pelo_sender():
    """A armadilha nº 1 da integração.

    Numa mensagem `fromMe` (o dono respondendo pelo próprio celular), o `sender_pn` é o
    DONO da instância, não o contato. Chavear por ele criaria uma "conversa com você
    mesmo" — a resposta iria para uma conversa com o próprio número, em vez de ir para a
    conversa do cliente.
    """
    n = normalizar_mensagem(_envelope_msg(
        fromMe=True,
        chatid="5586999991234@s.whatsapp.net",   # o CONTATO
        sender_pn="5511888887777@s.whatsapp.net",  # o DONO da instância
        senderName="AM Imóveis (dono)",
    ))
    assert n["direcao"] == "saida"
    assert n["contato_telefone"] == "5586999991234", "chaveou pelo sender, não pelo chatid"
    # E o nome do DONO não pode virar o nome do contato.
    assert n["contato_nome"] is None


def test_grupos_sao_ignorados():
    """Grupos viram lead lixo no CRM se passarem. Descartar ANTES de tocar o banco."""
    assert normalizar_mensagem(_envelope_msg(chatid="12036304@g.us")) is None
    assert normalizar_mensagem(_envelope_msg(isGroup=True)) is None


def test_sem_messageid_ou_sem_telefone_e_ignorado():
    assert normalizar_mensagem(_envelope_msg(messageid=None, id=None)) is None
    assert normalizar_mensagem(_envelope_msg(chatid="", sender_pn="", sender="")) is None


def test_evento_de_outro_tipo_nao_e_mensagem():
    assert normalizar_mensagem({"EventType": "messages_update", "event": {}}) is None


def test_tipo_de_midia_e_classificado_mas_conteudo_pode_ser_nulo():
    # v1 não baixa mídia, mas classifica o tipo (o gancho fica pronto).
    n = normalizar_mensagem(_envelope_msg(messageType="AudioMessage", text=None))
    assert n["tipo"] == "audio"
    n = normalizar_mensagem(_envelope_msg(messageType="ImageMessage", text=None, caption="foto"))
    assert n["tipo"] == "imagem" and n["conteudo"] == "foto"


def test_limpa_emoji_e_til_do_pushname():
    assert limpar_nome_contato("~Maria 🏠") == "Maria"
    assert limpar_nome_contato("   ") is None


# --------------------------------------------------------------------------- status

def _envelope_evt(tipo: str, ids=("MSG1",)) -> dict:
    return {"EventType": "messages_update", "event": {"Type": tipo, "MessageIDs": list(ids)}}


def test_extrai_ticks():
    assert extrair_status(_envelope_evt("Delivered")) == [{"external_id": "MSG1", "status": "delivered"}]
    assert extrair_status(_envelope_evt("Read"))[0]["status"] == "read"
    assert extrair_status(_envelope_evt("Played"))[0]["status"] == "read"
    assert extrair_status(_envelope_evt("Sent"))[0]["status"] == "sent"
    assert extrair_status(_envelope_evt("Error"))[0]["status"] == "failed"


def test_filedownloaded_nao_e_status():
    """FileDownloaded chega no mesmo evento dos ticks, mas é MÍDIA. Tratá-lo como status
    marcaria a mensagem com um estado inexistente."""
    assert extrair_status(_envelope_evt("FileDownloaded")) == []


def test_status_so_sai_de_messages_update():
    assert extrair_status({"EventType": "messages", "event": {"Type": "Read"}}) == []


def test_ticks_sao_monotonos():
    """Um webhook fora de ordem não pode rebaixar uma mensagem já lida.

    `sobrescreviveis_de(x)` lista os status que x TEM permissão de sobrescrever.
    """
    assert sobrescreviveis_de("sent") == ["pending"]
    assert "delivered" not in sobrescreviveis_de("sent")   # delivered -> sent: proibido
    assert "read" not in sobrescreviveis_de("delivered")   # read -> delivered: proibido
    assert set(sobrescreviveis_de("read")) == {"pending", "sent", "delivered"}
    assert sobrescreviveis_de("pending") == []             # nada regride para pending
