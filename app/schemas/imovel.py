from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ImovelBase(BaseModel):
    nome: str
    construtora_id: Optional[int] = None
    cidade_id: int


class ImovelCreate(ImovelBase):
    pass


class ImovelUpdate(ImovelBase):
    pass


class ImovelRead(ImovelBase):
    id: int
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    construtora_nome: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
