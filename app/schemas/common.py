"""Schemas comuns reutilizáveis."""
from __future__ import annotations

from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Pagination(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PagedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: Pagination


class MessageResponse(BaseModel):
    mensagem: str
