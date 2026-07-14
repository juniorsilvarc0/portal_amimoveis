from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class HabitacaoBase(BaseModel):
    cliente_id: int
    empreendimento: Optional[str] = None
    imovel_id: Optional[int] = None
    idade_snapshot: Optional[str] = None
    dependentes: Optional[str] = None
    coobrigado_nome: Optional[str] = None
    titular_funcao: Optional[str] = None
    titular_empresa: Optional[str] = None
    titular_admissao: Optional[str] = None
    titular_renda_bruta: Optional[str] = None
    titular_renda_liquida: Optional[str] = None
    titular_extras: Optional[str] = None
    conjuge_funcao: Optional[str] = None
    conjuge_empresa: Optional[str] = None
    conjuge_admissao: Optional[str] = None
    conjuge_renda_bruta: Optional[str] = None
    conjuge_renda_liquida: Optional[str] = None
    conjuge_extras: Optional[str] = None
    emprestimos: Optional[str] = None
    moradia_tipo: Optional[str] = None
    transportes: Optional[str] = None
    conta: Optional[str] = None
    conta_salario: Optional[str] = None
    open_finance: Optional[str] = None
    opt_in: Optional[str] = None
    biometria: Optional[str] = None
    cartao_credito: Optional[str] = None
    crot: Optional[str] = None
    valor_total: Optional[str] = None
    subsidio: Optional[str] = None
    entrada: Optional[str] = None
    negociacao: Optional[str] = None
    financiado: Optional[str] = None
    parcela: Optional[str] = None
    prazo: Optional[str] = None
    amortizacao: Optional[str] = None
    utilizar_fgts: Optional[str] = None
    endereco_imovel: Optional[str] = None
    proprietarios: Optional[str] = None
    construtora_id: Optional[int] = None
    proprietarios_construtora: Optional[str] = None
    taxa_vista_contrato: Optional[str] = None
    seguridade: Optional[str] = None


class HabitacaoCreate(HabitacaoBase):
    pass


class HabitacaoUpdate(HabitacaoBase):
    pass


class HabitacaoRead(HabitacaoBase):
    id: int
    cliente_nome: Optional[str] = None
    cliente_cpf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
