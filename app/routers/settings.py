"""Router de configurações chave/valor.

Expõe um conjunto pequeno de chaves públicas (whitelist) para serem lidas
sem auth, e endpoints de leitura/escrita protegidos por admin para qualquer
chave.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.auth.permissions import require_admin
from app.db import settings_repo

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])

# Chaves que podem ser lidas sem autenticação (somente leitura)
PUBLIC_READABLE_KEYS = {
    "corretores_publico_ativo",
}


@router.get("/public/{key}")
async def get_public(key: str):
    if key not in PUBLIC_READABLE_KEYS:
        raise HTTPException(404, "Chave não pública")
    return {"key": key, "value": settings_repo.get(key)}


@router.get("/{key}")
async def get_admin(key: str, user=Depends(require_admin)):
    return {"key": key, "value": settings_repo.get(key)}


@router.put("/{key}")
async def set_admin(key: str, body: dict, user=Depends(require_admin)):
    value = body.get("value")
    if value is None:
        raise HTTPException(422, "Body deve conter 'value'")
    settings_repo.set(key, str(value))
    return {"key": key, "value": str(value)}
