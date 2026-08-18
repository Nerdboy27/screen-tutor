"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.plugins.registry import get_plugin_registry
from app.services.events import get_event_hub
from app.services.gemini import get_gemini_client
from app.services.tutor import TutorService
from app.services.visual_context import get_visual_context_store


async def get_tutor_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TutorService:
    return TutorService(
        db=db,
        gemini=get_gemini_client(),
        contexts=get_visual_context_store(),
        registry=get_plugin_registry(),
        hub=get_event_hub(),
    )


TutorServiceDep = Annotated[TutorService, Depends(get_tutor_service)]
