from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class CorretorBase(BaseModel):
    nome: str
    cpf: Optional[str] = None
    nascimento: Optional[date] = None
    telefone: Optional[str] = None
    email: Optional[EmailStr] = None
    creci: Optional[str] = None
    cidade_id: Optional[int] = None
    tamanho_camisa: Optional[str] = None
    chocolate_preferido: Optional[str] = None
    bebida_preferida: Optional[str] = None


class CorretorCreate(CorretorBase):
    """Cadastro público — todos os campos são obrigatórios pelo frontend."""
    pass


class CorretorUpdate(BaseModel):
    """Update parcial."""
    nome: Optional[str] = None
    cpf: Optional[str] = None
    nascimento: Optional[date] = None
    telefone: Optional[str] = None
    email: Optional[EmailStr] = None
    creci: Optional[str] = None
    cidade_id: Optional[int] = None
    tamanho_camisa: Optional[str] = None
    chocolate_preferido: Optional[str] = None
    bebida_preferida: Optional[str] = None


class CorretorRead(CorretorBase):
    id: int
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
