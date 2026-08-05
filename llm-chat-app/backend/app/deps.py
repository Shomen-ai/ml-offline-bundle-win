"""Зависимости FastAPI, общие для роутеров."""
from fastapi import Depends, Header, HTTPException

from .services import auth as auth_service
from .services import dialogs as dialog_service


def current_user(authorization: str = Header(default="")) -> dict:
    """Bearer-токен -> {'id', 'username', 'token'}."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Нет токена")
    token = authorization.removeprefix("Bearer ").strip()
    user = auth_service.resolve_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия истекла, войдите заново")
    return {**user, "token": token}


def owned_dialog(dialog_id: int, user: dict = Depends(current_user)) -> dict:
    """Диалог из пути, если он принадлежит текущему пользователю. Иначе 404.

    Объявлена обычным def: обращение к Oracle синхронное, и FastAPI сам
    уводит такую зависимость в threadpool — в том числе для async-ручек.
    """
    dialog = dialog_service.get_owned(dialog_id, user["id"])
    if dialog is None:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return dialog
