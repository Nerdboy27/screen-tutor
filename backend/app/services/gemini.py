"""Thin, low-latency Gemini 1.5 Flash client.

The REST surface is used directly instead of the vendor SDK so that requests are
a single streaming-capable HTTP round trip with no global client state, and so
the image bytes can be released the moment the request is serialised.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

from app.config import Settings, get_settings


class GeminiError(RuntimeError):
    pass


@dataclass(slots=True)
class ImagePart:
    data_base64: str
    mime_type: str


@dataclass(slots=True)
class TextPart:
    text: str


Part = ImagePart | TextPart


@dataclass(slots=True)
class Message:
    role: str  # "user" or "model"
    parts: list[Part]


def _serialise_part(part: Part) -> dict[str, object]:
    if isinstance(part, ImagePart):
        return {
            "inline_data": {"mime_type": part.mime_type, "data": part.data_base64}
        }
    return {"text": part.text}


class GeminiClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def model(self) -> str:
        return self._settings.gemini_model

    @property
    def configured(self) -> bool:
        return bool(self._settings.gemini_api_key)

    async def generate(self, messages: list[Message]) -> str:
        if not self.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Gemini API key is not configured (TUTOR_GEMINI_API_KEY)",
            )

        payload = {
            "system_instruction": {
                "parts": [{"text": self._settings.system_instruction}]
            },
            "contents": [
                {
                    "role": message.role,
                    "parts": [_serialise_part(part) for part in message.parts],
                }
                for message in messages
            ],
            "generationConfig": {
                "temperature": 0.4,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            },
        }

        url = (
            f"{self._settings.gemini_base_url}/models/"
            f"{self._settings.gemini_model}:generateContent"
        )
        timeout = httpx.Timeout(self._settings.gemini_timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    params={"key": self._settings.gemini_api_key},
                    json=payload,
                    headers={"content-type": "application/json"},
                )
        except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Gemini request timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini request failed: {exc}",
            ) from exc
        finally:
            payload.clear()

        if response.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Gemini error {response.status_code}: {response.text[:500]}",
            )

        return _extract_text(response.json())


def _extract_text(body: dict[str, object]) -> str:
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        feedback = body.get("promptFeedback")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini returned no candidates (feedback={feedback})",
        )
    first = candidates[0]
    if not isinstance(first, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Malformed Gemini candidate"
        )
    content = first.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Malformed Gemini content"
        )
    chunks = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    text = "\n".join(chunks).strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Gemini returned empty text"
        )
    return text


def get_gemini_client() -> GeminiClient:
    return GeminiClient()
