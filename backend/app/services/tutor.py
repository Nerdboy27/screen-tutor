"""Conversation orchestration: sessions, visual context and the model call."""

from __future__ import annotations

import base64
import binascii
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Session, Turn, utcnow
from app.plugins.base import CaptureEvent, ReplyEvent
from app.plugins.registry import PluginRegistry
from app.schemas import TurnRead, TutorReply
from app.services.events import EventHub
from app.services.gemini import GeminiClient, ImagePart, Message, TextPart
from app.services.visual_context import VisualContext, VisualContextStore

# Number of past turns replayed to the model for conversational continuity.
HISTORY_TURNS = 8

HTTP_422_UNPROCESSABLE = 422
HTTP_413_TOO_LARGE = 413

IMPLICIT_CAPTURE_PROMPT = (
    "Explain what is on this screen right now, following your tutor instructions."
)


class TutorService:
    def __init__(
        self,
        db: AsyncSession,
        gemini: GeminiClient,
        contexts: VisualContextStore,
        registry: PluginRegistry,
        hub: EventHub,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._gemini = gemini
        self._contexts = contexts
        self._registry = registry
        self._hub = hub
        self._settings = settings or get_settings()

    async def get_session(self, session_id: str) -> Session:
        session = await self._db.get(Session, session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        return session

    async def create_session(self, *, title: str, client: str) -> Session:
        session = Session(title=title, client=client)
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def list_sessions(self, limit: int, offset: int) -> list[Session]:
        result = await self._db.execute(
            select(Session)
            .order_by(Session.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars())

    async def close_session(self, session_id: str) -> Session:
        session = await self.get_session(session_id)
        session.closed_at = utcnow()
        await self._db.commit()
        await self._contexts.discard(session_id)
        await self._db.refresh(session)
        return session

    async def delete_session(self, session_id: str) -> None:
        session = await self.get_session(session_id)
        await self._contexts.discard(session_id)
        await self._db.delete(session)
        await self._db.commit()

    async def analyze_capture(
        self,
        *,
        session_id: str | None,
        image_base64: str,
        mime_type: str,
        prompt: str | None,
        source: str,
    ) -> TutorReply:
        raw_size = _validate_image(image_base64, self._settings.max_image_bytes)
        width, height = _image_dimensions(image_base64, mime_type)

        session = (
            await self.get_session(session_id)
            if session_id
            else await self.create_session(title="Screen capture", client=source)
        )

        await self._registry.dispatch_capture(
            CaptureEvent(
                session_id=session.id,
                prompt=prompt,
                source=source,
                mime_type=mime_type,
                width=width,
                height=height,
            )
        )

        context = await self._contexts.set(
            session.id,
            image_base64=image_base64,
            mime_type=mime_type,
            width=width,
            height=height,
        )
        # The caller's copy is released here; only the TTL bound store holds it.
        del image_base64

        user_text = prompt or IMPLICIT_CAPTURE_PROMPT
        await self._record_turn(
            session,
            role="user",
            text=user_text,
            source=source,
            width=width,
            height=height,
        )

        history = await self._history(session.id)
        messages = history + [
            Message(
                role="user",
                parts=[
                    ImagePart(
                        data_base64=context.image_base64, mime_type=context.mime_type
                    ),
                    TextPart(text=user_text),
                ],
            )
        ]

        return await self._respond(
            session=session,
            messages=messages,
            prompt=prompt,
            source=source,
            used_visual_context=True,
            context=context,
            raw_size=raw_size,
        )

    async def follow_up(
        self, *, session_id: str, prompt: str, source: str
    ) -> TutorReply:
        session = await self.get_session(session_id)
        context = await self._contexts.get(session_id)

        await self._record_turn(session, role="user", text=prompt, source=source)

        history = await self._history(session.id)
        parts: list[ImagePart | TextPart] = []
        if context is not None:
            parts.append(
                ImagePart(data_base64=context.image_base64, mime_type=context.mime_type)
            )
        parts.append(TextPart(text=prompt))
        messages = history + [Message(role="user", parts=parts)]

        return await self._respond(
            session=session,
            messages=messages,
            prompt=prompt,
            source=source,
            used_visual_context=context is not None,
            context=context,
            raw_size=None,
        )

    async def _respond(
        self,
        *,
        session: Session,
        messages: list[Message],
        prompt: str | None,
        source: str,
        used_visual_context: bool,
        context: VisualContext | None,
        raw_size: int | None,
    ) -> TutorReply:
        started = time.perf_counter()
        reply_text = await self._gemini.generate(messages)
        latency_ms = int((time.perf_counter() - started) * 1000)
        messages.clear()

        metadata = {"bytes": str(raw_size)} if raw_size is not None else {}
        reply_text = await self._registry.dispatch_reply(
            ReplyEvent(
                session_id=session.id,
                prompt=prompt,
                reply=reply_text,
                source=source,
                used_visual_context=used_visual_context,
                latency_ms=latency_ms,
                metadata=metadata,
            )
        )

        turn = await self._record_turn(
            session,
            role="tutor",
            text=reply_text,
            source=source,
            latency_ms=latency_ms,
        )
        turn_read = TurnRead.model_validate(turn)
        await self._hub.publish(
            session.id,
            {
                "type": "turn",
                "session_id": session.id,
                "turn": turn_read.model_dump(mode="json"),
            },
        )
        return TutorReply(
            session_id=session.id,
            turn=turn_read,
            model=self._gemini.model,
            used_visual_context=used_visual_context,
            visual_context_expires_at=_expires_at(context, self._contexts.ttl_seconds),
        )

    async def _record_turn(
        self,
        session: Session,
        *,
        role: str,
        text: str,
        source: str,
        width: int | None = None,
        height: int | None = None,
        latency_ms: int | None = None,
    ) -> Turn:
        turn = Turn(
            session_id=session.id,
            role=role,
            text=text,
            source=source,
            image_width=width,
            image_height=height,
            latency_ms=latency_ms,
        )
        self._db.add(turn)
        session.updated_at = utcnow()
        await self._db.commit()
        await self._db.refresh(turn)
        return turn

    async def _history(self, session_id: str) -> list[Message]:
        result = await self._db.execute(
            select(Turn)
            .where(Turn.session_id == session_id)
            .order_by(Turn.created_at.desc())
            .limit(HISTORY_TURNS + 1)
        )
        turns = list(result.scalars())[::-1][:-1]  # drop the just-recorded user turn
        return [
            Message(
                role="user" if turn.role == "user" else "model",
                parts=[TextPart(text=turn.text)],
            )
            for turn in turns
        ]


def _expires_at(context: VisualContext | None, ttl: int) -> datetime | None:
    if context is None:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=ttl)


def _validate_image(image_base64: str, max_bytes: int) -> int:
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="image_base64 is not valid base64",
        ) from exc
    if not raw:
        raise HTTPException(status_code=HTTP_422_UNPROCESSABLE, detail="Empty image")
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=HTTP_413_TOO_LARGE,
            detail=f"Capture exceeds {max_bytes} bytes",
        )
    return len(raw)


def _image_dimensions(image_base64: str, mime_type: str) -> tuple[int | None, int | None]:
    """Read PNG dimensions from the header without decoding the pixels."""
    if mime_type != "image/png":
        return None, None
    try:
        header = base64.b64decode(image_base64[:64], validate=False)
    except (binascii.Error, ValueError):
        return None, None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width or None, height or None
