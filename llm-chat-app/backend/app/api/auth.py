"""Маршруты авторизации: регистрация, вход, выход."""
from fastapi import APIRouter, Depends, HTTPException

from ..deps import current_user
from ..schemas.auth import AuthMode, AuthOut, Credentials, OkOut, UserOut
from ..services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/mode", response_model=AuthMode)
def mode():
    """Публичная ручка для фронта: показывать ли вкладку регистрации."""
    return AuthMode(ldap=auth_service.ldap_enabled())


@router.post("/register", response_model=AuthOut)
def register(body: Credentials):
    if auth_service.ldap_enabled():
        raise HTTPException(
            status_code=403,
            detail="Регистрация отключена: учётные записи берутся из домена",
        )
    try:
        user_id = auth_service.register_local(body.username, body.password)
    except auth_service.UserExists:
        raise HTTPException(status_code=409, detail="Такой пользователь уже есть")
    return AuthOut(token=auth_service.issue_token(user_id), username=body.username)


@router.post("/login", response_model=AuthOut)
def login(body: Credentials):
    user_id = auth_service.authenticate(body.username, body.password)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return AuthOut(token=auth_service.issue_token(user_id), username=body.username)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)):
    return UserOut(username=user["username"])


@router.post("/logout", response_model=OkOut)
def logout(user: dict = Depends(current_user)):
    auth_service.revoke_token(user["token"])
    return OkOut(ok=True)
