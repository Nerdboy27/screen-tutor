from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from tutor_desktop import capture as capture_module


class _FakeShot:
    def __init__(self, width: int, height: int) -> None:
        self.size = (width, height)
        self.rgb = bytes([200, 200, 200]) * (width * height)


class _FakeMss:
    monitors = [{"left": 0, "top": 0, "width": 3840, "height": 2160}]

    def __enter__(self) -> _FakeMss:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def grab(self, monitor: dict[str, int]) -> _FakeShot:
        return _FakeShot(monitor["width"], monitor["height"])


@pytest.fixture(autouse=True)
def fake_mss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_module.mss, "mss", lambda: _FakeMss())


def test_capture_downscales_and_encodes_png_in_memory() -> None:
    capture = capture_module.grab_screen(max_width=1280)
    assert capture.mime_type == "image/png"
    assert capture.width == 1280
    assert capture.height == 720
    decoded = base64.b64decode(capture.image_base64)
    with Image.open(BytesIO(decoded)) as image:
        assert image.size == (1280, 720)


def test_capture_supports_jpeg() -> None:
    capture = capture_module.grab_screen(image_format="jpeg", max_width=640)
    assert capture.mime_type == "image/jpeg"
    assert capture.byte_size > 0


def test_purge_clears_payload() -> None:
    capture = capture_module.grab_screen(max_width=320)
    capture.purge()
    assert capture.image_base64 == ""
