"""Application factory for the Screen-Aware AI Tutor API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import dispose_db, init_db
from app.plugins.builtin.study_notes import plugin_factory as study_notes_factory
from app.plugins.registry import get_plugin_registry
from app.routers import sessions, system, tutor, ws
from app.services.visual_context import get_visual_context_store

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    try:
        yield
    finally:
        # Never outlive the process with capture data in memory.
        await get_visual_context_store().clear()
        await dispose_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Privacy-first, screen-aware tutoring API. Captures are processed in "
            "memory and never persisted."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registry = get_plugin_registry()
    if not registry.plugins:
        registry.register(study_notes_factory())
        registry.discover()

    app.include_router(system.router)
    app.include_router(sessions.router)
    app.include_router(tutor.router)
    app.include_router(ws.router)
    registry.mount(app)

    return app


app = create_app()
