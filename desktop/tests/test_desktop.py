from __future__ import annotations

import json

import httpx
import pytest

from tutor_desktop import api_client
from tutor_desktop.api_client import ApiError, TutorApiClient
from tutor_desktop.config import DesktopConfig


def test_config_env_overrides_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"api_base_url": "http://file:8000", "monitor": 2}), encoding="utf-8"
    )
    monkeypatch.setenv("TUTOR_DESKTOP_CONFIG", str(path))
    monkeypatch.setenv("TUTOR_API_BASE_URL", "http://env:9000")

    config = DesktopConfig.load()
    assert config.api_base_url == "http://env:9000"
    assert config.monitor == 2


def test_config_roundtrip(tmp_path) -> None:
    config = DesktopConfig(api_base_url="http://x", hotkey="<ctrl>+<alt>+t")
    path = config.save(tmp_path / "c.json")
    reloaded = DesktopConfig.load(path)
    assert reloaded.hotkey == "<ctrl>+<alt>+t"
    assert reloaded.api_base_url == "http://x"


def test_mime_type_follows_format() -> None:
    assert DesktopConfig(image_format="jpeg").mime_type == "image/jpeg"
    assert DesktopConfig(image_format="png").mime_type == "image/png"


def test_analyze_sends_api_key_and_parses_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["json"] = dict(kwargs["json"])  # type: ignore[arg-type]
        captured["headers"] = kwargs["headers"]
        return httpx.Response(
            200,
            json={
                "session_id": "abc",
                "used_visual_context": True,
                "model": "gemini-1.5-flash",
                "turn": {"text": "Explanation", "latency_ms": 812},
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(api_client.httpx, "post", fake_post)
    client = TutorApiClient("http://api:8000/", api_key="k")
    reply = client.analyze(
        image_base64="AAAA", mime_type="image/png", session_id=None
    )

    assert captured["url"] == "http://api:8000/analyze"
    assert captured["headers"]["x-api-key"] == "k"  # type: ignore[index]
    assert reply.session_id == "abc"
    assert reply.latency_ms == 812
    assert reply.used_visual_context is True


def test_api_error_surfaces_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        return httpx.Response(503, text="no key", request=httpx.Request("POST", url))

    monkeypatch.setattr(api_client.httpx, "post", fake_post)
    with pytest.raises(ApiError, match="503"):
        TutorApiClient("http://api").follow_up(session_id="s", prompt="why?")


def test_payload_is_cleared_after_send(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client must not keep a reference to the capture after transmission."""
    sent: list[dict[str, object]] = []

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        sent.append(kwargs["json"])  # type: ignore[arg-type]
        return httpx.Response(
            200,
            json={"session_id": "s", "used_visual_context": True, "turn": {"text": "ok"}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(api_client.httpx, "post", fake_post)
    TutorApiClient("http://api").analyze(
        image_base64="AAAA", mime_type="image/png", session_id="s"
    )
    assert sent[0] == {}
