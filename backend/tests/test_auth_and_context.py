from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import dependencies
from app.config import get_settings
from app.plugins.registry import reset_plugin_registry
from app.services.visual_context import VisualContextStore


async def test_api_key_is_enforced_when_configured(
    tmp_path, monkeypatch: pytest.MonkeyPatch, fake_gemini
) -> None:
    monkeypatch.setenv("TUTOR_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path/'a.db'}")
    monkeypatch.setenv("TUTOR_API_KEYS", "secret-one,secret-two")
    get_settings.cache_clear()
    reset_plugin_registry()

    from app.main import create_app

    app = create_app()
    monkeypatch.setattr(dependencies, "get_gemini_client", lambda: fake_gemini)
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get("/sessions")).status_code == 401
            authorised = await client.get(
                "/sessions", headers={"x-api-key": "secret-two"}
            )
            assert authorised.status_code == 200

    get_settings.cache_clear()
    reset_plugin_registry()


async def test_visual_context_expires_and_is_zeroed() -> None:
    store = VisualContextStore(ttl_seconds=0)
    await store.set(
        "session", image_base64="AAAA", mime_type="image/png", width=1, height=1
    )
    assert await store.get("session") is None


async def test_visual_context_clear_drops_payloads() -> None:
    store = VisualContextStore(ttl_seconds=600)
    context = await store.set(
        "session", image_base64="AAAA", mime_type="image/png", width=1, height=1
    )
    await store.clear()
    assert context.image_base64 == ""
    assert await store.get("session") is None
