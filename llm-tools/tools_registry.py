"""Реестр инструментов: строки dpis_tools -> JSON-схемы для модели.

Инструмент описывается данными, а не кодом: URL плюс текст «когда применять».
Добавить ручку = добавить строку через админ-панель, без правки кода и без
переноса нового файла на изолированную машину.

Схема для модели строится на лету через pydantic. Она же — валидатор аргументов,
так что описание параметров существует ровно в одном месте (колонка params)
и разъехаться с проверкой не может.

LangChain здесь используется узко: только генератор JSON-схемы. На выходе
обычный dict в формате OpenAI, поэтому llm-server про LangChain не знает.
Обе библиотеки уже стоят на машине B (langchain-core 1.5.1, pydantic 2.13.4).
"""
import json
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field, create_model

from .. import db

_PY_TYPES = {"str": str, "int": int, "bool": bool}

# Кэш как в settings.py: реестр читается на каждое сообщение, а меняется редко.
_cache: list[dict[str, Any]] | None = None


def _read_rows() -> list[dict[str, Any]]:
    rows = db.query_all(
        """
        SELECT id, name, method, url, when_to_use, params, is_mutating
          FROM dpis_tools
         WHERE enabled = 1
         ORDER BY name
        """
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            params = json.loads(r["params"]) if r["params"] else {}
        except ValueError:
            # Битый JSON в одной строке не должен ронять весь чат: инструмент
            # просто не показывается модели, остальные работают.
            continue
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "method": r["method"],
                "url": r["url"],
                "when_to_use": r["when_to_use"],
                "params": params,
                "is_mutating": bool(r["is_mutating"]),
            }
        )
    return out


def get_all() -> list[dict[str, Any]]:
    """Включённые инструменты. Список словарей — тот же формат, что в демо."""
    global _cache
    if _cache is None:
        _cache = _read_rows()
    return list(_cache)


def by_name(name: str) -> dict[str, Any] | None:
    return next((t for t in get_all() if t["name"] == name), None)


def invalidate() -> None:
    global _cache
    _cache = None


def build_args_model(tool: dict[str, Any]) -> type[BaseModel]:
    """Описание параметров -> pydantic-модель. Здесь рождается вся валидация."""
    fields: dict[str, Any] = {}
    for pname, spec in tool["params"].items():
        if spec.get("type") == "enum":
            ann: Any = Literal[tuple(spec["values"])]  # type: ignore[misc]
        else:
            ann = _PY_TYPES.get(spec.get("type", "str"), str)

        constraints: dict[str, Any] = {}
        if "min" in spec:
            constraints["ge"] = spec["min"]
        if "max" in spec:
            constraints["le"] = spec["max"]

        desc = spec.get("desc", "")
        if spec.get("required"):
            fields[pname] = (ann, Field(description=desc, **constraints))
        else:
            # Необязательность задаётся значением по умолчанию, а НЕ Optional.
            # Через Optional pydantic развернул бы поле в anyOf[{тип},{null}]:
            # длиннее вдвое и лишний повод для мелкой модели передать null.
            fields[pname] = (ann, Field(default=None, description=desc, **constraints))
    return create_model(f"{tool['name']}_Args", **fields)


def _strip_nulls(schema: dict[str, Any]) -> dict[str, Any]:
    """Убирает из схемы следы того, что параметр необязательный.

    Две вещи, которые pydantic пишет, а модели только мешают:

    * anyOf[{тип}, {null}] — если необязательное поле объявлено через Optional.
      Здесь так не делается (аннотация остаётся строгой, необязательность даёт
      сам default), но схема может прийти и из другого места;
    * "default": null — модель иногда понимает это как разрешение передать null
      буквально, и такой аргумент потом не проходит валидацию.

    Экономия здесь скромная: на трёх ручках 4% символов. Основной выигрыш даёт
    выбор аннотации в build_args_model, а эта функция подчищает остаток.
    """
    props = schema.get("function", {}).get("parameters", {}).get("properties", {})
    for spec in props.values():
        variants = spec.get("anyOf")
        if variants:
            real = [v for v in variants if v.get("type") != "null"]
            if len(real) == 1:
                spec.pop("anyOf")
                spec.update(real[0])
        if spec.get("default", ...) is None:
            spec.pop("default")
    return schema


def build_tool_schema(tool: dict[str, Any]) -> dict[str, Any]:
    """Инструмент -> JSON в формате OpenAI, который уходит в модель."""
    structured = StructuredTool(
        name=tool["name"],
        description=tool["when_to_use"],
        args_schema=build_args_model(tool),
        func=lambda **kw: None,  # не вызывается: схема нужна только для описания
    )
    return _strip_nulls(convert_to_openai_tool(structured))


def build_all_schemas() -> list[dict[str, Any]]:
    """Схемы всех включённых инструментов — то, что уходит в /chat."""
    return [build_tool_schema(t) for t in get_all()]


def schemas_size_estimate() -> int:
    """Длина всех схем в символах.

    Нужна админ-панели: описания инструментов уходят в промпт при КАЖДОМ
    запросе и едят тот же бюджет n_ctx, из которого кормится история диалога.
    На замерах одна простая ручка стоила около 170 токенов, то есть примерно
    треть символа на токен. Панель показывает это число рядом с n_ctx, чтобы
    было видно, сколько контекста съедено до первого слова пользователя.
    """
    return sum(len(json.dumps(s, ensure_ascii=False)) for s in build_all_schemas())
