"""Диалоги, сообщения и стриминг ответа нейронки (SSE)."""
import json

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import db, llm_client
from .auth import current_user

router = APIRouter(prefix="/api", tags=["chat"])

HISTORY_LIMIT = 40  # сколько последних сообщений уходит в контекст модели


class DialogCreate(BaseModel):
    model_name: str | None = None


class DialogPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    model_name: str | None = Field(default=None, max_length=200)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=32000)


def _own_dialog(dialog_id: int, user_id: int) -> dict:
    row = db.query_one(
        "SELECT id, title, model_name FROM dpis_dialogs WHERE id = :d AND user_id = :u",
        {"d": dialog_id, "u": user_id},
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return row


@router.get("/models")
async def models(user: dict = Depends(current_user)):
    try:
        return await llm_client.list_models()
    except Exception as e:  # LLM-сервер не поднят — фронт покажет предупреждение
        return {"models": [], "current": None, "error": str(e)}


@router.get("/dialogs")
def list_dialogs(user: dict = Depends(current_user)):
    return db.query_all(
        """
        SELECT id, title, model_name, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
        FROM dpis_dialogs WHERE user_id = :u ORDER BY id DESC
        """,
        {"u": user["id"]},
    )


@router.post("/dialogs")
def create_dialog(body: DialogCreate, user: dict = Depends(current_user)):
    dialog_id = db.insert_returning_id(
        """
        INSERT INTO dpis_dialogs (id, user_id, model_name)
        VALUES (dpis_dialogs_seq.NEXTVAL, :u, :m)
        RETURNING id INTO :out_id
        """,
        {"u": user["id"], "m": body.model_name},
    )
    return db.query_one(
        "SELECT id, title, model_name FROM dpis_dialogs WHERE id = :d", {"d": dialog_id}
    )


@router.patch("/dialogs/{dialog_id}")
def patch_dialog(dialog_id: int, body: DialogPatch, user: dict = Depends(current_user)):
    _own_dialog(dialog_id, user["id"])
    if body.title is not None:
        db.execute(
            "UPDATE dpis_dialogs SET title = :t WHERE id = :d", {"t": body.title, "d": dialog_id}
        )
    if body.model_name is not None:
        db.execute(
            "UPDATE dpis_dialogs SET model_name = :m WHERE id = :d",
            {"m": body.model_name, "d": dialog_id},
        )
    return db.query_one(
        "SELECT id, title, model_name FROM dpis_dialogs WHERE id = :d", {"d": dialog_id}
    )


@router.delete("/dialogs/{dialog_id}")
def delete_dialog(dialog_id: int, user: dict = Depends(current_user)):
    _own_dialog(dialog_id, user["id"])
    db.execute("DELETE FROM dpis_messages WHERE dialog_id = :d", {"d": dialog_id})
    db.execute("DELETE FROM dpis_dialogs WHERE id = :d", {"d": dialog_id})
    return {"ok": True}


@router.get("/dialogs/{dialog_id}/messages")
def list_messages(dialog_id: int, user: dict = Depends(current_user)):
    _own_dialog(dialog_id, user["id"])
    return db.query_all(
        """
        SELECT id, role, content, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
        FROM dpis_messages WHERE dialog_id = :d ORDER BY id
        """,
        {"d": dialog_id},
    )


def _save_message(dialog_id: int, role: str, content: str) -> int:
    return db.insert_returning_id(
        """
        INSERT INTO dpis_messages (id, dialog_id, role, content)
        VALUES (dpis_messages_seq.NEXTVAL, :d, :r, :c)
        RETURNING id INTO :out_id
        """,
        {"d": dialog_id, "r": role, "c": content},
    )


@router.post("/dialogs/{dialog_id}/messages")
async def send_message(dialog_id: int, body: MessageIn, user: dict = Depends(current_user)):
    dialog = await to_thread.run_sync(_own_dialog, dialog_id, user["id"])

    async def event_stream():
        # 1) сохраняем сообщение пользователя; первому сообщению — заголовок диалога
        user_msg_id = await to_thread.run_sync(_save_message, dialog_id, "user", body.content)
        dialog_title = dialog["title"]
        if dialog_title == "Новый диалог":
            dialog_title = body.content.strip().replace("\n", " ")[:60]
            await to_thread.run_sync(
                db.execute,
                "UPDATE dpis_dialogs SET title = :t WHERE id = :d",
                {"t": dialog_title, "d": dialog_id},
            )
        yield {
            "event": "start",
            "data": json.dumps(
                {"user_message_id": user_msg_id, "dialog_title": dialog_title},
                ensure_ascii=False,
            ),
        }

        # 2) история диалога -> контекст модели
        history = await to_thread.run_sync(
            db.query_all,
            f"""
            SELECT role, content FROM (
                SELECT role, content, id FROM dpis_messages
                WHERE dialog_id = :d ORDER BY id DESC
            ) WHERE ROWNUM <= {HISTORY_LIMIT} ORDER BY id
            """,
            {"d": dialog_id},
        )
        messages = [{"role": h["role"], "content": h["content"]} for h in history]

        # 3) стримим ответ отдельного LLM-сервера
        answer_parts: list[str] = []
        try:
            async for delta in llm_client.stream_chat(messages, dialog["model_name"]):
                answer_parts.append(delta)
                yield {"event": "delta", "data": delta}
        except Exception as e:
            yield {"event": "error", "data": f"Ошибка нейронки: {e}"}
            return

        # 4) сохраняем ответ целиком
        answer = "".join(answer_parts)
        assistant_id = await to_thread.run_sync(_save_message, dialog_id, "assistant", answer)
        yield {
            "event": "done",
            "data": json.dumps({"assistant_message_id": assistant_id}, ensure_ascii=False),
        }

    return EventSourceResponse(event_stream())
