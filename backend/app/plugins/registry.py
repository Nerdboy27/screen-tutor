"""Plugin discovery and dispatch.

Plugins are discovered from the ``screen_tutor.plugins`` entry point group, so a
third-party package (VS Code bridge, CLI daemon, browser relay) only needs to be
installed in the same environment to extend the API.
"""

from __future__ import annotations

import logging
from importlib.metadata import entry_points

from fastapi import APIRouter, FastAPI

from app.plugins.base import CaptureEvent, ReplyEvent, TutorPlugin

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "screen_tutor.plugins"


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[TutorPlugin] = []

    @property
    def plugins(self) -> list[TutorPlugin]:
        return list(self._plugins)

    def register(self, plugin: TutorPlugin) -> None:
        if any(existing.name == plugin.name for existing in self._plugins):
            raise ValueError(f"Duplicate plugin name: {plugin.name}")
        self._plugins.append(plugin)

    def discover(self) -> None:
        for entry_point in entry_points(group=ENTRY_POINT_GROUP):
            try:
                factory = entry_point.load()
                plugin = factory()
                if not isinstance(plugin, TutorPlugin):
                    raise TypeError(f"{entry_point.name} is not a TutorPlugin")
                self.register(plugin)
            except Exception:  # noqa: BLE001 - a bad plugin must not kill the API
                logger.exception("Failed to load plugin %s", entry_point.name)

    def mount(self, app: FastAPI) -> None:
        for plugin in self._plugins:
            router: APIRouter | None = plugin.router()
            if router is not None:
                app.include_router(router, prefix=f"/plugins/{plugin.name}")

    async def dispatch_capture(self, event: CaptureEvent) -> None:
        for plugin in self._plugins:
            try:
                await plugin.on_capture(event)
            except Exception:  # noqa: BLE001
                logger.exception("Plugin %s failed in on_capture", plugin.name)

    async def dispatch_reply(self, event: ReplyEvent) -> str:
        reply = event.reply
        for plugin in self._plugins:
            try:
                rewritten = await plugin.on_reply(event)
            except Exception:  # noqa: BLE001
                logger.exception("Plugin %s failed in on_reply", plugin.name)
                continue
            if isinstance(rewritten, str) and rewritten.strip():
                reply = rewritten
                event.reply = reply
        return reply


_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reset_plugin_registry() -> None:
    global _registry
    _registry = None
