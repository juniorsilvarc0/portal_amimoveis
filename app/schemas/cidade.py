from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CidadeBase(BaseModel):
    nome: str
    uf: str = Field(..., min_length=2, max_length=2)


class CidadeCreate(CidadeBase):
    pass


class CidadeUpdate(CidadeBase):
    pass


class CidadeRead(CidadeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
