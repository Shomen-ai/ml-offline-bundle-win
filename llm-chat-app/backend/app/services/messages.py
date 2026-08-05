"""Сообщения диалога: чтение и сохранение.

Отбор того, что уместится в контекст модели, живёт в services/context.py —
здесь только выборка сырых строк.
"""
from .. import db

# потолок на выборку: контекст всё равно режется по токенам, а тащить
# из базы весь длинный диалог целиком незачем
FETCH_LIMIT = 500


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


def list_after(dialog_id: int, after_id: int) -> list[dict]:
    """Сообщения диалога новее указанного id — то, что ещё не покрыто сводкой."""
    return db.query_all(
        f"""
        SELECT id, role, content FROM (
            SELECT id, role, content FROM dpis_messages
            WHERE dialog_id = :d AND id > :after ORDER BY id DESC
        ) WHERE ROWNUM <= {FETCH_LIMIT} ORDER BY id
        """,
        {"d": dialog_id, "after": after_id},
    )
