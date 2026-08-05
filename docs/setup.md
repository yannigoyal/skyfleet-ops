# Local Setup

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (recommended path)
- Node.js 20+ and `npm` (for frontend-only dev)
- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/) (for backend-only dev)
- An OpenRouter API key ([openrouter.ai](https://openrouter.ai)) for the AI flight director chat

## 1. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set `OPENROUTER_API_KEY`. Leave `MAVLINK_GATEWAY_URL` empty to use the
built-in fleet simulator (the default, recommended for local dev). Set `LLM_MOCK=true`
to run without a real API key, using deterministic mock chat responses.

## 2. Run with Docker (recommended)

This builds the frontend, packages it with the backend, and serves everything from a
single container on port 8000.

```bash
docker build -f docker/Dockerfile -t skyfleet-ops .
docker run -v skyfleet-data:/app/database -p 8000:8000 --env-file .env skyfleet-ops
```

Open `http://localhost:8000`.

Or use the convenience scripts, which build the image if needed and start the container:

```bash
./scripts/start_mac.sh       # macOS/Linux
./scripts/stop_mac.sh        # stop the container (data persists)
```

```powershell
scripts\start_windows.ps1    # Windows PowerShell
scripts\stop_windows.ps1
```

Alternatively, use Docker Compose:

```bash
docker compose -f docker/docker-compose.yml up --build
```

The SQLite database persists in the `skyfleet-data` Docker volume across restarts.

## 3. Run without Docker (backend + frontend separately)

Useful when actively developing one side of the app with hot reload.

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

The backend reads `.env` from the project root and lazily creates/seeds
`database/skyfleet.db` on first request.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

This starts the Next.js dev server (default `http://localhost:3000`). API calls to
`/api/*` expect the backend running on port 8000 — configure a proxy or run both and
point requests accordingly, since the production build serves both from one origin.

## 4. Run tests

**Backend (pytest):**

```bash
cd backend
uv run pytest
```

**Frontend (vitest):**

```bash
cd frontend
npm test
```

**E2E (Playwright, via Docker Compose):**

```bash
docker compose -f tests/docker-compose.test.yml up --build --abort-on-container-exit
```

E2E tests run with `LLM_MOCK=true` for speed and determinism.

## Troubleshooting

- **Port 8000 already in use** — stop any other container/process on that port, or
  change the `-p` mapping (e.g. `-p 8001:8000`) and adjust the URL you open.
- **Chat returns errors** — confirm `OPENROUTER_API_KEY` is set in `.env`, or set
  `LLM_MOCK=true` to bypass the live LLM call.
- **Stale data** — the database persists in the `skyfleet-data` Docker volume. Remove it
  with `docker volume rm skyfleet-data` to reset to a fresh, reseeded database.
