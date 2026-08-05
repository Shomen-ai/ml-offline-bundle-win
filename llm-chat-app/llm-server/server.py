"""Отдельный сервер с нейронкой (llama.cpp, CUDA).

Поднимается отдельным процессом от backend'а:
    python server.py
Переменные окружения:
    MODELS_DIR    — папка с *.gguf (по умолчанию D:\\bundle\\models)
    N_GPU_LAYERS  — слоёв на GPU, -1 = все (по умолчанию -1)
    N_CTX         — размер контекста (по умолчанию 8192)
    LLM_HOST/LLM_PORT — где слушать (127.0.0.1:8001)

API:
    GET  /health  -> {"ok": true, "loaded": "имя или null"}
    GET  /models  -> {"models": [{"name","size_mb","loaded"}], "current": ...}
    POST /load    {"model": "file.gguf"} -> грузит модель (выгружая прежнюю)
    POST /chat    {"messages":[...], "model": "...", ...} -> SSE-стрим дельт

Зависимости — только из офлайн-бандла: fastapi, uvicorn, llama-cpp-python.
Генерация однопоточная (Lock): пока идёт один ответ, второй запрос ждёт.
"""
import gc
import json
import os
import threading

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from llama_cpp import Llama
from pydantic import BaseModel, Field

MODELS_DIR = os.environ.get("MODELS_DIR", r"D:\bundle\models")
N_GPU_LAYERS = int(os.environ.get("N_GPU_LAYERS", "-1"))
N_CTX = int(os.environ.get("N_CTX", "8192"))
HOST = os.environ.get("LLM_HOST", "127.0.0.1")
PORT = int(os.environ.get("LLM_PORT", "8001"))

app = FastAPI(title="LLM server")

_lock = threading.Lock()
_llama: Llama | None = None
_current: str | None = None
# параметры, с которыми модель реально загружена: их меняет админ-панель,
# и смена любого из них означает перезагрузку весов в VRAM
_current_n_ctx: int = N_CTX
_current_n_gpu_layers: int = N_GPU_LAYERS


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class LoadRequest(BaseModel):
    model: str
    # необязательные: пусто = оставить те, с которыми модель уже загружена
    n_ctx: int | None = Field(default=None, ge=512, le=131072)
    n_gpu_layers: int | None = Field(default=None, ge=-1, le=999)


def _available_models() -> list[str]:
    if not os.path.isdir(MODELS_DIR):
        return []
    return sorted(f for f in os.listdir(MODELS_DIR) if f.lower().endswith(".gguf"))


def _ensure_loaded(
    model: str | None, n_ctx: int | None = None, n_gpu_layers: int | None = None
) -> None:
    """Грузит модель, если она ещё не загружена. Вызывать под _lock.

    Смена n_ctx или n_gpu_layers требует перезагрузки весов так же,
    как смена самой модели: эти параметры задаются при создании Llama.
    """
    global _llama, _current, _current_n_ctx, _current_n_gpu_layers
    names = _available_models()
    if not names:
        raise HTTPException(503, f"В {MODELS_DIR} нет ни одного .gguf")
    if model is None or model == "":
        model = _current or names[0]
    model = os.path.basename(model)  # никакой навигации по путям
    if model not in names:
        raise HTTPException(404, f"Модели {model} нет в {MODELS_DIR}")

    want_n_ctx = _current_n_ctx if n_ctx is None else n_ctx
    want_n_gpu_layers = _current_n_gpu_layers if n_gpu_layers is None else n_gpu_layers
    same = (
        _current == model
        and _llama is not None
        and _current_n_ctx == want_n_ctx
        and _current_n_gpu_layers == want_n_gpu_layers
    )
    if same:
        return

    # выгружаем прежнюю, чтобы освободить VRAM
    if _llama is not None:
        _llama = None
        gc.collect()
    print(f"[llm] загружаю {model} (n_gpu_layers={want_n_gpu_layers}, n_ctx={want_n_ctx})...")
    _llama = Llama(
        model_path=os.path.join(MODELS_DIR, model),
        n_gpu_layers=want_n_gpu_layers,
        n_ctx=want_n_ctx,
        verbose=False,
    )
    _current = model
    _current_n_ctx = want_n_ctx
    _current_n_gpu_layers = want_n_gpu_layers
    print(f"[llm] {model} готова")


@app.get("/health")
def health():
    return {
        "ok": True,
        "loaded": _current,
        "n_ctx": _current_n_ctx,
        "n_gpu_layers": _current_n_gpu_layers,
    }


@app.get("/models")
def models():
    return {
        "models": [
            {
                "name": f,
                "size_mb": round(os.path.getsize(os.path.join(MODELS_DIR, f)) / 1e6),
                "loaded": f == _current,
            }
            for f in _available_models()
        ],
        "current": _current,
    }


@app.post("/load")
def load(req: LoadRequest):
    with _lock:
        _ensure_loaded(req.model, req.n_ctx, req.n_gpu_layers)
    return {
        "ok": True,
        "loaded": _current,
        "n_ctx": _current_n_ctx,
        "n_gpu_layers": _current_n_gpu_layers,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    def generate():
        with _lock:
            try:
                _ensure_loaded(req.model)
                stream = _llama.create_chat_completion(
                    messages=req.messages,
                    max_tokens=req.max_tokens,
                    temperature=req.temperature,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk["choices"][0].get("delta", {}).get("content")
                    if delta:
                        payload = json.dumps({"delta": delta}, ensure_ascii=False)
                        yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"
            except HTTPException as e:
                yield f"data: {json.dumps({'error': e.detail}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    print(f"[llm] MODELS_DIR = {MODELS_DIR}")
    print(f"[llm] доступные модели: {', '.join(_available_models()) or 'нет'}")
    uvicorn.run(app, host=HOST, port=PORT)
