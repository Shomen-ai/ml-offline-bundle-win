"""Конфигурация backend'а: всё через переменные окружения / .env."""
import os

from dotenv import load_dotenv

load_dotenv()

# Oracle 11g: обязателен thick-режим (Instant Client 19.x)
ORACLE_USER = os.getenv("ORACLE_USER", "APP_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "")
ORACLE_DSN = os.getenv("ORACLE_DSN", "127.0.0.1:1521/ORCL")
# путь к распакованному Instant Client; пусто = клиент уже в PATH
ORACLE_CLIENT_DIR = os.getenv("ORACLE_CLIENT_DIR", r"D:\oracle\instantclient_19_31")

# Отдельный сервер с нейронкой (llm-server/server.py)
LLM_URL = os.getenv("LLM_URL", "http://127.0.0.1:8001")

# Active Directory. Пусто = вход по локальному паролю из таблицы USERS,
# заполнено = проверка bind'ом в каталог, пароли в БД не хранятся.
LDAP_URL = os.getenv("LDAP_URL", "")  # ldap://dc.example.local:389 (или ldaps://...:636)
LDAP_DOMAIN = os.getenv("LDAP_DOMAIN", "")  # example.local — логин уходит как user@domain
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "")  # пусто = не искать атрибуты, только проверить пароль
LDAP_USER_ATTR = os.getenv("LDAP_USER_ATTR", "sAMAccountName")
LDAP_TIMEOUT = int(os.getenv("LDAP_TIMEOUT", "10"))

# Сессии
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "72"))

# Сборка фронта (после npm run build) — если папка существует,
# backend отдаёт её как статику и фронт живёт на том же порту
FRONTEND_DIST = os.getenv(
    "FRONTEND_DIST",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")),
)

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
