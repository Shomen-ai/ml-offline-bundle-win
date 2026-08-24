"""ЗАПЛАТКА для backend/app/api/messages.py. Не модуль, не импортировать.

Здесь цикл инструментов подключается к потоку сообщений. Без этой правки
tools_loop.py — мёртвый код: файлы лежат, ничего не происходит.

ЛОГИКА РАЗВИЛКИ. Если tools_enabled выключен ИЛИ в реестре нет ни одного
включённого инструмента — идём прежним путём через llm_client.stream_chat,
поведение чата не меняется ни на йоту. Инструменты включаются только явно.

ЧТО МЕНЯЕТСЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ. С инструментами ответ приходит НЕ дельтами по
токену, а куском: пока модель решает, какую ручку дёрнуть, показывать нечего.
Поэтому в цикле полезны события tool_call — иначе экран молчит секунд тридцать
и выглядит зависшим.
"""

# ============================================================================
# ШАГ 1. Импорты, в начало файла — к остальным `from ..services import ...`
# ============================================================================

from ..services import tools_loop, tools_registry


# ============================================================================
# ШАГ 2. Заменить блок «# 3) стримим ответ отдельного LLM-сервера ...»
#
# ИСХОДНЫЙ КОД начинается строкой:
#     answer_parts: list[str] = []
# и кончается перед строкой:
#     # 4) сохраняем ответ целиком
#
# Заменить ВЕСЬ этот кусок вместе с try/except на код ниже.
# ============================================================================

        answer_parts: list[str] = []
        splitter = thinking.Splitter()

        # Инструменты включаются только явно и только если реестр не пуст:
        # пустой tools в промпте — напрасно потраченные токены.
        use_tools = bool(settings.get("tools_enabled")) and bool(
            await to_thread.run_sync(tools_registry.get_all)
        )

        def emit(kind: str, text: str):
            """Общая раскладка текста по SSE-кадрам: размышления отдельно."""
            out = []
            for k, t in (splitter.feed(text) if kind == "feed" else splitter.flush()):
                if k == "think":
                    out.append({"event": "think", "data": t})
                else:
                    answer_parts.append(t)
                    out.append({"event": "delta", "data": t})
            return out

        try:
            if use_tools:
                async for ev in tools_loop.run(
                    history,
                    dialog_id=dialog_id,
                    user_id=dialog["user_id"],
                    model=settings["model_name"],
                ):
                    kind = ev["type"]
                    if kind == "delta":
                        for frame in emit("feed", ev["text"]):
                            yield frame
                    elif kind == "error":
                        yield {"event": "error", "data": ev["text"]}
                    else:
                        # tool_call / tool_result / confirm — фронт, который о
                        # них не знает, их молча пропустит: в api.js разбор
                        # событий сделан цепочкой if/else if.
                        yield {"event": kind,
                               "data": json.dumps(ev, ensure_ascii=False)}
            else:
                async for delta in llm_client.stream_chat(
                    history,
                    settings["model_name"],
                    max_tokens=settings["max_tokens"],
                    temperature=settings["temperature"],
                ):
                    for frame in emit("feed", delta):
                        yield frame
            for frame in emit("flush", ""):
                yield frame
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

# ============================================================================
# ШАГ 3. Ничего больше менять не нужно.
#
# Блок «# 4) сохраняем ответ целиком» работает как прежде: answer_parts
# заполняется в обоих ветках одинаково.
# ============================================================================


# ----------------------------------------------------------------------------
# ОТКУДА user_id
#
# tools_loop пишет журнал dpis_tool_calls, туда нужен id пользователя.
# Зависимость owned_dialog отдаёт строку диалога, в ней есть user_id —
# поэтому выше используется dialog["user_id"]. Если в вашей версии
# owned_dialog возвращает диалог без этой колонки, проверьте SELECT
# в services/dialogs.py: колонка в таблице есть всегда.
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# ПРОВЕРКА после правки, по возрастанию сложности:
#
# 1. tools_enabled = 0 — чат должен работать ровно как раньше. Это главная
#    проверка: правка не должна ничего ломать, пока инструменты выключены.
#
# 2. tools_enabled = 1, реестр пуст — тоже как раньше (use_tools = False).
#
# 3. tools_enabled = 1, одна ручка на чтение из seed_tools.sql — задать
#    вопрос, на который она отвечает. В F12 -> Network -> EventStream
#    должны появиться кадры tool_call и tool_result.
#
# 4. Спросить то, для чего ручки нет. Модель должна ответить текстом, не
#    выдумывая вызов. На проверке qwen3:14b с этим справлялась.
# ----------------------------------------------------------------------------
