"""Session history CRUD shared by the desktop client and the web dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.dependencies import TutorServiceDep
from app.schemas import SessionCreate, SessionDetail, SessionRead
from app.security import require_api_key
from app.services.visual_context import get_visual_context_store

router = APIRouter(
    prefix="/sessions", tags=["sessions"], dependencies=[Depends(require_api_key)]
)


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionCreate, tutor: TutorServiceDep) -> SessionRead:
    session = await tutor.create_session(title=payload.title, client=payload.client)
    return SessionRead.model_validate(session)


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    tutor: TutorServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[SessionRead]:
    sessions = await tutor.list_sessions(limit=limit, offset=offset)
    return [SessionRead.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionDetail)
async def read_session(session_id: str, tutor: TutorServiceDep) -> SessionDetail:
    session = await tutor.get_session(session_id)
    context = await get_visual_context_store().get(session_id)
    detail = SessionDetail.model_validate(session)
    detail.has_visual_context = context is not None
    return detail


@router.post("/{session_id}/close", response_model=SessionRead)
async def close_session(session_id: str, tutor: TutorServiceDep) -> SessionRead:
    session = await tutor.close_session(session_id)
    return SessionRead.model_validate(session)


@router.delete("/{session_id}/visual-context", status_code=status.HTTP_204_NO_CONTENT)
async def purge_visual_context(session_id: str, tutor: TutorServiceDep) -> Response:
    await tutor.get_session(session_id)
    await get_visual_context_store().discard(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str, tutor: TutorServiceDep) -> Response:
    await tutor.delete_session(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
