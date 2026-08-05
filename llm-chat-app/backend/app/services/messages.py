"""Сообщения диалога: чтение, сохранение и сборка истории для модели."""
from .. import db

# сколько последних сообщений уходит в контекст модели
HISTORY_LIMIT = 40


def list_for_dialog(dialog_id: int) -> list[dict]:
    return db.query_all(
        """
        SELECT id, role, content, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
        FROM dpis_messages WHERE dialog_id = :d ORDER BY id
        """,
        {"d": dialog_id},
    )


def save(dialog_id: int, role: str, content: str) -> int:
    return db.insert_returning_id(
        """
        INSERT INTO dpis_messages (id, dialog_id, role, content)
        VALUES (dpis_messages_seq.NEXTVAL, :d, :r, :c)
        RETURNING id INTO :out_id
        """,
        {"d": dialog_id, "r": role, "c": content},
    )


def history_for_model(dialog_id: int) -> list[dict]:
    """Последние HISTORY_LIMIT сообщений в формате messages для LLM-сервера.

    Обрезка по количеству — временная: она не считает токены и потому
    переполняет контекст на длинных диалогах. Заменяется на подсчёт
    токенов со сжатием (см. спеку от 2026-08-06).
    """
    rows = db.query_all(
        f"""
        SELECT role, content FROM (
            SELECT role, content, id FROM dpis_messages
            WHERE dialog_id = :d ORDER BY id DESC
        ) WHERE ROWNUM <= {HISTORY_LIMIT} ORDER BY id
        """,
        {"d": dialog_id},
    )
    return [{"role": r["role"], "content": r["content"]} for r in rows]
