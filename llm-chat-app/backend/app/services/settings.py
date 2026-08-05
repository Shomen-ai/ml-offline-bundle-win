"""Настройки LLM: хранение в БД, значения по умолчанию, кэш.

Ключ-значение вместо колонок: параметры добавляются вместе с кодом,
и заводить миграцию на каждый новый — лишняя работа. Значения в базе
лежат строками, наружу отдаются уже типизированными.

Настройки делятся на две группы:

* горячие  — применяются со следующего запроса (температура, потолок
  длины ответа, системный промпт);
* холодные — заданы при создании Llama, поэтому требуют перезагрузки
  весов в VRAM (модель, размер контекста, число слоёв на GPU).
"""
from typing import Any

from .. import db


class Setting:
    def __init__(self, default: Any, cast, cold: bool, title: str):
        self.default = default
        self.cast = cast
        self.cold = cold
        self.title = title


def _to_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# Значения по умолчанию совпадают с теми, что LLM-сервер берёт из своих
# переменных окружения, — до первого сохранения обе стороны согласованы.
SPEC: dict[str, Setting] = {
    "model_name": Setting("", str, True, "Модель"),
    "n_ctx": Setting(8192, int, True, "Размер контекста, токенов"),
    "n_gpu_layers": Setting(-1, int, True, "Слоёв на GPU (-1 — все)"),
    "temperature": Setting(0.7, float, False, "Температура"),
    "max_tokens": Setting(1024, int, False, "Потолок длины ответа, токенов"),
    "system_prompt": Setting("", str, False, "Системный промпт"),
    "thinking_enabled": Setting(True, _to_bool, False, "Размышления по умолчанию"),
    # список через запятую: у Qwen3 /no_think документирован, у прочих
    # моделей поведение не проверено, поэтому включается вручную
    "thinking_models": Setting("", str, False, "Модели с поддержкой размышлений"),
}

COLD_KEYS = tuple(k for k, s in SPEC.items() if s.cold)

_cache: dict[str, Any] | None = None


def _read_rows() -> dict[str, str]:
    rows = db.query_all("SELECT skey, sval FROM dpis_settings")
    return {r["skey"]: r["sval"] for r in rows}


def get_all() -> dict[str, Any]:
    """Все настройки, типизированные; отсутствующие — со значением по умолчанию."""
    global _cache
    if _cache is not None:
        return dict(_cache)
    stored = _read_rows()
    values: dict[str, Any] = {}
    for key, spec in SPEC.items():
        raw = stored.get(key)
        if raw is None or raw == "":
            values[key] = spec.default
            continue
        try:
            values[key] = spec.cast(raw)
        except (TypeError, ValueError):
            # мусор в базе не должен ронять чат — откатываемся к умолчанию
            values[key] = spec.default
    _cache = values
    return dict(values)


def save(changes: dict[str, Any]) -> list[str]:
    """Пишет переданные ключи. Возвращает те, что реально изменились."""
    current = get_all()
    changed: list[str] = []
    for key, value in changes.items():
        if key not in SPEC:
            continue
        if current.get(key) == SPEC[key].cast(value):
            continue
        # MERGE вместо UPDATE+INSERT: строки может ещё не быть
        db.execute(
            """
            MERGE INTO dpis_settings t
            USING (SELECT :k AS skey FROM dual) s ON (t.skey = s.skey)
            WHEN MATCHED THEN UPDATE SET t.sval = :v
            WHEN NOT MATCHED THEN INSERT (skey, sval) VALUES (:k, :v)
            """,
            {"k": key, "v": str(value)},
        )
        changed.append(key)
    invalidate()
    return changed


def invalidate() -> None:
    global _cache
    _cache = None


def needs_reload(changed: list[str]) -> bool:
    return any(key in COLD_KEYS for key in changed)
