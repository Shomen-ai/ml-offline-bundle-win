"""Добавка к llm-server/server.py — НЕ отдельный модуль.

Скопировать в существующий server.py. Импорты (json, Field, BaseModel,
HTTPException, app, _lock, _ensure_loaded, _llama) там уже есть.

Новая ручка, а не правка /chat: у /chat формат ответа SSE-стрим текстовых
дельт, и втискивать в него вызовы функций значило бы ломать то, что уже
работает. /chat_tools отвечает обычным JSON и живёт рядом.

Важно: llm-server по-прежнему ничего не знает ни про LangChain, ни про
реестр, ни про api.php. Он получает готовый список схем и передаёт его в
llama.cpp. Вся логика остаётся в backend'е.
"""


class ChatToolsRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    tools: list[dict] = Field(default_factory=list)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


@app.post("/chat_tools")
def chat_tools(req: ChatToolsRequest):
    """Один шаг с инструментами. Без стриминга: см. llm_client_addition.py.

    Держит тот же _lock, что и /chat: модель одна, параллельной генерации
    llama.cpp здесь не даёт. Цикл из нескольких шагов означает, что очередь
    занята всё это время, — это известное ограничение конструкции.
    """
    with _lock:
        _ensure_loaded(req.model)
        try:
            resp = _llama.create_chat_completion(
                messages=req.messages,
                tools=req.tools or None,
                # "auto" — модель сама решает, звать инструмент или ответить
                # текстом. На проверке она корректно воздерживалась от вызова,
                # когда подходящей ручки не было.
                tool_choice="auto" if req.tools else None,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                stream=False,
            )
        except Exception as e:
            # Не все сборки llama-cpp-python умеют tools для всех форматов
            # промпта. Ошибку отдаём внятно, чтобы это не выглядело как
            # поломка чата.
            raise HTTPException(500, f"Вызов инструментов не поддержан: {e}")

    message = resp["choices"][0]["message"]
    return {
        "message": {
            "role": message.get("role", "assistant"),
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
        }
    }


# --------------------------------------------------------------------------
# ЗАГЛУШКА-ПРОВЕРКА. Выполнить один раз на машине B, прежде чем строить
# остальное: убедиться, что установленная сборка llama-cpp-python вообще
# умеет tools с вашим .gguf.
#
#   curl -X POST http://127.0.0.1:8001/chat_tools ^
#        -H "Content-Type: application/json" ^
#        -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Сколько заявок по DPIS?\"}],
#             \"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_tickets\",
#             \"description\":\"Список заявок по проекту\",\"parameters\":
#             {\"type\":\"object\",\"properties\":{\"project\":{\"type\":\"string\"}},
#             \"required\":[\"project\"]}}}]}"
#
# Ожидаемо: непустой tool_calls с name=get_tickets. Если приходит 500 с
# «Вызов инструментов не поддержан» — сборка или формат промпта модели не
# поддерживают функции, и дальше идти нет смысла, пока это не решено.
# --------------------------------------------------------------------------
