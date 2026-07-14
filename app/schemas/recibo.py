from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class FormaPagamento(BaseModel):
    forma: Optional[str] = None
    valor: Optional[float] = None


class ReciboBase(BaseModel):
    cliente_id: Optional[int] = None
    logo_id: Optional[int] = None
    cidade_id: Optional[int] = None
    numero_contrato: Optional[str] = None
    data_recibo: Optional[date] = None
    valor_recebido: Optional[float] = None
    nome_pagador: Optional[str] = None
    doc_pagador: Optional[str] = None
    forma_pagamento: Optional[str] = None
    formas_pagamento: Optional[List[FormaPagamento]] = None
    descricao_referencia: Optional[str] = None
    data_local: Optional[date] = None
    assinatura_nome: Optional[str] = None
    doc_recebedor: Optional[str] = None
    rodape_texto: Optional[str] = None
    observacoes: Optional[str] = None


class ReciboCreate(ReciboBase):
    pass


class ReciboUpdate(ReciboBase):
    pass


class ReciboRead(ReciboBase):
    id: int
    cliente_nome: Optional[str] = None
    cliente_cpf: Optional[str] = None
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    logo_nome: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
