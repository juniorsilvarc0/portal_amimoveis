from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ParentescoBase(BaseModel):
    cliente_id: int
    parente_nome: Optional[str] = None
    parente_cpf: Optional[str] = None
    parente_estado_civil: Optional[str] = None
    grau_parentesco: Optional[str] = None
    conjuge_parente_nome: Optional[str] = None
    data_declaracao: Optional[str] = None


class ParentescoCreate(ParentescoBase):
    pass


class ParentescoUpdate(ParentescoBase):
    pass


class ParentescoRead(ParentescoBase):
    id: int
    cliente_nome: Optional[str] = None
    cliente_cpf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
