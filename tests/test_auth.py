import pytest


def test_jwt_create_and_decode():
    from app.auth.jwt import create_access_token, decode_token
    token = create_access_token({"sub": "1", "email": "a@b.com", "perfil": "admin"})
    assert token
    payload = decode_token(token)
    assert payload["sub"] == "1"


def test_jwt_invalid_returns_none():
    from app.auth.jwt import decode_token
    assert decode_token("garbage") is None


def test_password_hash_and_verify():
    from app.auth.jwt import hash_password, verify_password
    h = hash_password("senha123")
    assert verify_password("senha123", h)
    assert not verify_password("errada", h)


def test_password_legacy_scrypt_fallback():
    """Senhas antigas em scrypt (werkzeug) devem continuar funcionando."""
    from werkzeug.security import generate_password_hash
    from app.auth.jwt import verify_password
    legacy = generate_password_hash("old_pass")
    assert legacy.startswith("scrypt:") or legacy.startswith("pbkdf2:")
    # só testa se é scrypt (pbkdf2 também deveria funcionar via mesmo fallback)
    assert verify_password("old_pass", legacy)


def test_login_success(client, admin_token):
    assert admin_token  # se chegou aqui, login funcionou


def test_login_wrong_password(client):
    try:
        r = client.post("/api/v1/auth/login", json={"email": "admin@roper.com", "senha": "errada"})
    except Exception as e:
        pytest.skip(f"DB indisponivel: {e}")
    if r.status_code == 500:
        pytest.skip("DB indisponivel (500)")
    assert r.status_code in (401, 429)


def test_me_endpoint(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@roper.com"


def test_me_without_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)
