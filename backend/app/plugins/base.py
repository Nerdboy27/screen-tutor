"""Plugin contract.

Any surface (browser extension proxy, CLI, IDE plugin, custom tool) can extend
the tutor by implementing :class:`TutorPlugin`. Plugins observe the conversation
and may mount their own FastAPI routes on the core API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from fastapi import APIRouter


@dataclass(slots=True)
class CaptureEvent:
    session_id: str
    prompt: str | None
    source: str
    mime_type: str
    width: int | None
    height: int | None


@dataclass(slots=True)
class ReplyEvent:
    session_id: str
    prompt: str | None
    reply: str
    source: str
    used_visual_context: bool
    latency_ms: int
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class TutorPlugin(Protocol):
    name: str
    version: str
    description: str
    capabilities: list[str]

    def router(self) -> APIRouter | None:
        """Optional FastAPI router mounted under ``/plugins/<name>``."""

    async def on_capture(self, event: CaptureEvent) -> None:
        """Called after a capture is accepted, before the model call."""

    async def on_reply(self, event: ReplyEvent) -> str | None:
        """Called with the model reply. Return a string to rewrite it."""


class BasePlugin:
    """Convenience base with no-op hooks."""

    name = "base"
    version = "0.1.0"
    description = ""
    capabilities: list[str] = []

    def router(self) -> APIRouter | None:
        return None

    async def on_capture(self, event: CaptureEvent) -> None:
        return None

    async def on_reply(self, event: ReplyEvent) -> str | None:
        return None
