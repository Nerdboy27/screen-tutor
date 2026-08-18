# Deployment

## 0. Prerequisites

* Python 3.10+, Node 18+ (Node 20 recommended).
* A Google AI Studio API key with access to `gemini-1.5-flash`
  (<https://aistudio.google.com/app/apikey>).
* Linux desktop clients need X11/Wayland with an accessible input device for the
  global hotkey (`pip install evdev` build deps: `python3-dev`, `build-essential`).

## 1. Local development

```bash
git clone <this repo> && cd screen-tutor
python -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]" -e "desktop[dev]"
cp .env.example .env            # then set TUTOR_GEMINI_API_KEY

uvicorn app.main:app --app-dir backend --reload --port 8000
cd web && npm install && npm run dev
screen-tutor                     # third terminal, on the machine with a display
```

## 2. Docker Compose (backend + dashboard)

```bash
export TUTOR_GEMINI_API_KEY=...
export TUTOR_API_KEYS=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
docker compose up --build
```

* API: <http://localhost:8000> (`/docs` for OpenAPI)
* Dashboard: <http://localhost:3000>
* SQLite lives in the `tutor-data` volume; switch `TUTOR_DATABASE_URL` to
  `postgresql+asyncpg://…` and `pip install "screen-tutor-backend[postgres]"`
  for a managed database.

## 3. Production backend

Any ASGI host works. Behind a reverse proxy:

```bash
pip install "screen-tutor-backend" "uvicorn[standard]"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
```

Notes for multi-worker deployments:

* The visual-context store and the WebSocket hub are per-process. Either run a
  single worker per node with sticky sessions at the proxy, or terminate the
  desktop/web traffic for one session on one node. This is intentional: the
  capture must never leave process memory for a shared cache.
* Always set `TUTOR_API_KEYS` in production; empty means unauthenticated.
* Set `TUTOR_CORS_ORIGINS` to the dashboard origin only.
* Terminate TLS at the proxy and forward WebSocket upgrades for `/ws/*`.

systemd unit:

```ini
[Unit]
Description=Screen-Aware AI Tutor API
After=network.target

[Service]
User=tutor
WorkingDirectory=/opt/screen-tutor
EnvironmentFile=/etc/screen-tutor.env
ExecStart=/opt/screen-tutor/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Fly.io / Render / Railway: build the `backend/Dockerfile`, expose port 8000, set
`TUTOR_GEMINI_API_KEY`, `TUTOR_API_KEYS`, `TUTOR_CORS_ORIGINS`, and (for a managed
Postgres) `TUTOR_DATABASE_URL`.

## 4. Dashboard

```bash
cd web
NEXT_PUBLIC_API_BASE_URL=https://api.example.com \
NEXT_PUBLIC_API_KEY=<client key> \
npm run build && npm start
```

On Vercel set the same two environment variables in the project settings. The
dashboard is a thin client: it never handles image data.

## 5. Packaging the desktop client

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile \
  --name screen-tutor \
  --collect-all pynput --collect-all mss \
  desktop/tutor_desktop/__main__.py
```

* **Windows:** the resulting `screen-tutor.exe` needs no extra permissions.
* **macOS:** grant *Screen Recording* and *Accessibility* to the app bundle
  (System Settings → Privacy & Security), otherwise the hotkey and capture are
  silently blocked.
* **Linux:** X11 works out of the box. Under Wayland, run the client with
  `GDK_BACKEND=x11`/XWayland or use a portal-based capture backend.

First run:

```bash
screen-tutor --api-base-url https://api.example.com --api-key <client key> --save-config
```

## 6. Integrations

* **CLI:** `pip install -e "desktop"` then
  `TUTOR_API_BASE_URL=… python integrations/cli/screen_tutor_cli.py capture`.
* **Browser extension:** `chrome://extensions` → *Load unpacked* →
  `integrations/browser-extension`. Set the API base URL and key in
  `chrome.storage.sync` (`apiBaseUrl`, `apiKey`).
* **VS Code:** `cd integrations/vscode-extension && npm install && npm run compile`,
  then press F5 to launch the extension host, or `vsce package` to publish.
* **Custom plugin:** ship a package exposing a `screen_tutor.plugins` entry point
  and install it into the backend environment; the API mounts it on startup.

## 7. Operations checklist

* `GET /health` reports the environment, model, key presence and loaded plugins —
  wire it to your uptime probe.
* Rotate `TUTOR_API_KEYS` by adding the new key, redeploying clients, then
  dropping the old one (the setting accepts a comma separated list).
* Back up only the database: it contains text history, never captures.
* Gemini rate limits surface as HTTP 502 with the upstream message; the desktop
  overlay shows them inline.
