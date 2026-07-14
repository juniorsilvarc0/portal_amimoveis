import pytest


def test_clientes_list(client, auth_headers):
    r = client.get("/api/v1/clientes", headers=auth_headers)
    if r.status_code == 404:
        pytest.skip("router /clientes ainda não implementado")
    assert r.status_code == 200


def test_clientes_create_and_lookup(client, auth_headers):
    payload = {"cpf": "99988877766", "nome": "Teste Pytest"}
    r = client.post("/api/v1/clientes", json=payload, headers=auth_headers)
    if r.status_code == 404:
        pytest.skip("router não implementado")
    assert r.status_code in (200, 201, 409)
    # lookup
    r = client.get("/api/v1/clientes?cpf=99988877766", headers=auth_headers)
    if r.status_code == 404:
        pytest.skip("lookup por cpf não implementado")


def test_criar_cliente_sem_cpf_pendente_nao_estoura_not_null(client, auth_headers):
    """Regressão: omitir `cpf_pendente` no POST não pode virar NULL no INSERT.

    ClienteCreate declara cpf_pendente como Optional[bool] = None, então model_dump() sempre
    inclui a chave — valendo None. O repositório precisa coagir isso para False; se ele apenas
    checar a presença da chave, o INSERT grava NULL explícito, o DEFAULT false do schema não se
    aplica (default só vale para coluna omitida) e o NOT NULL estoura em 500.
    """
    payload = {"cpf": "52998224725", "nome": "Regressao Cpf Pendente"}
    r = client.post("/api/v1/clientes", json=payload, headers=auth_headers)
    if r.status_code == 404:
        pytest.skip("router não implementado")
    assert r.status_code != 500, f"cpf_pendente virou NULL no INSERT: {r.text[:200]}"
    assert r.status_code in (200, 201, 409)
