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


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str | None = None
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class LoadRequest(BaseModel):
    model: str


def _available_models() -> list[str]:
    if not os.path.isdir(MODELS_DIR):
        return []
    return sorted(f for f in os.listdir(MODELS_DIR) if f.lower().endswith(".gguf"))


def _ensure_loaded(model: str | None) -> None:
    """Грузит модель, если она ещё не загружена. Вызывать под _lock."""
    global _llama, _current
    names = _available_models()
    if not names:
        raise HTTPException(503, f"В {MODELS_DIR} нет ни одного .gguf")
    if model is None or model == "":
        model = _current or names[0]
    model = os.path.basename(model)  # никакой навигации по путям
    if model not in names:
        raise HTTPException(404, f"Модели {model} нет в {MODELS_DIR}")
    if _current == model and _llama is not None:
        return
    # выгружаем прежнюю, чтобы освободить VRAM
    if _llama is not None:
        _llama = None
        gc.collect()
    print(f"[llm] загружаю {model} (n_gpu_layers={N_GPU_LAYERS}, n_ctx={N_CTX})...")
    _llama = Llama(
        model_path=os.path.join(MODELS_DIR, model),
        n_gpu_layers=N_GPU_LAYERS,
        n_ctx=N_CTX,
        verbose=False,
    )
    _current = model
    print(f"[llm] {model} готова")


@app.get("/health")
def health():
    return {"ok": True, "loaded": _current}


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
        _ensure_loaded(req.model)
    return {"ok": True, "loaded": _current}


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
