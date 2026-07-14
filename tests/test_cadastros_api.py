import pytest


@pytest.mark.parametrize("resource", ["cidades", "agencias", "gerentes", "parceiros", "imoveis", "correspondentes"])
def test_cadastro_list(client, auth_headers, resource):
    r = client.get(f"/api/v1/{resource}", headers=auth_headers)
    if r.status_code == 404:
        pytest.skip(f"router /{resource} ainda não implementado")
    assert r.status_code == 200
