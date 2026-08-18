"""Request and response contracts shared by every client and plugin."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    title: str = Field(default="Untitled session", max_length=200)
    client: str = Field(default="desktop", max_length=64)


class TurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "tutor"]
    text: str
    source: str
    image_width: int | None = None
    image_height: int | None = None
    latency_ms: int | None = None
    created_at: datetime


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    client: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None


class SessionDetail(SessionRead):
    turns: list[TurnRead] = Field(default_factory=list)
    has_visual_context: bool = False


class AnalyzeRequest(BaseModel):
    """A capture upload. ``image_base64`` is never persisted."""

    session_id: str | None = None
    image_base64: str = Field(min_length=1)
    mime_type: Literal["image/png", "image/jpeg", "image/webp"] = "image/png"
    prompt: str | None = Field(default=None, max_length=4000)
    source: str = Field(default="desktop", max_length=32)


class FollowUpRequest(BaseModel):
    """A text-only follow-up bound to the session's retained visual context."""

    prompt: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="desktop", max_length=32)


class TutorReply(BaseModel):
    session_id: str
    turn: TurnRead
    model: str
    used_visual_context: bool
    visual_context_expires_at: datetime | None = None


class PluginInfo(BaseModel):
    name: str
    version: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    model: str
    gemini_configured: bool
    plugins: list[str]
