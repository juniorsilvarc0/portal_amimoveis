from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ImovelBase(BaseModel):
    nome: str
    construtora_id: Optional[int] = None
    cidade_id: int
    # Dados de empreendimento — herdados pela oportunidade ao selecionar o imóvel.
    endereco: Optional[str] = None
    bairro: Optional[str] = None
    cep: Optional[str] = None
    tipo: Optional[str] = None


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


# --------------------------------------------------------------------------- unidades

class UnidadeBase(BaseModel):
    identificador: str
    valor: Optional[Decimal] = None
    status: Optional[str] = None            # disponivel | reservada | vendida
    observacao: Optional[str] = None


class UnidadeCreate(UnidadeBase):
    pass


class UnidadeUpdate(UnidadeBase):
    pass


class UnidadeRead(UnidadeBase):
    id: int
    imovel_id: int
    ocupada: Optional[bool] = None          # tem oportunidade não-perdida
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
