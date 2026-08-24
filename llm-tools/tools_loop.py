"""Цикл вызова инструментов: модель просит ручку -> дёргаем -> отдаём результат.

Один вопрос пользователя разворачивается в несколько генераций подряд. На
проверке (qwen3:14b, вопрос с цепочкой из двух ручек) это было три генерации
и около тридцати секунд. Отсюда два следствия, заложенных в конструкцию:

* потолок итераций обязателен — модель умеет повторять отвергнутый вызов
  по кругу, и без потолка это не кончится;
* всё это время llm-server держит свой глобальный Lock, то есть очередь стоит.
  Пока стенд тестовый, это терпимо; при нескольких работающих людях цикл
  придётся выносить в очередь с ограничением одновременных диалогов.

События наружу отдаются теми же SSE-кадрами, что и обычный ответ, — фронту
достаточно научиться показывать два новых типа: tool_call и tool_result.
"""
import json
from typing import Any, AsyncIterator

from . import llm_client, settings, tools_executor, tools_registry


async def run(
    messages: list[dict[str, Any]],
    dialog_id: int,
    user_id: int,
    model: str | None,
) -> AsyncIterator[dict[str, Any]]:
    """Гоняет цикл, пока модель не ответит текстом или не кончатся итерации.

    Отдаёт словари-события:
        {"type": "tool_call",   "name": ..., "args": {...}}
        {"type": "tool_result", "name": ..., "ok": bool, "preview": "..."}
        {"type": "confirm",     "call_id": int, "name": ..., "args": {...}}
        {"type": "delta",       "text": "..."}   — куски финального ответа
        {"type": "error",       "text": "..."}
    """
    cfg = settings.get_all()
    max_steps = int(cfg.get("tools_max_steps", 5))
    tools = tools_registry.build_all_schemas()
    if not tools:
        # Инструментов нет — незачем платить за пустой tools в промпте.
        async for delta in llm_client.stream_chat(messages, model):
            yield {"type": "delta", "text": delta}
        return

    history = list(messages)

    for _ in range(max_steps):
        reply = await llm_client.chat_with_tools(history, model, tools)
        calls = reply.get("tool_calls") or []

        if not calls:
            # Модель ответила текстом — это конец цикла.
            yield {"type": "delta", "text": reply.get("content", "")}
            return

        history.append(reply)

        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                # Часть сборок llama.cpp отдаёт аргументы строкой, часть — объектом.
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}

            yield {"type": "tool_call", "name": name, "args": args}

            tool = tools_registry.by_name(name)
            if tool is None:
                # Модель выдумала инструмент. Не ошибка потока: возвращаем ей
                # это как результат, она выберет существующий.
                text = f"ОШИБКА: инструмента '{name}' не существует"
                history.append({"role": "tool", "name": name, "content": text})
                yield {"type": "tool_result", "name": name, "ok": False,
                       "preview": text}
                continue

            # ---------------------------------------------------------------
            # ЗАГЛУШКА. Подтверждение изменяющих вызовов.
            #
            # Здесь цикл должен остановиться, отдать фронту событие confirm с
            # готовыми аргументами и ждать, пока пользователь нажмёт кнопку.
            # Реализуется это не внутри генератора, а разрывом потока: вызов
            # пишется в dpis_tool_calls со статусом pending, поток закрывается,
            # а подтверждение приходит отдельным запросом, который продолжает
            # диалог с этого места.
            #
            # Пока изменяющих ручек нет, ветка просто отказывает — так
            # безопаснее, чем исполнить втихую.
            # ---------------------------------------------------------------
            if tool["is_mutating"]:
                call_id = tools_executor.journal(
                    dialog_id, user_id, name, args, "pending"
                )
                yield {"type": "confirm", "call_id": call_id,
                       "name": name, "args": args}
                text = ("ВЫЗОВ ОТЛОЖЕН: инструмент изменяет данные и требует "
                        "подтверждения пользователя. Сообщи об этом и остановись.")
                history.append({"role": "tool", "name": name, "content": text})
                yield {"type": "tool_result", "name": name, "ok": False,
                       "preview": text}
                continue

            result = await tools_executor.execute(tool, args)
            tools_executor.journal(
                dialog_id, user_id, name, args, result.status,
                result.error, len(result.text),
            )
            history.append({"role": "tool", "name": name, "content": result.text})
            yield {
                "type": "tool_result",
                "name": name,
                "ok": result.ok,
                "preview": result.text[:200],
            }

    # Потолок исчерпан. Молчать нельзя: пользователь ждёт ответа, а его нет.
    yield {"type": "error",
           "text": f"Модель не уложилась в {max_steps} обращений к инструментам. "
                   f"Попробуйте переформулировать вопрос конкретнее."}
