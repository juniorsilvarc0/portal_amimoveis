from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

TipoParceiro = Literal["CONSTRUTORA", "IMOBILIARIA", "AUTONOMO"]


class ParceiroBase(BaseModel):
    nome: str
    tipo: TipoParceiro
    cidade_id: int


class ParceiroCreate(ParceiroBase):
    pass


class ParceiroUpdate(ParceiroBase):
    pass


class ParceiroRead(ParceiroBase):
    id: int
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
