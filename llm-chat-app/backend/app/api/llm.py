"""Состояние LLM-сервера для интерфейса чата.

Список моделей и их переключение живут в админском роутере; чату нужно
только понимать, поднят ли сервер, чтобы показать внятное предупреждение
вместо ошибки на первой же отправке.
"""
from fastapi import APIRouter, Depends

from anyio import to_thread

from ..deps import current_user
from ..services import llm_client
from ..services import settings as settings_service
from ..services import thinking

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/health")
async def llm_health(user: dict = Depends(current_user)):
    settings = await to_thread.run_sync(settings_service.get_all)
    try:
        state = await llm_client.health()
    except Exception as e:
        return {
            "ok": False,
            "loaded": None,
            "thinking_supported": False,
            "thinking_default": settings["thinking_enabled"],
            "error": str(e),
        }

    # поддержку проверяем по реально загруженной модели: в настройках
    # может стоять пустая строка, означающая «первая доступная»
    loaded = state.get("loaded") or settings["model_name"]
    return {
        "ok": True,
        "loaded": state.get("loaded"),
        "thinking_supported": thinking.supports(loaded, settings),
        "thinking_default": settings["thinking_enabled"],
        "error": None,
    }
