from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PagamentoBase(BaseModel):
    ordem: int
    descricao: str
    quantidade: Optional[str] = None
    valor_parcela: Optional[str] = None
    valor_total: Optional[str] = None
    forma: Optional[str] = None
    vencimento: Optional[str] = None


class PagamentoCreate(PagamentoBase):
    pass


class PagamentoRead(PagamentoBase):
    id: int
    proposta_id: int

    model_config = ConfigDict(from_attributes=True)


class PropostaBase(BaseModel):
    cliente_id: int
    imovel_id: Optional[int] = None
    corretor_id: Optional[int] = None
    empreendimento: Optional[str] = None
    unidade: Optional[str] = None
    valor_total: Optional[str] = None
    observacoes: Optional[str] = None
    validade: Optional[str] = None
    corretor_nome: Optional[str] = None
    corretor_creci: Optional[str] = None
    data_dia: Optional[str] = None
    data_mes: Optional[str] = None
    data_ano: Optional[str] = None


class PropostaCreate(PropostaBase):
    pagamentos: list[PagamentoCreate] = []


class PropostaUpdate(PropostaBase):
    pagamentos: list[PagamentoCreate] = []


class PropostaRead(PropostaBase):
    id: int
    cliente_nome: Optional[str] = None
    cliente_cpf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PropostaReadComPagamentos(PropostaRead):
    pagamentos: list[PagamentoRead] = []
