"""Reference plugin: exposes the last reply of a session as markdown notes.

It doubles as the smallest possible example of the plugin contract for browser,
CLI and IDE integrations.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.plugins.base import BasePlugin, ReplyEvent


class StudyNotesPlugin(BasePlugin):
    name = "study-notes"
    version = "1.0.0"
    description = "Keeps the latest tutor explanation per session as markdown."
    capabilities = ["on_reply", "http"]

    def __init__(self) -> None:
        self._notes: dict[str, str] = {}

    def router(self) -> APIRouter:
        router = APIRouter(tags=["plugin:study-notes"])

        @router.get("/notes/{session_id}")
        async def read_notes(session_id: str) -> dict[str, str]:
            note = self._notes.get(session_id)
            if note is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="No notes yet"
                )
            return {"session_id": session_id, "markdown": note}

        return router

    async def on_reply(self, event: ReplyEvent) -> None:
        heading = event.prompt or "Screen capture explanation"
        self._notes[event.session_id] = f"## {heading}\n\n{event.reply}\n"
        return None


def plugin_factory() -> StudyNotesPlugin:
    return StudyNotesPlugin()
