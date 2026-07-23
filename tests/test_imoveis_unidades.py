"""Testes do backend imóvel↔unidade↔oportunidade (PR 2).

Foco nas GARANTIAS de negócio: auto-preenchimento do snapshot, recusa de duplicação
por unidade (409) e sincronização do status da unidade. Repos mockados — sem DB.
"""
import pytest

from app.routers import crm as crm_router
from app.routers import imoveis as imoveis_router


def _override(app, user):
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


ADMIN = {"id": 1, "nome": "A", "email": "a@b.c", "perfil": "admin", "role_id": 1, "is_admin": True}

IMOVEL = {"id": 7, "nome": "Residencial X", "endereco": "Rua A, 100", "bairro": "Centro",
          "cidade_nome": "Teresina", "cidade_uf": "PI", "cep": "64000-000", "tipo": "Apartamento"}
UNIDADE = {"id": 55, "imovel_id": 7, "identificador": "Apto 302", "valor": 300000, "status": "disponivel"}


# --------------------------------------------------------- auto-preenchimento (unitário)

def test_snapshot_preenche_do_imovel_e_unidade():
    body = {"nome": "Opp", "cliente_id": 1}
    crm_router._preencher_snapshot_imovel(body, IMOVEL, UNIDADE)
    assert body["empreendimento_nome"] == "Residencial X"
    assert body["imovel_endereco"] == "Rua A, 100"
    assert body["imovel_cidade_uf"] == "Teresina/PI"   # junta cidade + uf
    assert body["imovel_cep"] == "64000-000"
    assert body["imovel_tipo"] == "Apartamento"
    assert body["unidade"] == "Apto 302"
    assert body["valor_imovel"] == 300000
    assert body["valor"] == 300000                      # valor da opp default = valor da unidade


def test_snapshot_nao_sobrescreve_o_que_o_usuario_mandou():
    body = {"nome": "Opp", "cliente_id": 1, "imovel_tipo": "Casa", "valor": 999}
    crm_router._preencher_snapshot_imovel(body, IMOVEL, UNIDADE)
    assert body["imovel_tipo"] == "Casa"   # respeita o override
    assert body["valor"] == 999


# --------------------------------------------------------- criação de oportunidade (API)

@pytest.fixture
def mock_criar(monkeypatch):
    estado = {"criado": None, "status_unidade": None, "checou_unidade": None}
    monkeypatch.setattr(crm_router.imovel_unidades_repo, "obter", lambda i: UNIDADE)
    monkeypatch.setattr(crm_router.imoveis_repo, "obter", lambda i: IMOVEL)
    def criar(dados): estado["criado"] = dados; return 123
    monkeypatch.setattr(crm_router.crm_opportunities_repo, "criar", criar)
    monkeypatch.setattr(crm_router.crm_opportunities_repo, "aplicar_automacao_etapa_atual", lambda i: None)
    monkeypatch.setattr(crm_router.crm_opportunities_repo, "obter", lambda i: {"id": 123, "unidade_id": 55})
    def def_status(uid, st): estado["status_unidade"] = (uid, st)
    monkeypatch.setattr(crm_router.imovel_unidades_repo, "definir_status", def_status)
    monkeypatch.setattr(crm_router.webhook_dispatcher, "disparar", lambda *a, **k: None)
    return estado


def test_criar_opp_com_unidade_livre_autopreenche_e_reserva(app, client, monkeypatch, mock_criar):
    monkeypatch.setattr(crm_router.crm_opportunities_repo, "oportunidade_ativa_da_unidade", lambda uid, excluir_id=None: None)
    _override(app, ADMIN)
    try:
        r = client.post("/api/v1/crm/opportunities", json={
            "nome": "Opp Nova", "cliente_id": 1, "pipeline_id": 3, "stage_id": 8, "unidade_id": 55,
        })
        assert r.status_code == 201, r.text
        # derivou imovel_id da unidade e auto-preencheu o snapshot
        assert mock_criar["criado"]["imovel_id"] == 7
        assert mock_criar["criado"]["empreendimento_nome"] == "Residencial X"
        assert mock_criar["criado"]["unidade"] == "Apto 302"
        # reservou a unidade
        assert mock_criar["status_unidade"] == (55, "reservada")
    finally:
        app.dependency_overrides.clear()


def test_criar_opp_com_unidade_ocupada_recusa_409(app, client, monkeypatch, mock_criar):
    monkeypatch.setattr(crm_router.crm_opportunities_repo, "oportunidade_ativa_da_unidade",
                        lambda uid, excluir_id=None: {"id": 9, "nome": "Opp Antiga", "stage_nome": "Proposta"})
    _override(app, ADMIN)
    try:
        r = client.post("/api/v1/crm/opportunities", json={
            "nome": "Opp Duplicada", "cliente_id": 1, "pipeline_id": 3, "stage_id": 8, "unidade_id": 55,
        })
        assert r.status_code == 409
        assert "Opp Antiga" in r.json()["detail"]
        assert mock_criar["criado"] is None   # NÃO criou
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------- unidades (API)

def test_criar_unidade_exige_permissao_criar(app, client, monkeypatch):
    monkeypatch.setattr(imoveis_router.imoveis_repo, "obter", lambda i: IMOVEL)
    _override(app, {"id": 2, "nome": "L", "email": "l@b.c", "perfil": "usuario", "role_id": 9, "is_admin": False})
    try:
        r = client.post("/api/v1/imoveis/7/unidades", json={"identificador": "Apto 1"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_unidade_identificador_duplicado_vira_409(app, client, monkeypatch):
    monkeypatch.setattr(imoveis_router.imoveis_repo, "obter", lambda i: IMOVEL)
    def criar(imovel_id, dados): raise Exception('duplicate key value violates unique constraint "imovel_unidades_uniq"')
    monkeypatch.setattr(imoveis_router.imovel_unidades_repo, "criar", criar)
    _override(app, ADMIN)
    try:
        r = client.post("/api/v1/imoveis/7/unidades", json={"identificador": "Apto 302"})
        assert r.status_code == 409
    finally:
        app.dependency_overrides.clear()
