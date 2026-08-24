"""Исполнение вызова инструмента: валидация аргументов и запрос к api.php.

Порядок важен: сначала аргументы прогоняются через pydantic-схему и только
потом уходит HTTP-запрос. Выдуманный моделью параметр до внутренней системы
не долетает.

Ошибка валидации НЕ поднимается наверх исключением, а возвращается модели как
результат вызова. На проверке это работало: модель придумала несуществующую
категорию, прочитала в тексте ошибки список допустимых значений и исправилась
сама. Стоило это двух лишних генераций, поэтому потолок итераций обязателен.

httpx уже стоит в бандле машины B (0.28.1) — новых колёс не требуется.
"""
import json
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from .. import config
from . import tools_registry


class ToolResult:
    """Результат вызова. ok=False означает «модель должна прочитать error»."""

    def __init__(self, ok: bool, text: str, status: str, error: str | None = None):
        self.ok = ok
        self.text = text          # то, что уходит модели как role=tool
        self.status = status      # для журнала dpis_tool_calls
        self.error = error


def _build_url(tool: dict[str, Any], values: dict[str, Any]) -> str:
    """Подставляет path-параметры в шаблон, остальное вешает в query."""
    path = tool["url"]
    query: dict[str, Any] = {}
    for pname, spec in tool["params"].items():
        if pname not in values:
            continue
        val = values[pname]
        if spec.get("in") == "path":
            path = path.replace("{" + pname + "}", quote(str(val), safe=""))
        elif spec.get("in") != "body":
            # bool в query-строке api.php ждёт как true/false, а не True/False
            query[pname] = "true" if val is True else "false" if val is False else val

    base = config.TOOLS_API_BASE.rstrip("/") if not path.startswith("http") else ""
    return base + path + ("?" + urlencode(query, encoding="utf-8") if query else "")


def _body(tool: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    return {
        p: values[p]
        for p, spec in tool["params"].items()
        if spec.get("in") == "body" and p in values
    }


async def execute(tool: dict[str, Any], raw_args: dict[str, Any]) -> ToolResult:
    """Валидирует аргументы и дёргает ручку. Исключений наружу не бросает."""
    try:
        model = tools_registry.build_args_model(tool)
        values = model(**raw_args).model_dump(exclude_none=True)
    except Exception as e:
        # Текст pydantic содержит перечень допустимых значений — именно он
        # и помогает модели исправиться, поэтому отдаём его целиком.
        return ToolResult(False, f"ОШИБКА ВАЛИДАЦИИ: {e}", "rejected", str(e)[:500])

    url = _build_url(tool, values)
    try:
        async with httpx.AsyncClient(timeout=config.TOOLS_TIMEOUT) as client:
            if tool["method"] == "POST":
                resp = await client.post(url, json=_body(tool, values),
                                         headers=_auth_headers())
            else:
                resp = await client.get(url, headers=_auth_headers())
    except Exception as e:
        return ToolResult(False, f"СЕТЕВАЯ ОШИБКА: {e}", "failed", str(e)[:500])

    if resp.status_code >= 400:
        detail = resp.text[:300]
        return ToolResult(
            False, f"HTTP {resp.status_code}: {detail}", "failed",
            f"{resp.status_code}: {detail}"[:500],
        )

    return ToolResult(True, _shrink(resp.text), "ok")


def _shrink(text: str) -> str:
    """Обрезает ответ api.php до бюджета из настроек.

    Без этого одна карточка товара съедает половину контекста. Обрезка грубая,
    по символам, и она честно сообщает модели, что данные неполные, — иначе
    модель делает выводы по обрывку и не сознаётся в этом.
    """
    from . import settings

    limit = int(settings.get_all().get("tools_result_limit", 2000))
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...(обрезано, всего {len(text)} символов)"


# --------------------------------------------------------------------------
# ЗАГЛУШКА. Авторизация во внутренних api.php.
#
# Чем закрыты ваши ручки, я не знаю, поэтому оставляю единственную точку, куда
# это вписывается. Варианты, которые встречаются чаще всего:
#
#   * общий сервисный токен в заголовке — TOOLS_API_TOKEN в .env, и тогда тело
#     функции сводится к возврату {"Authorization": f"Bearer {token}"};
#   * та же кука/сессия, что у пользователя в основной системе — тогда сюда
#     надо протащить current_user и брать его сессию, а сигнатуру функции
#     менять на execute(tool, args, user);
#   * доступ по IP-адресу сервера, без заголовков вообще — тогда оставить {}.
#
# Второй вариант — единственный, при котором модель не сможет прочитать больше,
# чем позволено самому пользователю. Если в api.php есть разграничение прав,
# выбирайте его, иначе через чат утечёт то, к чему у человека доступа нет.
# --------------------------------------------------------------------------
def _auth_headers() -> dict[str, str]:
    token = getattr(config, "TOOLS_API_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def journal(dialog_id: int, user_id: int, name: str, args: dict[str, Any],
            status: str, error: str | None = None, result_len: int = 0) -> int:
    """Пишет вызов в dpis_tool_calls, возвращает id записи.

    Для изменяющих ручек вызывается ДО исполнения со статусом pending: журнал
    ответственности не должен зависеть от того, дошло ли дело до запроса.
    """
    from .. import db

    return db.insert_returning_id(
        """
        INSERT INTO dpis_tool_calls
            (id, dialog_id, user_id, tool_name, args, status, error, result_len)
        VALUES
            (dpis_tool_calls_seq.NEXTVAL, :dialog_id, :user_id, :name, :args,
             :status, :error, :result_len)
        RETURNING id INTO :out_id
        """,
        {
            "dialog_id": dialog_id,
            "user_id": user_id,
            "name": name,
            "args": json.dumps(args, ensure_ascii=False),
            "status": status,
            "error": error,
            "result_len": result_len,
        },
    )
