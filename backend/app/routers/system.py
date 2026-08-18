"""Health and plugin introspection."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.plugins.registry import get_plugin_registry
from app.schemas import HealthResponse, PluginInfo
from app.services.gemini import get_gemini_client

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        model=settings.gemini_model,
        gemini_configured=get_gemini_client().configured,
        plugins=[plugin.name for plugin in get_plugin_registry().plugins],
    )


@router.get("/plugins", response_model=list[PluginInfo])
async def list_plugins() -> list[PluginInfo]:
    return [
        PluginInfo(
            name=plugin.name,
            version=plugin.version,
            description=plugin.description,
            capabilities=list(plugin.capabilities),
        )
        for plugin in get_plugin_registry().plugins
    ]
