"""Проверка окружения машины B. Запускать ПЕРВЫМ, до всех правок.

    D:\bundle\ml-bundle\.venv\Scripts\activate
    python check_env.py

Проверяет три вещи по отдельности, чтобы при провале было понятно, что чинить:
пакеты на месте, схема инструмента строится, LLM-сервер умеет вызывать функции.

Ничего не устанавливает и ничего не меняет.
"""
import json
import sys

LLM_URL = "http://127.0.0.1:8001"

ok = True


def say(good: bool, text: str) -> None:
    global ok
    if not good:
        ok = False
    print(f"  [{'OK ' if good else 'НЕТ'}] {text}")


print(f"\nPython {sys.version.split()[0]}")
say(sys.version_info >= (3, 10), "версия Python >= 3.10 (langchain-core 1.x ниже не ставится)")

print("\n1. Пакеты")
for mod, name in [("langchain_core", "langchain-core"), ("pydantic", "pydantic"),
                  ("httpx", "httpx")]:
    try:
        m = __import__(mod)
        say(True, f"{name} {getattr(m, '__version__', getattr(m, 'VERSION', '?'))}")
    except ImportError as e:
        say(False, f"{name} — НЕ УСТАНОВЛЕН ({e})")

print("\n2. Построение схемы инструмента")
try:
    from langchain_core.tools import StructuredTool
    from langchain_core.utils.function_calling import convert_to_openai_tool
    from pydantic import Field, create_model
    from typing import Literal

    Args = create_model(
        "Probe_Args",
        project=(str, Field(description="Код проекта")),
        status=(Literal["open", "closed"], Field(default=None, description="Статус")),
    )
    schema = convert_to_openai_tool(StructuredTool(
        name="probe", description="проверочный инструмент",
        args_schema=Args, func=lambda **kw: None))
    has_enum = "enum" in json.dumps(schema)
    say(has_enum, "схема строится, enum на месте")
    if not has_enum:
        print(json.dumps(schema, ensure_ascii=False, indent=2))
except Exception as e:
    say(False, f"схема не строится: {e}")

print("\n3. LLM-сервер и поддержка вызова функций")
try:
    import httpx

    h = httpx.get(f"{LLM_URL}/health", timeout=5).json()
    say(True, f"сервер отвечает, загружена модель: {h.get('loaded')}")

    probe_tool = {
        "type": "function",
        "function": {
            "name": "get_tickets",
            "description": "Список заявок по проекту",
            "parameters": {
                "type": "object",
                "properties": {"project": {"type": "string",
                                           "description": "Код проекта"}},
                "required": ["project"],
            },
        },
    }
    r = httpx.post(
        f"{LLM_URL}/chat_tools",
        json={"messages": [{"role": "user", "content": "Сколько заявок по проекту DPIS?"}],
              "tools": [probe_tool], "temperature": 0.1},
        timeout=600,
    )
    if r.status_code == 404:
        say(False, "/chat_tools нет — не дописан llm_server_addition.py в server.py")
    elif r.status_code != 200:
        say(False, f"/chat_tools ответил {r.status_code}: {r.text[:200]}")
    else:
        calls = r.json().get("message", {}).get("tool_calls") or []
        say(bool(calls), f"модель вернула вызовов: {len(calls)}")
        if calls:
            fn = calls[0].get("function", {})
            print(f"         -> {fn.get('name')}({fn.get('arguments')})")
        else:
            print("         Модель ответила текстом вместо вызова. Причины по "
                  "убыванию вероятности:")
            print("         - формат промпта .gguf не поддерживает функции;")
            print("         - сборка llama-cpp-python старая;")
            print("         - модель слишком мала (ниже 7B шансы невелики).")
except Exception as e:
    say(False, f"сервер недоступен ({e}). Запущен ли run_llm.bat?")

print("\n" + ("ВСЁ ГОТОВО, можно приступать к правкам."
              if ok else "ЕСТЬ ПРОБЛЕМЫ — см. отметки НЕТ выше."))
sys.exit(0 if ok else 1)
