"""Live session stream for dashboards and plugins."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.events import get_event_hub

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/sessions/{session_id}")
async def session_stream(websocket: WebSocket, session_id: str) -> None:
    settings = get_settings()
    if settings.auth_required:
        key = websocket.query_params.get("api_key", "")
        if not any(secrets.compare_digest(key, valid) for valid in settings.api_keys):
            await websocket.close(code=4401)
            return

    hub = get_event_hub()
    await websocket.accept()
    await hub.subscribe(session_id, websocket)
    try:
        while True:
            # The stream is push only; reads keep the socket alive and detect close.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(session_id, websocket)
