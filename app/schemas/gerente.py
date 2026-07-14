from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class GerenteBase(BaseModel):
    nome: str
    agencia_id: int


class GerenteCreate(GerenteBase):
    pass


class GerenteUpdate(GerenteBase):
    pass


class GerenteRead(GerenteBase):
    id: int
    agencia_nome: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
