"""Borderless Tkinter overlay for the Screen-Aware AI Tutor.

Design notes:
* The UI thread never blocks: captures and HTTP calls run on a worker thread and
  post results back through a queue drained by ``after``.
* Capture is strictly opt-in - it only happens on the global hotkey or the
  in-window button. Nothing runs in the background.
* The encoded capture is purged from memory as soon as the request returns.
"""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import font as tkfont

from tutor_desktop.api_client import ApiError, Reply, TutorApiClient
from tutor_desktop.capture import Capture, grab_screen
from tutor_desktop.config import DesktopConfig
from tutor_desktop.hotkey import HotkeyListener

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UiEvent:
    kind: str  # "status" | "reply" | "error"
    text: str
    reply: Reply | None = None


class TutorOverlay:
    def __init__(
        self,
        config: DesktopConfig | None = None,
        client: TutorApiClient | None = None,
        capture_fn: Callable[..., Capture] | None = None,
    ) -> None:
        self.config = config or DesktopConfig.load()
        self.client = client or TutorApiClient(
            self.config.api_base_url, self.config.api_key, self.config.request_timeout
        )
        self._capture_fn = capture_fn or grab_screen
        self._events: queue.Queue[UiEvent] = queue.Queue()
        self._busy = threading.Event()
        self.session_id: str | None = None

        self.root = tk.Tk()
        self._build_ui()
        self.hotkey = HotkeyListener(self.config.hotkey, self.request_capture)

    # ---------------------------------------------------------------- UI setup
    def _build_ui(self) -> None:
        theme = self.config.theme
        root = self.root
        root.title("Screen-Aware AI Tutor")
        root.overrideredirect(True)
        root.attributes("-topmost", self.config.always_on_top)
        try:
            root.attributes("-alpha", self.config.opacity)
        except tk.TclError:  # pragma: no cover - platform dependent
            pass
        root.configure(bg=theme["bg"])
        root.geometry(self._initial_geometry())

        title_font = tkfont.Font(family="DejaVu Sans", size=11, weight="bold")
        body_font = tkfont.Font(family="DejaVu Sans", size=10)

        header = tk.Frame(root, bg=theme["panel"], height=36)
        header.pack(fill="x")
        header.bind("<Button-1>", self._start_drag)
        header.bind("<B1-Motion>", self._on_drag)

        title = tk.Label(
            header,
            text="AI Tutor",
            bg=theme["panel"],
            fg=theme["fg"],
            font=title_font,
            padx=12,
        )
        title.pack(side="left")
        title.bind("<Button-1>", self._start_drag)
        title.bind("<B1-Motion>", self._on_drag)

        tk.Button(
            header,
            text="✕",
            command=self.quit,
            bg=theme["panel"],
            fg=theme["muted"],
            bd=0,
            activebackground=theme["panel"],
            activeforeground=theme["fg"],
            padx=10,
        ).pack(side="right")

        tk.Button(
            header,
            text="Purge context",
            command=self.purge_context,
            bg=theme["panel"],
            fg=theme["muted"],
            bd=0,
            activebackground=theme["panel"],
            activeforeground=theme["fg"],
            padx=8,
        ).pack(side="right")

        self.status = tk.Label(
            root,
            text=f"Idle · press {self.config.hotkey} to capture",
            bg=theme["bg"],
            fg=theme["muted"],
            anchor="w",
            padx=12,
            pady=4,
            font=body_font,
        )
        self.status.pack(fill="x")

        body = tk.Frame(root, bg=theme["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.transcript = tk.Text(
            body,
            wrap="word",
            bg=theme["panel"],
            fg=theme["fg"],
            insertbackground=theme["fg"],
            bd=0,
            padx=12,
            pady=10,
            font=body_font,
            state="disabled",
        )
        self.transcript.pack(fill="both", expand=True, side="left")
        scrollbar = tk.Scrollbar(body, command=self.transcript.yview)
        scrollbar.pack(fill="y", side="right")
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.tag_configure("user", foreground=theme["accent"], spacing1=6)
        self.transcript.tag_configure("tutor", foreground=theme["fg"], spacing3=8)
        self.transcript.tag_configure("error", foreground="#ff6b6b")

        footer = tk.Frame(root, bg=theme["bg"])
        footer.pack(fill="x", padx=12, pady=(0, 12))
        self.entry = tk.Entry(
            footer,
            bg=theme["panel"],
            fg=theme["fg"],
            insertbackground=theme["fg"],
            bd=0,
            font=body_font,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        self.entry.bind("<Return>", lambda _event: self.send_follow_up())
        tk.Button(
            footer,
            text="Capture",
            command=self.request_capture,
            bg=theme["accent"],
            fg="#0b0d13",
            bd=0,
            padx=14,
            pady=6,
        ).pack(side="right")

        root.bind("<Escape>", lambda _event: self.hide())
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.after(100, self._drain_events)

    def _initial_geometry(self) -> str:
        width, height = 460, 560
        screen_w = self.root.winfo_screenwidth()
        return f"{width}x{height}+{max(screen_w - width - 40, 0)}+80"

    # ------------------------------------------------------------- interaction
    def _start_drag(self, event: tk.Event) -> None:
        self._drag_origin = (event.x_root, event.y_root)
        self._window_origin = (self.root.winfo_x(), self.root.winfo_y())

    def _on_drag(self, event: tk.Event) -> None:
        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]
        x, y = self._window_origin
        self.root.geometry(f"+{x + dx}+{y + dy}")

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()

    def hide(self) -> None:
        self.root.withdraw()

    def request_capture(self) -> None:
        """Opt-in capture: hides the overlay, grabs the screen, asks the tutor."""
        if self._busy.is_set():
            return
        self._busy.set()
        self._set_status("Capturing screen…")
        self.hide()
        self.root.update_idletasks()
        threading.Thread(target=self._capture_worker, daemon=True).start()

    def send_follow_up(self) -> None:
        prompt = self.entry.get().strip()
        if not prompt or self._busy.is_set():
            return
        self.entry.delete(0, "end")
        self._append("You", prompt, "user")
        if self.session_id is None:
            self._append(
                "Tutor", "Capture your screen first to start a session.", "error"
            )
            return
        self._busy.set()
        self._set_status("Thinking…")
        threading.Thread(
            target=self._follow_up_worker, args=(prompt,), daemon=True
        ).start()

    def purge_context(self) -> None:
        if self.session_id:
            self.client.purge_visual_context(self.session_id)
        self._set_status("Visual context purged")

    def quit(self) -> None:
        self.hotkey.stop()
        self.root.destroy()

    # ------------------------------------------------------------------ workers
    def _capture_worker(self) -> None:
        capture: Capture | None = None
        try:
            capture = self._capture_fn(
                monitor=self.config.monitor,
                image_format=self.config.image_format,
                max_width=self.config.max_width,
                jpeg_quality=self.config.jpeg_quality,
            )
            self._events.put(
                UiEvent("status", f"Sent {capture.width}×{capture.height} capture")
            )
            reply = self.client.analyze(
                image_base64=capture.image_base64,
                mime_type=capture.mime_type,
                session_id=self.session_id,
            )
            self._events.put(UiEvent("reply", reply.text, reply))
        except (ApiError, OSError) as exc:
            self._events.put(UiEvent("error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Capture failed")
            self._events.put(UiEvent("error", f"Unexpected failure: {exc}"))
        finally:
            if capture is not None:
                capture.purge()
            self._busy.clear()

    def _follow_up_worker(self, prompt: str) -> None:
        try:
            assert self.session_id is not None
            reply = self.client.follow_up(session_id=self.session_id, prompt=prompt)
            self._events.put(UiEvent("reply", reply.text, reply))
        except ApiError as exc:
            self._events.put(UiEvent("error", str(exc)))
        finally:
            self._busy.clear()

    def _drain_events(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _handle_event(self, event: UiEvent) -> None:
        if event.kind == "status":
            self._set_status(event.text)
            return
        if event.kind == "error":
            self._append("Tutor", event.text, "error")
            self._set_status("Error")
            self.show()
            return
        if event.reply is not None:
            self.session_id = event.reply.session_id
            latency = (
                f" · {event.reply.latency_ms} ms" if event.reply.latency_ms else ""
            )
            self._set_status(f"Ready{latency}")
        self._append("Tutor", event.text, "tutor")
        self.show()

    # ------------------------------------------------------------------ helpers
    def _append(self, speaker: str, text: str, tag: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{speaker}\n", (tag,))
        self.transcript.insert("end", f"{text}\n\n", (tag,))
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def run(self) -> None:
        self.hotkey.start()
        self.root.mainloop()
