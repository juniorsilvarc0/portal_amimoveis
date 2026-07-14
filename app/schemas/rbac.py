from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class PermissaoItem(BaseModel):
    recurso: str
    ver: bool = False
    criar: bool = False
    editar: bool = False
    excluir: bool = False


class RoleBase(BaseModel):
    nome: str
    descricao: Optional[str] = None


class RoleCreate(RoleBase):
    permissoes: List[PermissaoItem] = []


class RoleUpdate(RoleBase):
    permissoes: List[PermissaoItem] = []


class RoleRead(RoleBase):
    id: int
    is_system: bool
    ativo: bool
    usuarios_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RoleDetail(RoleRead):
    permissoes: List[PermissaoItem] = []
