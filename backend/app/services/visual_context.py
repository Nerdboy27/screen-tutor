"""In-memory, TTL bound store for the most recent capture of each session.

This is the only place a screen capture ever lives on the server. Entries are
purged on TTL expiry, on session close, and on process shutdown; nothing is
written to disk or to the database.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.config import get_settings


@dataclass(slots=True)
class VisualContext:
    image_base64: str
    mime_type: str
    width: int | None
    height: int | None
    expires_at: float = field(default=0.0)

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class VisualContextStore:
    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else get_settings().visual_context_ttl_seconds
        )
        self._entries: dict[str, VisualContext] = {}
        self._lock = asyncio.Lock()

    async def set(
        self,
        session_id: str,
        *,
        image_base64: str,
        mime_type: str,
        width: int | None,
        height: int | None,
    ) -> VisualContext:
        context = VisualContext(
            image_base64=image_base64,
            mime_type=mime_type,
            width=width,
            height=height,
            expires_at=time.monotonic() + self._ttl,
        )
        async with self._lock:
            self._purge_locked()
            self._entries[session_id] = context
        return context

    async def get(self, session_id: str) -> VisualContext | None:
        async with self._lock:
            self._purge_locked()
            return self._entries.get(session_id)

    async def discard(self, session_id: str) -> None:
        async with self._lock:
            self._drop_locked(session_id)

    async def clear(self) -> None:
        async with self._lock:
            for session_id in list(self._entries):
                self._drop_locked(session_id)

    def _purge_locked(self) -> None:
        for session_id, context in list(self._entries.items()):
            if context.expired:
                self._drop_locked(session_id)

    def _drop_locked(self, session_id: str) -> None:
        context = self._entries.pop(session_id, None)
        if context is not None:
            # Drop the only reference to the payload immediately.
            context.image_base64 = ""

    @property
    def ttl_seconds(self) -> int:
        return self._ttl


_store: VisualContextStore | None = None


def get_visual_context_store() -> VisualContextStore:
    global _store
    if _store is None:
        _store = VisualContextStore()
    return _store


def reset_visual_context_store() -> None:
    global _store
    _store = None
