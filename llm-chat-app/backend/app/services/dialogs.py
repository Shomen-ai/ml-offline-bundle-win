"""Диалоги: выборки и изменения. Проверка владельца возвращает None, не 404."""
from .. import db


def list_for_user(user_id: int) -> list[dict]:
    return db.query_all(
        """
        SELECT id, title, model_name, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
        FROM dpis_dialogs WHERE user_id = :u ORDER BY id DESC
        """,
        {"u": user_id},
    )


def get(dialog_id: int) -> dict | None:
    return db.query_one(
        "SELECT id, title, model_name FROM dpis_dialogs WHERE id = :d", {"d": dialog_id}
    )


def get_summary(dialog_id: int) -> dict:
    """Сводка диалога и граница, до которой она его покрывает."""
    row = db.query_one(
        "SELECT summary, summary_upto FROM dpis_dialogs WHERE id = :d", {"d": dialog_id}
    )
    if row is None:
        return {"summary": "", "summary_upto": 0}
    return {"summary": row["summary"] or "", "summary_upto": int(row["summary_upto"] or 0)}


def set_summary(dialog_id: int, summary: str, upto: int) -> None:
    db.execute(
        "UPDATE dpis_dialogs SET summary = :s, summary_upto = :u WHERE id = :d",
        {"s": summary, "u": upto, "d": dialog_id},
    )


def get_owned(dialog_id: int, user_id: int) -> dict | None:
    """Диалог, если он принадлежит этому пользователю. Иначе None."""
    return db.query_one(
        "SELECT id, title, model_name FROM dpis_dialogs WHERE id = :d AND user_id = :u",
        {"d": dialog_id, "u": user_id},
    )


def create(user_id: int, model_name: str | None) -> dict:
    dialog_id = db.insert_returning_id(
        """
        INSERT INTO dpis_dialogs (id, user_id, model_name)
        VALUES (dpis_dialogs_seq.NEXTVAL, :u, :m)
        RETURNING id INTO :out_id
        """,
        {"u": user_id, "m": model_name},
    )
    return get(dialog_id)


def rename(dialog_id: int, title: str) -> None:
    db.execute(
        "UPDATE dpis_dialogs SET title = :t WHERE id = :d", {"t": title, "d": dialog_id}
    )


def set_model(dialog_id: int, model_name: str) -> None:
    db.execute(
        "UPDATE dpis_dialogs SET model_name = :m WHERE id = :d",
        {"m": model_name, "d": dialog_id},
    )


def delete(dialog_id: int) -> None:
    # порядок важен: внешний ключ сообщений смотрит на диалог
    db.execute("DELETE FROM dpis_messages WHERE dialog_id = :d", {"d": dialog_id})
    db.execute("DELETE FROM dpis_dialogs WHERE id = :d", {"d": dialog_id})
