"""Применяет schema.sql к базе. Запуск: python apply_schema.py [--drop]

--drop — сначала удалить существующие объекты (данные потеряются!).
"""
import os
import sys

from app import db

DROP_STATEMENTS = [
    "DROP TABLE dpis_messages",
    "DROP TABLE dpis_dialogs",
    "DROP TABLE dpis_sessions",
    "DROP TABLE dpis_users",
    "DROP SEQUENCE dpis_messages_seq",
    "DROP SEQUENCE dpis_dialogs_seq",
    "DROP SEQUENCE dpis_users_seq",
]


def main() -> int:
    db.init_pool()
    if "--drop" in sys.argv:
        for stmt in DROP_STATEMENTS:
            try:
                db.execute(stmt)
                print(f"[drop] {stmt}")
            except Exception as e:
                print(f"[skip] {stmt}: {e}")

    path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    ok, failed = 0, 0
    for stmt in raw.split(";"):
        lines = [l for l in stmt.splitlines() if not l.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if not stmt:
            continue
        head = " ".join(stmt.split()[:3])
        try:
            db.execute(stmt)
            print(f"[ok]   {head}")
            ok += 1
        except Exception as e:
            print(f"[fail] {head}: {e}")
            failed += 1

    print(f"\nГотово: {ok} выполнено, {failed} с ошибками")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
