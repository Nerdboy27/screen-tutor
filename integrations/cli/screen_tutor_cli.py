#!/usr/bin/env python3
"""Headless CLI integration for the Screen-Aware AI Tutor.

Examples
--------
    screen-tutor-cli capture                     # grab the screen and explain it
    screen-tutor-cli ask "why is this O(n^2)?"   # follow-up in the last session
    screen-tutor-cli sessions                    # list recent sessions
    cat diagram.png | screen-tutor-cli capture --stdin
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import httpx

STATE_PATH = Path.home() / ".cache" / "screen-tutor" / "cli-state.json"


def _headers() -> dict[str, str]:
    headers = {"content-type": "application/json"}
    key = os.environ.get("TUTOR_API_KEY", "")
    if key:
        headers["x-api-key"] = key
    return headers


def _base_url() -> str:
    return os.environ.get("TUTOR_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _load_session() -> str | None:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text()).get("session_id")
    return None


def _store_session(session_id: str) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"session_id": session_id}))


def _post(path: str, payload: dict[str, object]) -> dict[str, object]:
    response = httpx.post(
        f"{_base_url()}{path}", json=payload, headers=_headers(), timeout=60.0
    )
    response.raise_for_status()
    return response.json()


def cmd_capture(args: argparse.Namespace) -> int:
    if args.stdin:
        image_bytes = sys.stdin.buffer.read()
        mime_type = args.mime_type
    else:
        from tutor_desktop.capture import grab_screen  # optional desktop dependency

        capture = grab_screen(monitor=args.monitor)
        image_bytes = base64.b64decode(capture.image_base64)
        capture.purge()
        mime_type = capture.mime_type

    body = _post(
        "/analyze",
        {
            "session_id": None if args.new_session else _load_session(),
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "mime_type": mime_type,
            "prompt": args.prompt,
            "source": "cli",
        },
    )
    _store_session(str(body["session_id"]))
    print(body["turn"]["text"])  # type: ignore[index]
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    session_id = args.session_id or _load_session()
    if not session_id:
        print("No active session. Run 'capture' first.", file=sys.stderr)
        return 2
    body = _post(
        f"/sessions/{session_id}/follow-up",
        {"prompt": args.prompt, "source": "cli"},
    )
    print(body["turn"]["text"])  # type: ignore[index]
    return 0


def cmd_sessions(_: argparse.Namespace) -> int:
    response = httpx.get(f"{_base_url()}/sessions", headers=_headers(), timeout=30.0)
    response.raise_for_status()
    for session in response.json():
        print(f"{session['id']}  {session['updated_at']}  {session['title']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="screen-tutor-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="Analyze the screen or piped image")
    capture.add_argument("--prompt", default=None)
    capture.add_argument("--monitor", type=int, default=0)
    capture.add_argument("--stdin", action="store_true", help="Read image from stdin")
    capture.add_argument("--mime-type", default="image/png")
    capture.add_argument("--new-session", action="store_true")
    capture.set_defaults(func=cmd_capture)

    ask = sub.add_parser("ask", help="Follow-up bound to the last visual context")
    ask.add_argument("prompt")
    ask.add_argument("--session-id", default=None)
    ask.set_defaults(func=cmd_ask)

    sessions = sub.add_parser("sessions", help="List recent sessions")
    sessions.set_defaults(func=cmd_sessions)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
