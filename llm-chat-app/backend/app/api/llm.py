"""Состояние LLM-сервера для интерфейса чата.

Список моделей и их переключение живут в админском роутере; чату нужно
только понимать, поднят ли сервер, чтобы показать внятное предупреждение
вместо ошибки на первой же отправке.
"""
from fastapi import APIRouter, Depends

from ..deps import current_user
from ..services import llm_client

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/health")
async def llm_health(user: dict = Depends(current_user)):
    try:
        state = await llm_client.health()
        return {"ok": True, "loaded": state.get("loaded"), "error": None}
    except Exception as e:
        return {"ok": False, "loaded": None, "error": str(e)}
