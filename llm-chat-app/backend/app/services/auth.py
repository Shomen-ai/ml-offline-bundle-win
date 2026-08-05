"""Пароли, сессионные токены и учётные записи.

Два режима входа, переключаются одним LDAP_URL в .env:

* локальный (по умолчанию) — PBKDF2 из stdlib, пароли в DPIS_USERS;
* доменный — проверка bind'ом в Active Directory, пароль в БД не попадает,
  учётка заводится автоматически при первом входе.

Механика сессий в обоих режимах одна: opaque-токен в DPIS_SESSIONS.
Функции этого модуля ничего не знают про HTTP — статусы ответов
расставляет роутер.
"""
import hashlib
import secrets

import oracledb

from .. import config, db
from . import ldap_auth

_PBKDF2_ITERATIONS = 200_000


class UserExists(Exception):
    """Логин занят — при локальной регистрации."""


def ldap_enabled() -> bool:
    return ldap_auth.enabled()


def hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS
    ).hex()


def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(48)
    db.execute(
        """
        INSERT INTO dpis_sessions (token, user_id, expires_at)
        VALUES (:token, :user_id, SYSDATE + :ttl_hours / 24)
        """,
        {"token": token, "user_id": user_id, "ttl_hours": config.TOKEN_TTL_HOURS},
    )
    return token


def user_id_for(username: str) -> int:
    """id доменного пользователя; при первом входе заводит строку в DPIS_USERS.

    Пароль не сохраняется — в доменном режиме password_hash/salt пустые.
    """
    row = db.query_one("SELECT id FROM dpis_users WHERE username = :u", {"u": username})
    if row is not None:
        return int(row["id"])
    try:
        return db.insert_returning_id(
            """
            INSERT INTO dpis_users (id, username)
            VALUES (dpis_users_seq.NEXTVAL, :username)
            RETURNING id INTO :out_id
            """,
            {"username": username},
        )
    except oracledb.IntegrityError:
        # два одновременных первых входа — сосед успел вставить, читаем его строку
        row = db.query_one("SELECT id FROM dpis_users WHERE username = :u", {"u": username})
        if row is None:
            raise
        return int(row["id"])


def register_local(username: str, password: str) -> int:
    """Заводит локальную учётку. UserExists — если логин занят."""
    salt = secrets.token_hex(16)
    try:
        return db.insert_returning_id(
            """
            INSERT INTO dpis_users (id, username, password_hash, salt)
            VALUES (dpis_users_seq.NEXTVAL, :username, :password_hash, :salt)
            RETURNING id INTO :out_id
            """,
            {
                "username": username,
                "password_hash": hash_password(password, salt),
                "salt": salt,
            },
        )
    except oracledb.IntegrityError as e:
        raise UserExists(username) from e


def authenticate(username: str, password: str) -> int | None:
    """Проверяет пару логин/пароль тем способом, который включён. None — отказ."""
    if ldap_auth.enabled():
        if ldap_auth.authenticate(username, password) is None:
            return None
        return user_id_for(username)

    row = db.query_one(
        "SELECT id, password_hash, salt FROM dpis_users WHERE username = :u",
        {"u": username},
    )
    # password_hash пуст у доменных учёток — локальным паролем такие не пускаем
    if row is None or not row["password_hash"] or not row["salt"]:
        return None
    if not secrets.compare_digest(row["password_hash"], hash_password(password, row["salt"])):
        return None
    return int(row["id"])


def resolve_token(token: str) -> dict | None:
    """Живая сессия -> {'id', 'username'}; истёкшая или чужая -> None."""
    row = db.query_one(
        """
        SELECT u.id, u.username
        FROM dpis_sessions s JOIN dpis_users u ON u.id = s.user_id
        WHERE s.token = :token AND s.expires_at > SYSDATE
        """,
        {"token": token},
    )
    if row is None:
        return None
    return {"id": int(row["id"]), "username": row["username"]}


def revoke_token(token: str) -> None:
    db.execute("DELETE FROM dpis_sessions WHERE token = :token", {"token": token})
