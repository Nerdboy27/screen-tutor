"""Example out-of-tree plugin: derives flashcards from each tutor reply."""

from __future__ import annotations

from typing import ClassVar

from app.plugins.base import BasePlugin, ReplyEvent
from fastapi import APIRouter


class FlashcardsPlugin(BasePlugin):
    name = "flashcards"
    version = "1.0.0"
    description = "Turns each tutor explanation into question/answer flashcards."
    capabilities: ClassVar[list[str]] = ["on_reply", "http"]

    def __init__(self) -> None:
        self._cards: dict[str, list[dict[str, str]]] = {}

    def router(self) -> APIRouter:
        router = APIRouter(tags=["plugin:flashcards"])

        @router.get("/cards/{session_id}")
        async def read_cards(session_id: str) -> list[dict[str, str]]:
            return self._cards.get(session_id, [])

        return router

    async def on_reply(self, event: ReplyEvent) -> None:
        question = event.prompt or "What is shown on the captured screen?"
        answer = event.reply.strip().split("\n\n")[0]
        self._cards.setdefault(event.session_id, []).append(
            {"question": question, "answer": answer}
        )


def plugin_factory() -> FlashcardsPlugin:
    return FlashcardsPlugin()
