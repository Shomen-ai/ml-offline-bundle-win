"""Схемы настроек LLM."""
from pydantic import BaseModel, ConfigDict, Field


class SettingsPatch(BaseModel):
    """Приходят только изменённые поля; остальные остаются как были."""

    # model_name попадает в защищённое пространство имён pydantic — снимаем
    model_config = ConfigDict(protected_namespaces=())

    model_name: str | None = Field(default=None, max_length=200)
    n_ctx: int | None = Field(default=None, ge=512, le=131072)
    n_gpu_layers: int | None = Field(default=None, ge=-1, le=999)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    system_prompt: str | None = Field(default=None, max_length=8000)


class SettingInfo(BaseModel):
    key: str
    title: str
    cold: bool


class SettingsOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    values: dict
    # какие ключи требуют перезагрузки модели — чтобы фронт не хардкодил список
    spec: list[SettingInfo]
    reloaded: bool = False
    reload_error: str | None = None
