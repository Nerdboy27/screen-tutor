"""Runtime configuration for the Screen-Aware AI Tutor backend."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="TUTOR_", extra="ignore"
    )

    app_name: str = "Screen-Aware AI Tutor API"
    environment: str = "development"

    database_url: str = "sqlite+aiosqlite:///./tutor.db"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: float = 30.0

    # Comma separated list of client keys. Empty disables authentication, which
    # is only tolerated outside of production.
    api_keys_raw: str = Field(default="", validation_alias="TUTOR_API_KEYS")

    cors_origins_raw: str = Field(
        default="http://localhost:3000", validation_alias="TUTOR_CORS_ORIGINS"
    )

    # Visual context lives in process memory only and expires aggressively.
    visual_context_ttl_seconds: int = 900
    max_image_bytes: int = 12 * 1024 * 1024

    system_instruction: str = (
        "You are an expert, proactive academic and technical tutor. Analyze the "
        "provided high-resolution image immediately. Concisely explain the main "
        "educational concept, code segment, or problem visible without waiting "
        "for a question. Maintain this specific visual context in your immediate "
        "memory for follow-ups."
    )

    @property
    def api_keys(self) -> list[str]:
        return _split_csv(self.api_keys_raw)

    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.cors_origins_raw)

    @property
    def auth_required(self) -> bool:
        return bool(self.api_keys)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
