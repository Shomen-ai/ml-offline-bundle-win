"""Админ-панель: настройки LLM и список моделей.

Доступ пока не ограничен — стенд тестовый, ролей и флага админа нет.
Перед реальной эксплуатацией сюда нужна проверка прав, иначе любой
пользователь перезагрузит модель под всеми остальными.
"""
from fastapi import APIRouter, Depends

from ..deps import current_user
from ..schemas.settings import SettingInfo, SettingsOut, SettingsPatch
from ..services import llm_client
from ..services import settings as settings_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _spec() -> list[SettingInfo]:
    return [
        SettingInfo(key=key, title=s.title, cold=s.cold)
        for key, s in settings_service.SPEC.items()
    ]


@router.get("/settings", response_model=SettingsOut)
def read_settings(user: dict = Depends(current_user)):
    return SettingsOut(values=settings_service.get_all(), spec=_spec())


@router.put("/settings", response_model=SettingsOut)
async def write_settings(body: SettingsPatch, user: dict = Depends(current_user)):
    changed = settings_service.save(body.model_dump(exclude_none=True))
    values = settings_service.get_all()

    reloaded = False
    reload_error = None
    if settings_service.needs_reload(changed):
        # холодные параметры живут только внутри загруженной Llama,
        # поэтому применяются перезагрузкой весов
        try:
            await llm_client.load(
                values["model_name"], values["n_ctx"], values["n_gpu_layers"]
            )
            reloaded = True
        except Exception as e:
            # настройки уже сохранены: не откатываем, но честно говорим,
            # что модель осталась на прежних параметрах
            reload_error = str(e)

    return SettingsOut(
        values=values, spec=_spec(), reloaded=reloaded, reload_error=reload_error
    )


@router.get("/models")
async def models(user: dict = Depends(current_user)):
    try:
        return await llm_client.list_models()
    except Exception as e:  # LLM-сервер не поднят — панель покажет предупреждение
        return {"models": [], "current": None, "error": str(e)}
