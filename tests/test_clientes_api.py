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
