from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LogoBase(BaseModel):
    nome: str


class LogoCreate(LogoBase):
    pass


class LogoRead(LogoBase):
    id: int
    content_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
