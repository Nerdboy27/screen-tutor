from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient

from app import dependencies
from app.config import get_settings
from app.plugins.registry import reset_plugin_registry
from app.services.gemini import GeminiClient, Message
from app.services.visual_context import reset_visual_context_store


class FakeGemini(GeminiClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[list[Message]] = []
        self.reply = "This screen shows a binary search implementation."

    @property
    def configured(self) -> bool:
        return True

    async def generate(self, messages: list[Message]) -> str:
        self.calls.append([Message(role=m.role, parts=list(m.parts)) for m in messages])
        return self.reply


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
async def client(
    tmp_path, monkeypatch: pytest.MonkeyPatch, fake_gemini: FakeGemini
) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv(
        "TUTOR_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'test.db'}"
    )
    monkeypatch.setenv("TUTOR_GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    reset_plugin_registry()
    reset_visual_context_store()

    from app.main import create_app  # imported late so settings are in place

    app = create_app()
    monkeypatch.setattr(dependencies, "get_gemini_client", lambda: fake_gemini)

    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http

    get_settings.cache_clear()
    reset_plugin_registry()
    reset_visual_context_store()


@pytest.fixture
def png_base64() -> str:
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (320, 200), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
