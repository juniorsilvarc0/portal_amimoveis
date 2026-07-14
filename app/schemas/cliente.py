from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


class ClienteBase(BaseModel):
    cpf: str = Field(..., min_length=11, max_length=14)
    nome: str
    rg: Optional[str] = None
    rg_orgao: Optional[str] = None
    nascimento: Optional[date] = None
    nacionalidade: Optional[str] = None
    estado_civil: Optional[str] = None
    regime_bens: Optional[str] = None
    profissao: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone_fixo: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    endereco: Optional[str] = None
    bairro: Optional[str] = None
    cep: Optional[str] = None
    cidade_id: Optional[int] = None
    observacoes: Optional[str] = None


class ClienteCreate(ClienteBase):
    # cpf é opcional na criação: pode ser pendente (cpf_pendente=true).
    # extra='allow' preserva os campos expandidos (sexo, tipo_pessoa, nome_mae, etc.);
    # o repositório aplica whitelist (_ALLOWED_FIELDS) no INSERT.
    cpf: Optional[str] = Field(default=None, max_length=14)
    cpf_pendente: Optional[bool] = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _validar_cpf(self):
        # CPF curto só é aceito quando o cliente é marcado como pendente.
        if not self.cpf_pendente and self.cpf:
            if len(re.sub(r"\D", "", self.cpf)) < 11:
                raise ValueError("cpf deve ter ao menos 11 dígitos (ou marque cpf_pendente).")
        return self


class ClienteUpdate(BaseModel):
    """Todos os campos são opcionais — update é sempre parcial (PATCH-like)."""
    cpf: Optional[str] = Field(None, min_length=11, max_length=14)
    nome: Optional[str] = None
    rg: Optional[str] = None
    rg_orgao: Optional[str] = None
    nascimento: Optional[date] = None
    nacionalidade: Optional[str] = None
    estado_civil: Optional[str] = None
    regime_bens: Optional[str] = None
    profissao: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone_fixo: Optional[str] = None
    whatsapp1: Optional[str] = None
    whatsapp2: Optional[str] = None
    endereco: Optional[str] = None
    bairro: Optional[str] = None
    cep: Optional[str] = None
    cidade_id: Optional[int] = None
    observacoes: Optional[str] = None


class ClienteRead(ClienteBase):
    id: int
    cpf_pendente: bool = False
    cidade_nome: Optional[str] = None
    cidade_uf: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
