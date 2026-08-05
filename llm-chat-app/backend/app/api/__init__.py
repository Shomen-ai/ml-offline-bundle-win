"""HTTP-слой: маршруты, коды ответов, форматы. Логика — в services/."""
from fastapi import APIRouter

from . import auth, dialogs, messages, models

router = APIRouter()
router.include_router(auth.router)
router.include_router(models.router)
router.include_router(dialogs.router)
router.include_router(messages.router)
