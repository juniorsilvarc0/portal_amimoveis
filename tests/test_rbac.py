"""Testes do RBAC granular — catálogo de recursos, lógica de permissões,
dependencies (require_permission/require_admin) e endpoints do router de perfis.

Tudo aqui roda SEM banco de dados: a lógica que tocaria o banco
(rbac_repo.get_permissions_for_role) é substituída via monkeypatch, e os
testes de API usam app.dependency_overrides para injetar o usuário atual.
"""
import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Catálogo de recursos (app/auth/recursos.py)
# ---------------------------------------------------------------------------

def test_recursos_catalogo():
    from app.auth.recursos import RECURSOS, RECURSO_KEYS, ACOES

    assert len(RECURSOS) == 23
    assert ACOES == ("ver", "criar", "editar", "excluir")
    # chaves representativas de cada grupo
    for key in ("clientes", "habitacao", "recibo", "financiamento",
                "crm_leads", "crm_opportunities", "cad_cidades", "logos",
                "chat", "chat_conexao", "usuarios"):
        assert key in RECURSO_KEYS
    # cada item tem key/label/grupo
    for r in RECURSOS:
        assert {"key", "label", "grupo"} <= set(r.keys())
    # keys únicas
    assert len(RECURSO_KEYS) == len(RECURSOS)


# ---------------------------------------------------------------------------
# get_user_permissions / user_can (app/auth/permissions.py)
# ---------------------------------------------------------------------------

def test_admin_tem_tudo():
    from app.auth.permissions import get_user_permissions, user_can
    from app.auth.recursos import RECURSO_KEYS, ACOES

    perms = get_user_permissions({"is_admin": True})
    assert set(perms.keys()) == set(RECURSO_KEYS)
    for rec in RECURSO_KEYS:
        for acao in ACOES:
            assert perms[rec][acao] is True
    assert user_can({"is_admin": True}, "clientes", "excluir") is True


def test_perfil_parcial(monkeypatch):
    """Usuário não-admin com permissão só de ver clientes."""
    import app.db.rbac_repo as rbac_repo

    def fake_perms(role_id):
        assert role_id == 5
        return [{"recurso": "clientes", "ver": True, "criar": False,
                 "editar": False, "excluir": False}]

    monkeypatch.setattr(rbac_repo, "get_permissions_for_role", fake_perms)

    from app.auth.permissions import get_user_permissions, user_can
    user = {"is_admin": False, "role_id": 5}
    perms = get_user_permissions(user)

    assert perms["clientes"]["ver"] is True
    assert perms["clientes"]["criar"] is False
    # recurso não atribuído fica tudo False
    assert perms["habitacao"]["ver"] is False
    assert user_can(user, "clientes", "ver") is True
    assert user_can(user, "clientes", "criar") is False
    assert user_can(user, "habitacao", "ver") is False


def test_sem_role_nao_tem_nada():
    from app.auth.permissions import get_user_permissions, user_can
    user = {"is_admin": False, "role_id": None}
    perms = get_user_permissions(user)
    assert all(not any(v.values()) for v in perms.values())
    assert user_can(user, "clientes", "ver") is False


# ---------------------------------------------------------------------------
# require_permission / require_admin (dependencies chamadas diretamente)
# ---------------------------------------------------------------------------

def test_require_permission_nega_e_permite(monkeypatch):
    import app.db.rbac_repo as rbac_repo
    monkeypatch.setattr(
        rbac_repo, "get_permissions_for_role",
        lambda role_id: [{"recurso": "clientes", "ver": True, "criar": False,
                          "editar": False, "excluir": False}],
    )
    from app.auth.permissions import require_permission

    user = {"is_admin": False, "role_id": 5}

    # 'ver' permitido → retorna o próprio usuário
    dep_ver = require_permission("clientes", "ver")
    assert dep_ver(user) is user

    # 'criar' negado → 403
    dep_criar = require_permission("clientes", "criar")
    with pytest.raises(HTTPException) as exc:
        dep_criar(user)
    assert exc.value.status_code == 403


def test_require_permission_admin_bypassa():
    from app.auth.permissions import require_permission
    dep = require_permission("clientes", "excluir")
    admin = {"is_admin": True}
    assert dep(admin) is admin


def test_require_permission_recurso_invalido():
    from app.auth.permissions import require_permission
    with pytest.raises(ValueError):
        require_permission("inexistente", "ver")
    with pytest.raises(ValueError):
        require_permission("clientes", "voar")


def test_require_admin():
    from app.auth.permissions import require_admin
    admin = {"is_admin": True}
    assert require_admin(admin) is admin
    with pytest.raises(HTTPException) as exc:
        require_admin({"is_admin": False})
    assert exc.value.status_code == 403


# ---------------------------------------------------------------------------
# get_current_user — fallback de tokens antigos (sem is_admin/role_id)
# ---------------------------------------------------------------------------

def _creds(token):
    from fastapi.security import HTTPAuthorizationCredentials
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_novo_carrega_role_e_admin():
    from app.auth.jwt import create_access_token
    from app.auth.dependencies import get_current_user
    token = create_access_token({
        "sub": "7", "nome": "X", "email": "x@y.com", "perfil": "admin",
        "role_id": 1, "role_nome": "Administrador", "is_admin": True,
    })
    u = get_current_user(_creds(token))
    assert u["id"] == 7 and u["is_admin"] is True and u["role_id"] == 1


def test_token_legado_deriva_is_admin_do_perfil():
    from app.auth.jwt import create_access_token
    from app.auth.dependencies import get_current_user
    # token "antigo": sem is_admin/role_id
    tok_admin = create_access_token({"sub": "1", "nome": "A", "email": "a@b.com", "perfil": "admin"})
    tok_user = create_access_token({"sub": "2", "nome": "B", "email": "b@b.com", "perfil": "usuario"})
    assert get_current_user(_creds(tok_admin))["is_admin"] is True
    assert get_current_user(_creds(tok_user))["is_admin"] is False


# ---------------------------------------------------------------------------
# API — router de perfis (sem DB: usa dependency_overrides / monkeypatch)
# ---------------------------------------------------------------------------

def _override_user(app, user):
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


def test_recursos_endpoint_exige_auth(client):
    # sem token → 401/403
    r = client.get("/api/v1/perfis/recursos")
    assert r.status_code in (401, 403)


def test_recursos_endpoint_lista_catalogo(app, client):
    # GET /perfis/recursos só depende de get_current_user e não toca o banco
    _override_user(app, {"id": 1, "nome": "X", "email": "x@y.com",
                         "perfil": "usuario", "role_id": 9, "is_admin": False})
    try:
        r = client.get("/api/v1/perfis/recursos")
        assert r.status_code == 200
        body = r.json()
        # Compara com o catálogo em vez de um número fixo: o endpoint tem que devolver
        # o catálogo INTEIRO, e a contagem já é travada em test_recursos_catalogo.
        # (Um segundo número mágico aqui só vira armadilha para quem adiciona recurso.)
        from app.auth.recursos import RECURSOS
        assert len(body["recursos"]) == len(RECURSOS)
        assert body["acoes"] == ["ver", "criar", "editar", "excluir"]
    finally:
        app.dependency_overrides.clear()


def test_post_cliente_negado_por_permissao(app, client, monkeypatch):
    """Usuário sem 'clientes.criar' recebe 403 ANTES de tocar o banco."""
    import app.db.rbac_repo as rbac_repo
    monkeypatch.setattr(rbac_repo, "get_permissions_for_role",
                        lambda role_id: [])  # nenhuma permissão

    _override_user(app, {"id": 2, "nome": "Vend", "email": "v@y.com",
                         "perfil": "usuario", "role_id": 9, "is_admin": False})
    try:
        r = client.post("/api/v1/clientes", json={"nome": "Fulano", "cpf": "12345678901"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
