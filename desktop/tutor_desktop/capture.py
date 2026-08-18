"""Zero-disk screen capture.

``mss`` grabs raw framebuffer pixels, Pillow downscales and encodes them, and the
result is base64 encoded in a ``BytesIO`` buffer. Nothing is written to disk, and
every intermediate buffer is closed before the function returns.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO

import mss
from PIL import Image


@dataclass(slots=True)
class Capture:
    image_base64: str
    mime_type: str
    width: int
    height: int
    byte_size: int

    def purge(self) -> None:
        """Drop the encoded payload once it has been transmitted."""
        self.image_base64 = ""


def grab_screen(
    *,
    monitor: int = 0,
    image_format: str = "png",
    max_width: int = 1920,
    jpeg_quality: int = 85,
) -> Capture:
    with mss.mss() as sct:
        monitors = sct.monitors
        index = monitor if 0 <= monitor < len(monitors) else 0
        raw = sct.grab(monitors[index])
        image = Image.frombytes("RGB", raw.size, raw.rgb)

    try:
        if max_width and image.width > max_width:
            height = round(image.height * max_width / image.width)
            image = image.resize((max_width, height), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        if image_format.lower() in {"jpg", "jpeg"}:
            image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
            mime_type = "image/jpeg"
        else:
            image.save(buffer, format="PNG", optimize=False, compress_level=6)
            mime_type = "image/png"

        payload = buffer.getvalue()
        buffer.close()
        return Capture(
            image_base64=base64.b64encode(payload).decode("ascii"),
            mime_type=mime_type,
            width=image.width,
            height=image.height,
            byte_size=len(payload),
        )
    finally:
        image.close()
