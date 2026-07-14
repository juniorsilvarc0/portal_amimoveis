"""Router de Logos — upload e gerenciamento de imagens para documentos PDF.

Endpoints:
  GET    /api/v1/logos            — lista todas as logos
  POST   /api/v1/logos            — upload de nova logo (multipart)
  GET    /api/v1/logos/{id}       — dados da logo
  GET    /api/v1/logos/{id}/imagem — serve a imagem (bytes)
  DELETE /api/v1/logos/{id}       — deletar logo
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_permission
from app.db import logos_repo

router = APIRouter(prefix="/api/v1/logos", tags=["Logos"])

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


@router.get("")
async def listar(user: dict = Depends(get_current_user)):
    return logos_repo.listar()


@router.get("/{id}")
async def obter(id: int, user: dict = Depends(get_current_user)):
    logo = logos_repo.obter(id)
    if not logo:
        raise HTTPException(status_code=404, detail="Logo não encontrada.")
    return logo


@router.post("", status_code=201)
async def criar(
    nome: str = Form(...),
    arquivo: UploadFile = File(...),
    user: dict = Depends(require_permission("logos", "criar")),
):
    if arquivo.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo não permitido: {arquivo.content_type}. Use PNG, JPEG, WebP ou SVG.")

    dados = await arquivo.read()
    if len(dados) > MAX_SIZE:
        raise HTTPException(status_code=422, detail="Arquivo excede 5 MB.")

    logo_id = logos_repo.criar(nome, dados, arquivo.content_type)
    return logos_repo.obter(logo_id)


@router.get("/{id}/imagem")
async def servir_imagem(id: int):
    result = logos_repo.obter_imagem(id)
    if not result:
        raise HTTPException(status_code=404, detail="Logo não encontrada.")
    dados, content_type = result
    return Response(content=dados, media_type=content_type)


@router.delete("/{id}")
async def deletar(id: int, user: dict = Depends(require_permission("logos", "excluir"))):
    if not logos_repo.obter(id):
        raise HTTPException(status_code=404, detail="Logo não encontrada.")
    logos_repo.deletar(id)
    return {"mensagem": "Logo excluída com sucesso."}
