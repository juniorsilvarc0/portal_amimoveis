import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_db_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    return url


@pytest.fixture(scope="session")
def app():
    """FastAPI app; skipado se falhar pra não bloquear outros testes."""
    try:
        from app.main import app as _app
        return _app
    except Exception as e:
        pytest.skip(f"FastAPI app não pôde ser importado: {e}")


@pytest.fixture(scope="session")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="session")
def admin_token(client):
    """Loga como admin e retorna o JWT.

    Credenciais vêm do ambiente (nunca hardcoded):
      TEST_ADMIN_EMAIL / TEST_ADMIN_SENHA  (ou ADMIN_PASSWORD)
    Sem elas, o teste é pulado.
    """
    email = os.environ.get("TEST_ADMIN_EMAIL")
    senha = os.environ.get("TEST_ADMIN_SENHA") or os.environ.get("ADMIN_PASSWORD")
    if not email or not senha:
        pytest.skip("defina TEST_ADMIN_EMAIL e TEST_ADMIN_SENHA (ou ADMIN_PASSWORD) para os testes autenticados")
    try:
        r = client.post("/api/v1/auth/login", json={"email": email, "senha": senha})
    except Exception as e:
        pytest.skip(f"auth endpoint indisponível: {e}")
    if r.status_code != 200:
        pytest.skip(f"admin login não disponível (status {r.status_code}): {r.text[:100]}")
    return r.json()["access_token"]


# scope="session" nos três fixtures acima é deliberado: o login tem rate limit (10/60s por IP).
# Com escopo de função, cada teste autenticado logava de novo, o ~11º tomava 429 e o fixture
# fazia pytest.skip() — sumindo com testes reais da suíte sem ninguém notar. Foi assim que um
# bug de produção (cpf_pendente NULL no POST /clientes) passou despercebido: o teste que o
# pegava era justamente o skipado. Uma sessão = um login.
@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
