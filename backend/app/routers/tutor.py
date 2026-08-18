"""Capture analysis and context-bound follow-ups."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import TutorServiceDep
from app.schemas import AnalyzeRequest, FollowUpRequest, TutorReply
from app.security import require_api_key

router = APIRouter(tags=["tutor"], dependencies=[Depends(require_api_key)])


@router.post("/analyze", response_model=TutorReply)
async def analyze(payload: AnalyzeRequest, tutor: TutorServiceDep) -> TutorReply:
    """Accept an in-memory capture and return the tutor's proactive explanation."""
    return await tutor.analyze_capture(
        session_id=payload.session_id,
        image_base64=payload.image_base64,
        mime_type=payload.mime_type,
        prompt=payload.prompt,
        source=payload.source,
    )


@router.post("/sessions/{session_id}/follow-up", response_model=TutorReply)
async def follow_up(
    session_id: str, payload: FollowUpRequest, tutor: TutorServiceDep
) -> TutorReply:
    """Ask a text-only follow-up against the session's retained visual context."""
    return await tutor.follow_up(
        session_id=session_id, prompt=payload.prompt, source=payload.source
    )
