from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient

from app.services.gemini import ImagePart
from app.services.visual_context import get_visual_context_store


async def test_health_reports_plugins(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "study-notes" in body["plugins"]


async def test_analyze_creates_session_and_reads_png_dimensions(
    client: AsyncClient, png_base64: str
) -> None:
    response = await client.post(
        "/analyze", json={"image_base64": png_base64, "mime_type": "image/png"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["used_visual_context"] is True
    assert body["turn"]["role"] == "tutor"

    detail = await client.get(f"/sessions/{body['session_id']}")
    turns = detail.json()["turns"]
    assert [turn["role"] for turn in turns] == ["user", "tutor"]
    assert turns[0]["image_width"] == 320
    assert turns[0]["image_height"] == 200
    assert detail.json()["has_visual_context"] is True


async def test_follow_up_reuses_visual_context_without_reupload(
    client: AsyncClient, png_base64: str, fake_gemini
) -> None:
    session_id = (
        await client.post("/analyze", json={"image_base64": png_base64})
    ).json()["session_id"]

    response = await client.post(
        f"/sessions/{session_id}/follow-up", json={"prompt": "Why is it O(log n)?"}
    )
    assert response.status_code == 200
    assert response.json()["used_visual_context"] is True

    last_call = fake_gemini.calls[-1]
    image_parts = [part for part in last_call[-1].parts if isinstance(part, ImagePart)]
    assert len(image_parts) == 1
    # History is replayed as text only; the image is attached once, from memory.
    assert any(message.role == "model" for message in last_call[:-1])


async def test_visual_context_purge_endpoint(
    client: AsyncClient, png_base64: str
) -> None:
    session_id = (
        await client.post("/analyze", json={"image_base64": png_base64})
    ).json()["session_id"]

    assert await get_visual_context_store().get(session_id) is not None
    response = await client.delete(f"/sessions/{session_id}/visual-context")
    assert response.status_code == 204
    assert await get_visual_context_store().get(session_id) is None

    follow_up = await client.post(
        f"/sessions/{session_id}/follow-up", json={"prompt": "still there?"}
    )
    assert follow_up.json()["used_visual_context"] is False


async def test_capture_bytes_are_never_persisted(
    client: AsyncClient, png_base64: str
) -> None:
    session_id = (
        await client.post("/analyze", json={"image_base64": png_base64})
    ).json()["session_id"]
    detail = (await client.get(f"/sessions/{session_id}")).json()
    assert png_base64[:64] not in detail_text(detail)


def detail_text(detail: dict) -> str:
    return str(detail)


async def test_invalid_base64_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/analyze", json={"image_base64": "not-base64!!"})
    assert response.status_code == 422


async def test_oversized_capture_is_rejected(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "max_image_bytes", 10)
    payload = base64.b64encode(b"x" * 64).decode()
    response = await client.post("/analyze", json={"image_base64": payload})
    assert response.status_code == 413


async def test_plugin_route_exposes_notes(client: AsyncClient, png_base64: str) -> None:
    session_id = (
        await client.post("/analyze", json={"image_base64": png_base64})
    ).json()["session_id"]
    response = await client.get(f"/plugins/study-notes/notes/{session_id}")
    assert response.status_code == 200
    assert "binary search" in response.json()["markdown"]


async def test_unknown_session_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/sessions/does-not-exist/follow-up", json={"prompt": "hi"}
    )
    assert response.status_code == 404
