from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AgenciaBase(BaseModel):
    nome: str
    bairro: Optional[str] = None
    numero: Optional[str] = None
    cidade_id: int


class AgenciaCreate(AgenciaBase):
    pass


class AgenciaUpdate(AgenciaBase):
    pass


class AgenciaRead(AgenciaBase):
    id: int
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
