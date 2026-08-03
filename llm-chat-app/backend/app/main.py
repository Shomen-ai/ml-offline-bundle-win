"""Точка входа backend'а: FastAPI + статика собранного фронта."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import auth, chat, config, db

app = FastAPI(title="LLM Chat", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)


@app.on_event("startup")
def _startup():
    db.init_pool()


@app.on_event("shutdown")
def _shutdown():
    db.close_pool()


@app.get("/api/health")
def health():
    return {"ok": True}


# Если фронт собран (npm run build) — отдаём его этим же сервером,
# отдельный web-сервер на машине B не нужен. Роутер фронта — hash-режим,
# поэтому deep-link'и работают без fallback-магии.
if os.path.isdir(config.FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="spa")
