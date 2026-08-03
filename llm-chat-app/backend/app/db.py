"""Пул соединений Oracle (thick-режим — Oracle 11g не работает с thin)."""
import contextlib

import oracledb

from . import config

_pool: oracledb.ConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    # 11g требует thick: подключаем Instant Client 19.x
    if config.ORACLE_CLIENT_DIR:
        oracledb.init_oracle_client(lib_dir=config.ORACLE_CLIENT_DIR)
    else:
        oracledb.init_oracle_client()
    _pool = oracledb.create_pool(
        user=config.ORACLE_USER,
        password=config.ORACLE_PASSWORD,
        dsn=config.ORACLE_DSN,
        min=1,
        max=4,
        increment=1,
    )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _clob_as_str(cursor, fetch_info):
    # CLOB (content сообщений) читаем сразу строкой, а не LOB-объектом
    if fetch_info.type_code is oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)


@contextlib.contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Пул БД не инициализирован")
    conn = _pool.acquire()
    conn.outputtypehandler = _clob_as_str
    try:
        yield conn
    finally:
        _pool.release(conn)


def query_all(sql: str, params: dict | None = None) -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def query_one(sql: str, params: dict | None = None) -> dict | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: dict | None = None) -> None:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or {})
        conn.commit()


def insert_returning_id(sql: str, params: dict) -> int:
    """INSERT ... RETURNING id INTO :out_id — 11g-совместимо (sequence в SQL)."""
    with get_conn() as conn:
        cur = conn.cursor()
        out_id = cur.var(oracledb.NUMBER)
        cur.execute(sql, {**params, "out_id": out_id})
        conn.commit()
        return int(out_id.getvalue()[0])
