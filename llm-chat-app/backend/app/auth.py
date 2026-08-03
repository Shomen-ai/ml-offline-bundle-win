"""Авторизация: регистрация, вход, сессионные токены в БД.

Без внешних зависимостей: PBKDF2 из stdlib, opaque-токены в таблице SESSIONS —
работает офлайн, ничего докачивать не нужно.
"""
import hashlib
import secrets

import oracledb
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from . import config, db

router = APIRouter(prefix="/api/auth", tags=["auth"])

_PBKDF2_ITERATIONS = 200_000


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-zА-Яа-я0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)


class AuthOut(BaseModel):
    token: str
    username: str


def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS
    ).hex()


def _issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    db.execute(
        """
        INSERT INTO sessions (token, user_id, expires_at)
        VALUES (:token, :user_id, SYSDATE + :ttl_hours / 24)
        """,
        {"token": token, "user_id": user_id, "ttl_hours": config.TOKEN_TTL_HOURS},
    )
    return token


@router.post("/register", response_model=AuthOut)
def register(body: Credentials):
    salt = secrets.token_hex(16)
    try:
        user_id = db.insert_returning_id(
            """
            INSERT INTO users (id, username, password_hash, salt)
            VALUES (users_seq.NEXTVAL, :username, :password_hash, :salt)
            RETURNING id INTO :out_id
            """,
            {
                "username": body.username,
                "password_hash": _hash_password(body.password, salt),
                "salt": salt,
            },
        )
    except oracledb.IntegrityError:
        raise HTTPException(status_code=409, detail="Такой пользователь уже есть")
    return AuthOut(token=_issue_token(user_id), username=body.username)


@router.post("/login", response_model=AuthOut)
def login(body: Credentials):
    row = db.query_one(
        "SELECT id, password_hash, salt FROM users WHERE username = :u",
        {"u": body.username},
    )
    if row is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    expected = row["password_hash"]
    actual = _hash_password(body.password, row["salt"])
    if not secrets.compare_digest(expected, actual):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return AuthOut(token=_issue_token(int(row["id"])), username=body.username)


def current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI-зависимость: Bearer-токен -> {'id': ..., 'username': ...}."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Нет токена")
    token = authorization.removeprefix("Bearer ").strip()
    row = db.query_one(
        """
        SELECT u.id, u.username
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token = :token AND s.expires_at > SYSDATE
        """,
        {"token": token},
    )
    if row is None:
        raise HTTPException(status_code=401, detail="Сессия истекла, войдите заново")
    return {"id": int(row["id"]), "username": row["username"], "token": token}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return {"username": user["username"]}


@router.post("/logout")
def logout(user: dict = Depends(current_user)):
    db.execute("DELETE FROM sessions WHERE token = :token", {"token": user["token"]})
    return {"ok": True}
