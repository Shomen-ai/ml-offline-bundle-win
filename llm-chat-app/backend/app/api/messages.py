"""Сообщения диалога и стриминг ответа нейронки (SSE)."""
import json

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..deps import owned_dialog
from ..schemas.messages import MessageIn, MessageOut
from ..services import context
from ..services import dialogs as dialog_service
from ..services import llm_client
from ..services import messages as message_service
from ..services import settings as settings_service
from ..services import thinking

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/dialogs/{dialog_id}/messages", response_model=list[MessageOut])
def list_messages(dialog: dict = Depends(owned_dialog)):
    return message_service.list_for_dialog(dialog["id"])


@router.post("/dialogs/{dialog_id}/messages")
async def send_message(body: MessageIn, dialog: dict = Depends(owned_dialog)):
    dialog_id = dialog["id"]
    settings = await to_thread.run_sync(settings_service.get_all)

    # длинное сообщение отвергаем до записи в базу: иначе в истории
    # останется вопрос, на который модель физически не может ответить
    if not await context.fits_alone(body.content, settings):
        raise HTTPException(
            status_code=400,
            detail=(
                "Сообщение длиннее контекста модели. Разбейте его на части "
                "или увеличьте размер контекста в настройках."
            ),
        )

    async def event_stream():
        # 1) сохраняем сообщение пользователя; первому сообщению — заголовок диалога
        user_msg_id = await to_thread.run_sync(
            message_service.save, dialog_id, "user", body.content
        )
        dialog_title = dialog["title"]
        if dialog_title == "Новый диалог":
            dialog_title = body.content.strip().replace("\n", " ")[:60]
            await to_thread.run_sync(dialog_service.rename, dialog_id, dialog_title)
        yield {
            "event": "start",
            "data": json.dumps(
                {"user_message_id": user_msg_id, "dialog_title": dialog_title},
                ensure_ascii=False,
            ),
        }

        # 2) контекст: системный промпт, сводка и столько истории, сколько
        #    влезает в бюджет токенов; при переполнении старое сжимается
        history: list[dict] = []
        async for kind, payload in context.assemble(dialog_id, settings):
            if kind == "status":
                yield {"event": "status", "data": payload}
            else:
                history = payload

        # переключатель размышлений: суффикс уходит только в контекст,
        # в сохранённом сообщении пользователя его нет
        want_think = settings["thinking_enabled"] if body.think is None else body.think
        if not want_think and thinking.supports(settings["model_name"], settings) and history:
            last = history[-1]
            if last["role"] == "user":
                last["content"] = f"{last['content']}\n{thinking.NO_THINK}"

        # 3) стримим ответ отдельного LLM-сервера. Модель, температура и потолок
        #    длины — общие для всех диалогов, их задаёт админ-панель.
        #    Размышления отделяются от ответа и в answer_parts не попадают:
        #    на экране они живут до перезагрузки, в базе их нет вообще
        answer_parts: list[str] = []
        splitter = thinking.Splitter()
        try:
            async for delta in llm_client.stream_chat(
                history,
                settings["model_name"],
                max_tokens=settings["max_tokens"],
                temperature=settings["temperature"],
            ):
                for kind, text in splitter.feed(delta):
                    if kind == "think":
                        yield {"event": "think", "data": text}
                    else:
                        answer_parts.append(text)
                        yield {"event": "delta", "data": text}
            for kind, text in splitter.flush():
                if kind == "think":
                    yield {"event": "think", "data": text}
                else:
                    answer_parts.append(text)
                    yield {"event": "delta", "data": text}
        except Exception as e:
            # то, что успело долететь до экрана, сохраняем: иначе после
            # перезагрузки диалога кусок ответа исчезает вместе с ошибкой
            partial = "".join(answer_parts)
            if partial:
                await to_thread.run_sync(
                    message_service.save, dialog_id, "assistant", partial
                )
            yield {"event": "error", "data": f"Ошибка нейронки: {e}"}
            return

        # 4) сохраняем ответ целиком
        answer = "".join(answer_parts)
        assistant_id = await to_thread.run_sync(
            message_service.save, dialog_id, "assistant", answer
        )
        yield {
            "event": "done",
            "data": json.dumps({"assistant_message_id": assistant_id}, ensure_ascii=False),
        }

    return EventSourceResponse(event_stream())
