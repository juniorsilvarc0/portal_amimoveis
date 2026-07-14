"""Testes do webhook de entrada (orquestração), com os repositórios mockados.

Não exige banco: o que interessa aqui é a ORDEM das operações — é ela que separa
"funciona" de "duplica toda mensagem enviada".
"""
import pytest

from app.services import chat_service


class _Espiao:
    """Registra o que foi chamado, para provar o que NÃO foi chamado também."""

    def __init__(self):
        self.chamadas: list[str] = []
        self.leads: list[tuple] = []

    # chat_integracoes_repo
    def obter_ativa(self):
        return {"id": 1, "api_url": "https://x.uazapi.com", "token": "t", "webhook_secret": "s"}

    # chat_conversas_repo
    def upsert(self, integracao_id, dados, incremento_nao_lidas=0):
        self.chamadas.append("upsert_conversa")
        self.incremento = incremento_nao_lidas
        return {"id": 10, "status": "aberta", "lead_id": None, "nao_lidas": incremento_nao_lidas}

    def vincular_lead(self, id, lead_id):
        self.chamadas.append("vincular_lead")
        return True

    # chat_mensagens_repo
    def inserir_dedup(self, conversa_id, dados):
        self.chamadas.append("inserir_mensagem")
        self.msg = dados
        return 100

    def reconciliar_echo(self, id, external_id):
        self.chamadas.append("reconciliar_echo")
        self.echo = (id, external_id)
        return True

    def atualizar_status(self, external_id, novo, sobrescreviveis):
        self.chamadas.append("atualizar_status")
        self.status = (external_id, novo, sobrescreviveis)
        return True

    # crm_leads_repo
    def upsert_por_telefone_whatsapp(self, telefone, nome):
        self.chamadas.append("upsert_lead")
        self.leads.append((telefone, nome))
        return 7


@pytest.fixture
def espiao(monkeypatch):
    e = _Espiao()
    monkeypatch.setattr(chat_service.chat_integracoes_repo, "obter_ativa", e.obter_ativa)
    monkeypatch.setattr(chat_service.chat_conversas_repo, "upsert", e.upsert)
    monkeypatch.setattr(chat_service.chat_conversas_repo, "vincular_lead", e.vincular_lead)
    monkeypatch.setattr(chat_service.chat_mensagens_repo, "inserir_dedup", e.inserir_dedup)
    monkeypatch.setattr(chat_service.chat_mensagens_repo, "reconciliar_echo", e.reconciliar_echo)
    monkeypatch.setattr(chat_service.chat_mensagens_repo, "atualizar_status", e.atualizar_status)
    monkeypatch.setattr(chat_service.crm_leads_repo, "upsert_por_telefone_whatsapp",
                        e.upsert_por_telefone_whatsapp)
    return e


def _msg(**over):
    m = {
        "messageid": "MSG1",
        "chatid": "5586999991234@s.whatsapp.net",
        "senderName": "Maria",
        "fromMe": False,
        "messageType": "Conversation",
        "text": "oi",
        "messageTimestamp": 1750000000,
    }
    m.update(over)
    return {"EventType": "messages", "message": m}


def test_inbound_cria_conversa_mensagem_e_lead(espiao):
    r = chat_service.processar_webhook(_msg())
    assert r["ok"]
    assert espiao.chamadas == [
        "upsert_conversa", "inserir_mensagem", "upsert_lead", "vincular_lead",
    ]
    assert espiao.incremento == 1                      # mensagem recebida conta como não-lida
    assert espiao.msg["delivery_status"] == "delivered"  # chegou até nós
    assert espiao.leads == [("5586999991234", "Maria")]


def test_echo_reconcilia_e_NAO_duplica(espiao):
    """A armadilha nº 2: a mensagem que enviamos volta como fromMe carregando o track_id.

    Ela precisa RECONCILIAR e parar ali. Se seguisse para o fluxo normal, seria inserida
    de novo e apareceria DUAS VEZES no chat.
    """
    r = chat_service.processar_webhook(_msg(fromMe=True, track_id="55", messageid="WID9"))
    assert r["motivo"] == "echo_reconciliado"
    assert espiao.chamadas == ["reconciliar_echo"]
    assert espiao.echo == (55, "WID9")
    assert "inserir_mensagem" not in espiao.chamadas, "o echo foi inserido de novo -> duplicou"
    assert "upsert_lead" not in espiao.chamadas


def test_fromMe_do_celular_do_dono_entra_mas_nao_cria_lead(espiao):
    """Sem track_id (não passou por nós): é gravada, mas não é captação de lead."""
    chat_service.processar_webhook(_msg(fromMe=True))
    assert "inserir_mensagem" in espiao.chamadas
    assert "upsert_lead" not in espiao.chamadas
    assert espiao.incremento == 0        # o que EU mando não conta como não-lida
    assert espiao.msg["direcao"] == "saida"


def test_grupo_e_ignorado_sem_tocar_o_banco(espiao):
    r = chat_service.processar_webhook(_msg(chatid="12036304@g.us"))
    assert r["motivo"] == "ignorado"
    assert espiao.chamadas == []


def test_messages_update_avanca_o_tick(espiao):
    r = chat_service.processar_webhook(
        {"EventType": "messages_update", "event": {"Type": "Read", "MessageIDs": ["WID9"]}}
    )
    assert r["status_atualizados"] == 1
    assert espiao.status == ("WID9", "read", ["pending", "sent", "delivered"])
    assert "inserir_mensagem" not in espiao.chamadas


def test_sem_integracao_nao_processa(monkeypatch):
    monkeypatch.setattr(chat_service.chat_integracoes_repo, "obter_ativa", lambda: None)
    r = chat_service.processar_webhook(_msg())
    assert r == {"ok": False, "motivo": "sem_integracao"}


def test_echo_com_track_id_nao_inteiro_cai_no_fluxo_normal(espiao):
    """track_id corrompido (não-inteiro) não pode derrubar o webhook: cai para o
    fluxo de mensagem nova em vez de estourar no int()."""
    r = chat_service.processar_webhook(_msg(fromMe=True, track_id="abc", messageid="WID"))
    assert r["ok"]
    assert "reconciliar_echo" not in espiao.chamadas
    assert "inserir_mensagem" in espiao.chamadas   # tratada como mensagem normal
