"""Точка входа backend'а: FastAPI + статика собранного фронта."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # пул поднимаем один раз на процесс; init_oracle_client внутри —
    # операция разовая и повторного вызова не терпит
    db.init_pool()
    yield
    db.close_pool()


app = FastAPI(
    title="LLM Chat",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health():
    return {"ok": True}


# Если фронт собран (npm run build) — отдаём его этим же сервером,
# отдельный web-сервер на машине B не нужен. Роутер фронта — hash-режим,
# поэтому deep-link'и работают без fallback-магии.
if os.path.isdir(config.FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="spa")
