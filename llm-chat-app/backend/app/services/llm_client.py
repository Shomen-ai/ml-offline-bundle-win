"""Клиент к отдельному LLM-серверу (llm-server/server.py).

httpx уже стоит в бандле машины B (0.28.1) — новых колёс не требуется.
"""
import json
from typing import AsyncIterator

import httpx

from .. import config


async def list_models() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{config.LLM_URL}/models")
        r.raise_for_status()
        return r.json()


async def health() -> dict:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{config.LLM_URL}/health")
        r.raise_for_status()
        return r.json()


async def load(model: str, n_ctx: int, n_gpu_layers: int) -> dict:
    """Перезагружает модель с новыми параметрами.

    Таймаут щедрый: чтение весов с диска и раскладка по VRAM занимают
    десятки секунд, а на модели покрупнее — минуты.
    """
    async with httpx.AsyncClient(timeout=600) as client:
        r = await client.post(
            f"{config.LLM_URL}/load",
            json={"model": model, "n_ctx": n_ctx, "n_gpu_layers": n_gpu_layers},
        )
        r.raise_for_status()
        return r.json()


async def stream_chat(
    messages: list[dict],
    model: str | None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Отдаёт текстовые дельты ответа. Ошибки сервера пробрасывает RuntimeError."""
    payload = {
        "messages": messages,
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    # timeout=None: первая дельта может ждать загрузки модели (десятки секунд)
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{config.LLM_URL}/chat", json=payload) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"LLM-сервер ответил {resp.status_code}: {body[:300]}")
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    return
                obj = json.loads(data)
                if "error" in obj:
                    raise RuntimeError(obj["error"])
                delta = obj.get("delta")
                if delta:
                    yield delta
