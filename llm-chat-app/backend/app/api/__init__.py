"""HTTP-слой: маршруты, коды ответов, форматы. Логика — в services/."""
from fastapi import APIRouter

from . import admin, auth, dialogs, llm, messages

router = APIRouter()
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(llm.router)
router.include_router(dialogs.router)
router.include_router(messages.router)
