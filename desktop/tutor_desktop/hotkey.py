"""Global hotkey listener built on pynput (X11, Windows and macOS)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)


class HotkeyListener:
    """Runs a global hotkey on its own daemon thread.

    ``combination`` uses pynput syntax, e.g. ``"<ctrl>+<shift>+<space>"``.
    """

    def __init__(self, combination: str, callback: Callable[[], None]) -> None:
        self._combination = combination
        self._callback = callback
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        if self._listener is not None:
            return
        self._listener = keyboard.GlobalHotKeys({self._combination: self._invoke})
        self._listener.daemon = True
        self._listener.start()
        logger.info("Global hotkey registered: %s", self._combination)

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def rebind(self, combination: str) -> None:
        self.stop()
        self._combination = combination
        self.start()

    def _invoke(self) -> None:
        try:
            self._callback()
        except Exception:  # noqa: BLE001 - never kill the listener thread
            logger.exception("Hotkey handler failed")
