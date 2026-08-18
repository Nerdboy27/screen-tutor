"""API key authentication shared by every client surface."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import Settings, get_settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    settings: Settings = get_settings()
    if not settings.auth_required:
        return "anonymous"
    if x_api_key and any(
        secrets.compare_digest(x_api_key, key) for key in settings.api_keys
    ):
        return x_api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
    )
