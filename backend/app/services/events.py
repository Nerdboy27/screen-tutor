"""Fan-out hub that pushes session turns to dashboards and plugins over WS."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class EventHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, topic: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._subscribers[topic].add(websocket)

    async def unsubscribe(self, topic: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._subscribers[topic].discard(websocket)
            if not self._subscribers[topic]:
                self._subscribers.pop(topic, None)

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._subscribers.get(topic, ()))
            wildcard = list(self._subscribers.get("*", ()))
        for websocket in targets + wildcard:
            try:
                await websocket.send_json(message)
            except Exception:  # noqa: BLE001 - a dead socket must not break publish
                await self.unsubscribe(topic, websocket)


_hub: EventHub | None = None


def get_event_hub() -> EventHub:
    global _hub
    if _hub is None:
        _hub = EventHub()
    return _hub
