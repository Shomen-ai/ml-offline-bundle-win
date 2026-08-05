"""Схемы сообщений."""
from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=32000)


class MessageOut(BaseModel):
    id: int
    role: str
    # CLOB допускает NULL, поэтому пустое сообщение из базы не должно ронять ответ
    content: str | None = None
    created_at: str | None = None
