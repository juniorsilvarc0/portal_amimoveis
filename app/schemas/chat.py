"""Schemas do módulo WhatsApp (uazapi)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConexaoCreate(BaseModel):
    """Credenciais digitadas na tela de conexão. A URL passa pelo guard de SSRF."""
    api_url: str = Field(min_length=8, max_length=300)
    token: str = Field(min_length=8, max_length=300)


class ConexaoRead(BaseModel):
    """Estado da conexão para a UI.

    NÃO expõe `token` nem `webhook_secret`: o token dá controle total da instância de
    WhatsApp, e ele nunca precisa chegar ao navegador.
    """
    model_config = ConfigDict(from_attributes=True)

    configurada: bool
    id: int | None = None
    api_url: str | None = None
    conectado: bool = False
    estado: str = "unknown"
    telefone_dono: str | None = None
    webhook_url: str | None = None
    ultimo_erro: str | None = None


class QrCodeRead(BaseModel):
    connected: bool = False
    qrcode: str | None = None    # data URI (image/png base64)
    paircode: str | None = None  # código de pareamento, alternativa ao QR


class ConversaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    contato_nome: str | None = None
    contato_telefone: str
    contato_avatar_url: str | None = None
    lead_id: int | None = None
    lead_nome: str | None = None
    status: str
    nao_lidas: int
    ultima_mensagem_em: datetime | None = None
    ultima_mensagem_previa: str | None = None


class MensagemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversa_id: int
    external_id: str | None = None
    direcao: str
    tipo: str
    conteudo: str | None = None
    delivery_status: str
    erro: str | None = None
    enviado_por_id: int | None = None
    mensagem_em: datetime


class EnviarTextoCreate(BaseModel):
    texto: str = Field(min_length=1, max_length=4096)
