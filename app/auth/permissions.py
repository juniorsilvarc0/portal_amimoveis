"""Enforcement de permissões granulares (RBAC).

Espelha o padrão de require_role em app/auth/dependencies.py, mas resolve a
permissão a partir do perfil (role) do usuário e da matriz recurso × ação.

Avaliação: 1 query indexada por request (barata para a escala do portal) e
mudanças de permissão propagam imediatamente, sem precisar re-login.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import get_current_user
from app.auth.recursos import ACOES, RECURSO_KEYS


def get_user_permissions(user: dict) -> dict:
    """Retorna a matriz de permissões do usuário: {recurso: {ver, criar, editar, excluir}}.

    Administrador (role de sistema) recebe tudo True. Demais perfis leem a matriz
    do banco; recurso ausente = todas as ações False.
    """
    todos_true = {a: True for a in ACOES}
    todos_false = {a: False for a in ACOES}

    if user.get("is_admin"):
        return {r: dict(todos_true) for r in RECURSO_KEYS}

    role_id = user.get("role_id")
    base = {r: dict(todos_false) for r in RECURSO_KEYS}
    if not role_id:
        return base

    try:
        from app.db import rbac_repo
        for row in rbac_repo.get_permissions_for_role(role_id):
            rec = row["recurso"]
            if rec in base:
                base[rec] = {a: bool(row.get(a)) for a in ACOES}
    except Exception:
        # Em caso de falha de leitura, nega por segurança (já é tudo False).
        pass
    return base


def user_can(user: dict, recurso: str, acao: str) -> bool:
    if user.get("is_admin"):
        return True
    perms = get_user_permissions(user)
    return bool(perms.get(recurso, {}).get(acao))


def require_permission(recurso: str, acao: str):
    """Dependency factory: exige `acao` sobre `recurso`.

    Uso::

        @router.post("")
        async def criar(..., user=Depends(require_permission("clientes", "criar"))):
            ...
    """
    if recurso not in RECURSO_KEYS:
        raise ValueError(f"Recurso RBAC desconhecido: {recurso}")
    if acao not in ACOES:
        raise ValueError(f"Ação RBAC desconhecida: {acao}")

    def _check(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if not user_can(current_user, recurso, acao):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso negado: sem permissão para {acao} em {recurso}.",
            )
        return current_user

    return _check


def require_admin(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """Exige perfil de sistema (Administrador). Para recursos de superusuário."""
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao Administrador.",
        )
    return current_user
