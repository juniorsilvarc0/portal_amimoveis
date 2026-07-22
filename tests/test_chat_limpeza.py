"""Testes da limpeza de histórico do chat.

O que importa travar aqui não é "apagou", é o que NÃO pode ser apagado junto:
a conexão do WhatsApp e os leads do CRM.
"""
import pytest

from app.routers import chat as chat_router


def _override(app, user):
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


ADMIN = {"id": 1, "nome": "A", "email": "a@b.c", "perfil": "admin",
         "role_id": 1, "is_admin": True}


def test_limpar_exige_confirmacao(app, client, monkeypatch):
    """Sem ?confirmar=true -> 400 e NADA é apagado (trava anti-acidente)."""
    chamou = {"n": 0}
    monkeypatch.setattr(chat_router.chat_conversas_repo, "deletar_todas",
                        lambda: chamou.__setitem__("n", chamou["n"] + 1))
    _override(app, ADMIN)
    try:
        r = client.delete("/api/v1/chat/conversas")
        assert r.status_code == 400
        assert chamou["n"] == 0, "apagou sem confirmação!"
    finally:
        app.dependency_overrides.clear()


def test_limpar_com_confirmacao_apaga_e_reporta(app, client, monkeypatch):
    monkeypatch.setattr(chat_router.chat_conversas_repo, "deletar_todas",
                        lambda: {"conversas": 30, "mensagens": 854})
    _override(app, ADMIN)
    try:
        r = client.delete("/api/v1/chat/conversas?confirmar=true")
        assert r.status_code == 200
        corpo = r.json()["mensagem"]
        assert "30 conversas" in corpo and "854 mensagens" in corpo
        # a mensagem tem que deixar explícito o que foi preservado
        assert "preservad" in corpo.lower()
    finally:
        app.dependency_overrides.clear()


def test_deletar_conversa_inexistente_404(app, client, monkeypatch):
    monkeypatch.setattr(chat_router.chat_conversas_repo, "deletar", lambda i: False)
    _override(app, ADMIN)
    try:
        assert client.delete("/api/v1/chat/conversas/999").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_limpeza_exige_permissao_excluir(app, client):
    """Perfil sem 'excluir' em chat não pode limpar o histórico."""
    _override(app, {"id": 2, "nome": "L", "email": "l@b.c", "perfil": "usuario",
                    "role_id": 9, "is_admin": False})
    try:
        r = client.delete("/api/v1/chat/conversas?confirmar=true")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.clear()
