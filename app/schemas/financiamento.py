from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

ModalidadeImovel = Literal["CASA", "APARTAMENTO", "TERRENO", "COMERCIAL"]
StatusAnalise = Literal["PENDENTE", "EM_ANALISE", "APROVADO", "REPROVADO", "CANCELADO"]


class FinanciamentoBase(BaseModel):
    cliente_id: int
    imovel_id: Optional[int] = None
    gerente_id: Optional[int] = None
    parceiro_id: Optional[int] = None
    correspondente_id: Optional[int] = None
    modalidade: Optional[ModalidadeImovel] = None
    renda: Optional[Decimal] = None
    valor_financiamento: Optional[Decimal] = None
    analise: StatusAnalise = "PENDENTE"
    observacoes: Optional[str] = None


class FinanciamentoCreate(FinanciamentoBase):
    pass


class FinanciamentoUpdate(FinanciamentoBase):
    pass


class FinanciamentoRead(FinanciamentoBase):
    id: int
    cliente_nome: Optional[str] = None
    cliente_cpf: Optional[str] = None
    imovel_nome: Optional[str] = None
    gerente_nome: Optional[str] = None
    parceiro_nome: Optional[str] = None
    parceiro_tipo: Optional[str] = None
    correspondente_nome: Optional[str] = None
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
