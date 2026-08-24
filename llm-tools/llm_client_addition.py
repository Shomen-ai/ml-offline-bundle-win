"""Добавка к backend/app/services/llm_client.py — НЕ отдельный модуль.

Скопировать функцию в конец существующего llm_client.py. Импорты (json, httpx,
config) там уже есть.

Зачем не стриминг: пока модель решает, какую ручку дёрнуть, показывать
пользователю нечего — токенов ответа ещё нет, есть только служебный вызов
функции. Поэтому шаги цикла идут обычным POST, и лишь финальный текстовый
ответ отдаётся дельтами через существующий stream_chat.
"""


async def chat_with_tools(
    messages: list[dict],
    model: str | None,
    tools: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> dict:
    """Один шаг цикла: отдаёт message целиком, вместе с tool_calls.

    Температура низкая намеренно: выбор ручки и аргументов — задача не
    творческая, а разброс на 14B-модели заметно повышает долю промахов.

    timeout=None: первый запрос может ждать загрузки весов в VRAM.
    """
    payload = {
        "messages": messages,
        "model": model,
        "tools": tools,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(f"{config.LLM_URL}/chat_tools", json=payload)
        if r.status_code != 200:
            raise RuntimeError(
                f"LLM-сервер ответил {r.status_code}: {r.text[:300]}"
            )
        return r.json()["message"]
