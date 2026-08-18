"""Desktop client configuration (env + optional JSON file)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_ENV_VAR = "TUTOR_DESKTOP_CONFIG"
DEFAULT_CONFIG_PATH = Path.home() / ".config" / "screen-tutor" / "config.json"


@dataclass(slots=True)
class DesktopConfig:
    api_base_url: str = "http://127.0.0.1:8000"
    api_key: str = ""
    hotkey: str = "<ctrl>+<shift>+<space>"
    monitor: int = 0  # 0 = all monitors, 1..n = a specific monitor
    image_format: str = "png"
    jpeg_quality: int = 85
    max_width: int = 1920
    request_timeout: float = 45.0
    always_on_top: bool = True
    opacity: float = 0.96
    theme: dict[str, str] = field(
        default_factory=lambda: {
            "bg": "#0f1117",
            "panel": "#171a23",
            "fg": "#e6e8ef",
            "muted": "#8b90a1",
            "accent": "#6c8cff",
        }
    )

    @classmethod
    def load(cls, path: Path | None = None) -> DesktopConfig:
        config = cls()
        config_path = path or Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH))
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        env_map = {
            "api_base_url": "TUTOR_API_BASE_URL",
            "api_key": "TUTOR_API_KEY",
            "hotkey": "TUTOR_HOTKEY",
        }
        for attr, env in env_map.items():
            value = os.environ.get(env)
            if value:
                setattr(config, attr, value)

        monitor = os.environ.get("TUTOR_MONITOR")
        if monitor and monitor.isdigit():
            config.monitor = int(monitor)
        return config

    def save(self, path: Path | None = None) -> Path:
        config_path = path or Path(os.environ.get(CONFIG_ENV_VAR, DEFAULT_CONFIG_PATH))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "api_base_url": self.api_base_url,
            "api_key": self.api_key,
            "hotkey": self.hotkey,
            "monitor": self.monitor,
            "image_format": self.image_format,
            "max_width": self.max_width,
        }
        config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return config_path

    @property
    def mime_type(self) -> str:
        if self.image_format.lower() in {"jpg", "jpeg"}:
            return "image/jpeg"
        return "image/png"
