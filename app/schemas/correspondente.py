from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CorrespondenteBase(BaseModel):
    nome: str
    cidade_id: int


class CorrespondenteCreate(CorrespondenteBase):
    pass


class CorrespondenteUpdate(CorrespondenteBase):
    pass


class CorrespondenteRead(CorrespondenteBase):
    id: int
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
