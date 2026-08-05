"""Список моделей LLM-сервера.

Отдельным роутером, потому что по спеке от 2026-08-06 он переезжает
в админский раздел, когда появится панель настроек.
"""
from fastapi import APIRouter, Depends

from ..deps import current_user
from ..services import llm_client

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def models(user: dict = Depends(current_user)):
    try:
        return await llm_client.list_models()
    except Exception as e:  # LLM-сервер не поднят — фронт покажет предупреждение
        return {"models": [], "current": None, "error": str(e)}
