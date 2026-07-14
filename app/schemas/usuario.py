from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# Apenas 2 perfis no portal: admin (read/write tudo) e usuario (apenas leitura).
PerfilType = Literal["admin", "usuario"]


class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr
    perfil: PerfilType = "usuario"
    role_id: Optional[int] = None


class UsuarioCreate(UsuarioBase):
    senha: str


class UsuarioUpdate(BaseModel):
    """Update parcial — todos os campos opcionais."""
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    perfil: Optional[PerfilType] = None
    role_id: Optional[int] = None
    senha: Optional[str] = None
    ativo: Optional[bool] = None


class UsuarioRead(UsuarioBase):
    id: int
    ativo: bool
    created_at: datetime
    role_nome: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
