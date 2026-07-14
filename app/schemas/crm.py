"""Schemas Pydantic do módulo CRM."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


# ---------- Pipeline ----------
class PipelineBase(BaseModel):
    nome: str
    descricao: Optional[str] = None
    is_default: bool = False
    ativo: bool = True


class PipelineCreate(PipelineBase):
    pass


class PipelineRead(PipelineBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Stage ----------
class StageBase(BaseModel):
    pipeline_id: int
    nome: str
    ordem: int = 0
    probabilidade: int = 0
    cor: str = "#065676"
    tipo: str = "aberto"  # aberto | ganho | perdido


class StageCreate(StageBase):
    pass


class StageRead(StageBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Campaign ----------
class CampaignBase(BaseModel):
    nome: str
    tipo: Optional[str] = None
    status: Optional[str] = "ativa"
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    orcamento: Optional[float] = None
    descricao: Optional[str] = None
    ativo: bool = True


class CampaignCreate(CampaignBase):
    pass


class CampaignRead(CampaignBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Lead ----------
class LeadBase(BaseModel):
    nome: str
    email: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    cidade_id: Optional[int] = None
    origem: Optional[str] = None
    campaign_id: Optional[int] = None
    status: Optional[str] = "novo"
    score: Optional[int] = 0
    interesse: Optional[str] = None
    imovel_interesse_id: Optional[int] = None
    valor_estimado: Optional[float] = None
    proprietario_id: Optional[int] = None
    observacoes: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadRead(LeadBase):
    id: int
    cliente_id: Optional[int] = None
    data_conversao: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Opportunity ----------
class OpportunityBase(BaseModel):
    nome: str
    cliente_id: Optional[int] = None
    lead_id: Optional[int] = None
    pipeline_id: int
    stage_id: int
    imovel_id: Optional[int] = None
    valor: Optional[float] = None
    probabilidade: Optional[int] = None
    data_previsao: Optional[date] = None
    proprietario_id: Optional[int] = None
    campaign_id: Optional[int] = None
    descricao: Optional[str] = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    nome: Optional[str] = None
    cliente_id: Optional[int] = None
    lead_id: Optional[int] = None
    pipeline_id: Optional[int] = None
    stage_id: Optional[int] = None
    imovel_id: Optional[int] = None
    valor: Optional[float] = None
    probabilidade: Optional[int] = None
    data_previsao: Optional[date] = None
    data_fechamento: Optional[date] = None
    proprietario_id: Optional[int] = None
    campaign_id: Optional[int] = None
    status: Optional[str] = None
    motivo_perda: Optional[str] = None
    descricao: Optional[str] = None


class OpportunityRead(OpportunityBase):
    id: int
    status: str
    motivo_perda: Optional[str] = None
    data_fechamento: Optional[date] = None
    proposta_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StageMoveRequest(BaseModel):
    stage_id: int
    motivo: Optional[str] = None


# ---------- Activity ----------
class ActivityBase(BaseModel):
    tipo: str  # tarefa | ligacao | reuniao | email | whatsapp | nota
    assunto: str
    descricao: Optional[str] = None
    data_atividade: Optional[datetime] = None
    status: Optional[str] = "pendente"
    prioridade: Optional[str] = "normal"
    lead_id: Optional[int] = None
    opportunity_id: Optional[int] = None
    cliente_id: Optional[int] = None
    proprietario_id: Optional[int] = None


class ActivityCreate(ActivityBase):
    pass


class ActivityRead(ActivityBase):
    id: int
    data_conclusao: Optional[datetime] = None
    criado_por_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Webhook ----------
class WebhookBase(BaseModel):
    nome: str
    url: str
    eventos: str  # csv
    secret: Optional[str] = None
    ativo: bool = True


class WebhookCreate(WebhookBase):
    pass


class WebhookRead(WebhookBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- Lead Convert ----------
class LeadConvertRequest(BaseModel):
    """Converte um lead em cliente e opcionalmente em opportunity."""
    criar_opportunity: bool = True
    opportunity_nome: Optional[str] = None
    opportunity_valor: Optional[float] = None
    stage_id: Optional[int] = None
    pipeline_id: Optional[int] = None
