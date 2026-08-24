"""Применяет schema_tools.sql к базе. Запуск ИЗ ПАПКИ backend:

    D:\\bundle\\ml-bundle\\.venv\\Scripts\\activate
    cd llm-chat-app\\backend
    python ..\\..\\llm-tools\\apply_tools_schema.py

Зачем отдельный скрипт, а не sqlplus: SQL*Plus не входит в Instant Client
Basic, и на машине B его может не оказаться. А oracledb в thick-режиме там
заведомо работает — через него ходит само приложение. Штатный apply_schema.py
для этого не годится: он жёстко читает schema.sql и произвольный файл принять
не умеет.

Скрипт рассчитан на повторный запуск. CREATE TABLE во второй раз выдаст
ORA-00955 (имя уже занято) — это не ошибка, а признак, что таблица уже есть,
и такие сообщения помечаются как [есть]. MERGE в dpis_settings идемпотентен
по построению.

Ничего не удаляет. Аналога --drop здесь нет намеренно.
"""
import os
import sys

# запускаться должен из backend/, чтобы импортировался его пакет app
sys.path.insert(0, os.getcwd())

try:
    from app import db
except ImportError:
    print("Не найден пакет app. Запускать надо из папки backend:")
    print(r"    cd llm-chat-app\backend")
    print(r"    python ..\..\llm-tools\apply_tools_schema.py")
    sys.exit(1)

# «уже существует» — не ошибка, а нормальный исход повторного запуска
BENIGN = ("ORA-00955", "ORA-01430", "ORA-02260", "ORA-00001")


def main() -> int:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_tools.sql")
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    db.init_pool()

    ok = exists = failed = 0
    for stmt in raw.split(";"):
        lines = [l for l in stmt.splitlines() if not l.strip().startswith("--")]
        stmt = "\n".join(lines).strip()
        if not stmt or stmt.upper() == "COMMIT":
            continue
        head = " ".join(stmt.split()[:4])
        try:
            db.execute(stmt)
            print(f"[ok]   {head}")
            ok += 1
        except Exception as e:
            text = str(e)
            if any(code in text for code in BENIGN):
                print(f"[есть] {head}")
                exists += 1
            else:
                print(f"[СБОЙ] {head}\n       {text}")
                failed += 1

    print(f"\nВыполнено: {ok}, уже было: {exists}, сбоев: {failed}")
    if failed:
        print("Сбои разбирать по тексту ORA-кода выше.")
    else:
        print("Схема готова. Проверить: SELECT COUNT(*) FROM dpis_tools;")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
