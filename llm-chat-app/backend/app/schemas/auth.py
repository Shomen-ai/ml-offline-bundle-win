"""Схемы авторизации."""
from pydantic import BaseModel, Field


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-zА-Яа-я0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class AuthOut(BaseModel):
    token: str
    username: str


class AuthMode(BaseModel):
    ldap: bool


class UserOut(BaseModel):
    username: str


class OkOut(BaseModel):
    ok: bool
