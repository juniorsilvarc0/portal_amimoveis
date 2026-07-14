from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class ConjugeBase(BaseModel):
    cliente_id: int
    nome: str
    cpf: Optional[str] = None
    rg: Optional[str] = None
    rg_orgao: Optional[str] = None
    nascimento: Optional[date] = None
    nacionalidade: Optional[str] = None
    estado_civil: Optional[str] = None
    profissao: Optional[str] = None
    email: Optional[EmailStr] = None
    whatsapp: Optional[str] = None
    fixo: Optional[str] = None


class ConjugeCreate(ConjugeBase):
    pass


class ConjugeUpdate(ConjugeBase):
    pass


class ConjugeRead(ConjugeBase):
    id: int
    cliente_nome: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
