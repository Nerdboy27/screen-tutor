# Screen-Aware AI Tutor

A privacy-first tutoring system that explains whatever is on your screen. Press a
global hotkey, the desktop client grabs the screen entirely in memory, and Gemini
1.5 Flash returns a proactive explanation. Follow-up questions reuse the same
visual context — from the desktop overlay, the web dashboard, the CLI, a browser
extension, or VS Code — without re-uploading the image.

```
                    ┌──────────────────────┐
  hotkey ──────────▶│  Desktop client      │  mss + Pillow, zero-disk capture
                    │  (Tkinter overlay)   │
                    └──────────┬───────────┘
                               │ POST /analyze (base64, in memory)
 browser ext ─┐                ▼
 CLI ─────────┼──────▶┌──────────────────────┐   Gemini 1.5 Flash
 VS Code ─────┘       │  FastAPI core API    │──────────────────▶
                      │  sessions · plugins  │
                      └──────────┬───────────┘
                                 │ WebSocket /ws/sessions/{id}
                                 ▼
                      ┌──────────────────────┐
                      │  Next.js dashboard   │  history, live turns, purge
                      └──────────────────────┘
```

## Repository layout

| Path | What it is |
| --- | --- |
| `backend/` | FastAPI API: sessions, capture analysis, plugin registry, WebSocket stream |
| `backend/app/services/visual_context.py` | The only place a capture lives server-side: in-memory, TTL bound |
| `desktop/` | Borderless Tkinter overlay, global hotkey, in-memory `mss`/Pillow capture |
| `web/` | Next.js 14 dashboard (session history, live turns, context purge) |
| `integrations/cli/` | Headless CLI (`capture`, `ask`, `sessions`) |
| `integrations/browser-extension/` | Manifest V3 extension that analyses the visible tab |
| `integrations/vscode-extension/` | VS Code commands that explain the selection |
| `integrations/example-plugin/` | Out-of-tree plugin discovered via entry points |

## Privacy model

* **Opt-in only.** Capture happens on an explicit hotkey or button press. There is
  no background loop, no continuous streaming, and no telemetry.
* **Zero disk.** `mss` writes into a memory buffer, Pillow encodes into `BytesIO`,
  the client base64-encodes it and drops the reference after the HTTP call
  (`Capture.purge()`).
* **Server memory only.** The API keeps the latest capture per session in
  `VisualContextStore` with a TTL (default 15 min) so follow-ups don't need a
  re-upload. It is never written to the database or the filesystem, and is purged
  on TTL expiry, on `DELETE /sessions/{id}/visual-context`, on session close, and
  on shutdown.
* **History is text.** Only prompts, replies and capture dimensions are persisted.

## Quick start

```bash
# 1. Backend
python -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]"
export TUTOR_GEMINI_API_KEY=<your key>
uvicorn app.main:app --app-dir backend --reload      # http://127.0.0.1:8000/docs

# 2. Desktop client (needs a display session)
pip install -e "desktop[dev]"
screen-tutor --api-base-url http://127.0.0.1:8000    # Ctrl+Shift+Space to capture

# 3. Web dashboard
cd web && npm install && npm run dev                 # http://localhost:3000
```

Everything is also wired up in `docker-compose.yml` (backend + dashboard).

## Configuration

Backend, via env (prefix `TUTOR_`) or `.env` — see `.env.example`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TUTOR_GEMINI_API_KEY` | – | Google AI Studio key (required) |
| `TUTOR_GEMINI_MODEL` | `gemini-1.5-flash` | Model id |
| `TUTOR_API_KEYS` | – | Comma separated client keys; empty disables auth |
| `TUTOR_DATABASE_URL` | `sqlite+aiosqlite:///./tutor.db` | Any SQLAlchemy async URL |
| `TUTOR_VISUAL_CONTEXT_TTL_SECONDS` | `900` | How long a capture stays in memory |
| `TUTOR_MAX_IMAGE_BYTES` | `12582912` | Upload guard |
| `TUTOR_CORS_ORIGINS` | `http://localhost:3000` | Comma separated origins |

Desktop client, via `~/.config/screen-tutor/config.json`, `TUTOR_*` env vars, or
CLI flags (`--hotkey`, `--api-base-url`, `--api-key`, `--monitor`, `--save-config`).
Hotkeys use pynput syntax, e.g. `<ctrl>+<shift>+<space>` or `<cmd>+<alt>+t`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/analyze` | Analyze a capture; creates a session when `session_id` is null |
| `POST` | `/sessions/{id}/follow-up` | Text follow-up bound to the retained visual context |
| `GET` | `/sessions`, `/sessions/{id}` | History for the dashboard |
| `DELETE` | `/sessions/{id}/visual-context` | Purge the in-memory capture immediately |
| `GET` | `/health`, `/plugins` | Status and installed plugins |
| `WS` | `/ws/sessions/{id}` | Live turn stream |

## Writing a plugin

```python
from app.plugins.base import BasePlugin, ReplyEvent

class MyPlugin(BasePlugin):
    name = "my-plugin"
    version = "1.0.0"

    async def on_reply(self, event: ReplyEvent) -> str | None:
        return f"{event.reply}\n\n— reviewed by my-plugin"

def plugin_factory() -> MyPlugin:
    return MyPlugin()
```

Expose it under the `screen_tutor.plugins` entry point group (see
`integrations/example-plugin/pyproject.toml`) and install it next to the backend;
it is discovered at startup and its optional router is mounted at
`/plugins/<name>`. `integrations/` shows the same core API driven from a browser
extension, a CLI and VS Code.

## Tests and checks

```bash
pytest backend/tests desktop/tests
ruff check backend desktop
mypy backend/app desktop/tutor_desktop
cd web && npm run lint && npm run typecheck
```

Deployment (Docker, systemd, Fly/Render, Vercel, packaging the desktop app with
PyInstaller) is documented in [`DEPLOYMENT.md`](DEPLOYMENT.md).
