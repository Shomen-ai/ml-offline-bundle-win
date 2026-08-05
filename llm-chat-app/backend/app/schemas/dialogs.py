"""Схемы диалогов."""
from pydantic import BaseModel, Field


class DialogCreate(BaseModel):
    model_name: str | None = None


class DialogPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    model_name: str | None = Field(default=None, max_length=200)


class DialogOut(BaseModel):
    id: int
    title: str
    model_name: str | None = None
    # приходит только в списке диалогов, у одиночных ответов его нет
    created_at: str | None = None
