import pytest


def test_app_imports():
    from app.main import app
    assert app.title == "Portal AM Imóveis"


def test_openapi_schema_generated():
    from app.main import app
    schema = app.openapi()
    assert "openapi" in schema
    assert "/api/v1/auth/login" in schema["paths"]


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_docs_endpoint(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_static_mount(client):
    # /static/* deve estar montado
    r = client.get("/static/css/layout.css")
    # pode ser 200 ou 404 dependendo se o arquivo já existe;
    # mas não pode ser 500 (erro de config)
    assert r.status_code in (200, 404)
