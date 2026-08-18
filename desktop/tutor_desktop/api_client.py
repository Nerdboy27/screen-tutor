"""HTTP client for the tutor backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ApiError(RuntimeError):
    pass


@dataclass(slots=True)
class Reply:
    session_id: str
    text: str
    latency_ms: int | None
    used_visual_context: bool


class TutorApiClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: float = 45.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"content-type": "application/json"}
        if api_key:
            self._headers["x-api-key"] = api_key
        self._timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self._base_url}{path}",
                json=payload,
                headers=self._headers,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ApiError(f"Cannot reach the tutor API: {exc}") from exc
        finally:
            payload.clear()

        if response.status_code >= 400:
            raise ApiError(f"API error {response.status_code}: {response.text[:300]}")
        return response.json()

    def analyze(
        self,
        *,
        image_base64: str,
        mime_type: str,
        session_id: str | None,
        prompt: str | None = None,
    ) -> Reply:
        body = self._post(
            "/analyze",
            {
                "session_id": session_id,
                "image_base64": image_base64,
                "mime_type": mime_type,
                "prompt": prompt,
                "source": "desktop",
            },
        )
        return _to_reply(body)

    def follow_up(self, *, session_id: str, prompt: str) -> Reply:
        body = self._post(
            f"/sessions/{session_id}/follow-up",
            {"prompt": prompt, "source": "desktop"},
        )
        return _to_reply(body)

    def purge_visual_context(self, session_id: str) -> None:
        try:
            httpx.delete(
                f"{self._base_url}/sessions/{session_id}/visual-context",
                headers=self._headers,
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            pass


def _to_reply(body: dict[str, Any]) -> Reply:
    turn = body.get("turn", {})
    return Reply(
        session_id=body["session_id"],
        text=turn.get("text", ""),
        latency_ms=turn.get("latency_ms"),
        used_visual_context=bool(body.get("used_visual_context")),
    )
