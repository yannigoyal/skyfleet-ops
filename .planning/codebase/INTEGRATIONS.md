# External Integrations

**Analysis Date:** 2026-08-12

## APIs & External Services

**Telemetry Sources (pluggable):**
- MAVLink Gateway (optional, real hardware) — HTTP REST polling interface
  - When enabled: `MAVLINK_GATEWAY_URL` environment variable points to gateway bridge
  - Protocol: GET `{gateway_url}/telemetry?drones=FALCON-01,FALCON-02,...` returns JSON list of readings
  - Client: `httpx.AsyncClient` with 5.0s timeout in `backend/app/telemetry/mavlink_gateway.py`
  - Polling interval: 2.0s (configurable)
  - No auth required in current implementation (bridge-side responsibility)
  - Fallback: If URL not set or unreachable, simulator is used instead (graceful degradation)

- Fleet Simulator (default, no external dependency)
  - Built-in Python implementation using numpy Ornstein-Uhlenbeck model
  - No external service call; runs as in-process background task
  - Generates correlated battery drain, altitude, speed per drone
  - Updates at ~500ms intervals, writes to in-memory telemetry cache

**LLM Integration (planned, not yet implemented):**
- Provider: OpenRouter (cerebras skill)
  - Model: `openrouter/openai/gpt-oss-120b` on Cerebras inference
  - Auth: `OPENROUTER_API_KEY` environment variable
  - Client: LiteLLM SDK (to be added to dependencies)
  - Structured Outputs: JSON schema for mission dispatch actions
  - Mock mode: `LLM_MOCK=true` returns deterministic responses (E2E testing)
  - Endpoint: POST `/api/chat` (not yet implemented in `backend/app/missions/router.py`)

## Data Storage

**Databases:**
- SQLite (file-based, single writer)
  - Location: `database/skyfleet.db` (volume-mounted in Docker)
  - Connection: Python `sqlite3` standard library
  - Client: Custom async wrapper in `backend/app/db/connection.py` using asyncio locks
  - Mode: WAL (Write-Ahead Logging), foreign keys ON
  - Schema: `operator_profile`, `fleet_roster`, `missions`, `mission_log`, `budget_snapshots`, `chat_messages`
  - Initialization: Lazy creation on first request via `backend/app/db/schema.py` and `backend/app/db/seed.py`

**File Storage:**
- Local filesystem only
  - Frontend: Static files served from `static/` directory within Docker container (copy of Next.js export output)
  - Database: Mounted volume at `/app/database` in container → `database/` in project root

**Caching:**
- In-memory telemetry cache (no external service)
  - Location: `TelemetryCache` instance in `backend/app/telemetry/cache.py`
  - Holds: Latest reading, previous reading, timestamp per drone
  - Scope: Single backend process (not distributed)
  - Cleared on backend restart

## Authentication & Identity

**Auth Provider:**
- Custom (hardcoded single operator)
  - No login, no signup, no OAuth
  - All requests use operator_id = "default" (hardcoded in schema)
  - Future: Multi-tenant schema in place but not used (`operator_id` column on all tables)

**Credentials:**
- `OPENROUTER_API_KEY` — Future LLM integration; currently optional (not in use until chat implemented)
- No database credentials required (SQLite file-based)

## Monitoring & Observability

**Error Tracking:**
- None (not integrated)
- Errors logged to console via Python `logging` module
- Backend logs include telemetry updates, scheduler actions, API requests

**Logs:**
- Standard Python logging to stdout (inherited by Docker container)
- Log level: INFO by default, set in `backend/app/main.py:24`
- Key loggers:
  - `app.telemetry.simulator` — Telemetry updates, event triggers
  - `app.telemetry.mavlink_gateway` — MAVLink polling, errors, drone additions/removals
  - `app.missions.*` — Mission launches, recalls, scheduler activity
  - `app.db.*` — Database initialization
  - FastAPI default logger — HTTP requests (via uvicorn)

**Metrics:**
- None (not integrated)
- Budget snapshots recorded to database every 30s (for energy chart)

## CI/CD & Deployment

**Hosting:**
- Docker container, single image
- Runs locally: `docker run -v ./database:/app/database -p 8000:8000 --env-file .env skyfleet-ops`
- Tested targets: AWS App Runner, Render, any OCI-compatible container host
- No separate orchestration (single container, no docker-compose needed for production)

**CI Pipeline:**
- Not configured (no `.github/workflows` or similar)
- Optional: Add GitHub Actions for tests, linting, image build

**Start/Stop Scripts:**
- `scripts/start_mac.sh` — Wrapper around `docker run` with volume, port, env-file
- `scripts/stop_mac.sh` — Stops and removes container (volume persists)
- `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` — PowerShell equivalents

## Environment Configuration

**Required env vars:**
- `OPENROUTER_API_KEY` — Listed in `.env.example` but not currently used (LLM chat not yet implemented)

**Optional env vars:**
- `MAVLINK_GATEWAY_URL` — URL to MAVLink gateway bridge (if empty, simulator used)
- `LLM_MOCK` — Set to "true" for deterministic mock LLM responses (testing only, affects `/api/chat` when implemented)
- `DATABASE_PATH` — Override SQLite file location (defaults to `database/skyfleet.db`)

**Secrets location:**
- `.env` file in project root (gitignored)
- `.env.example` provides template (shared in repo)
- Mounted into Docker container via `--env-file .env` flag in start scripts

## Webhooks & Callbacks

**Incoming:**
- None at this time

**Outgoing:**
- None at this time
- Future: LLM chat could trigger outbound logging/monitoring if integrated

## Real-Time Communication

**Server → Client:**
- Server-Sent Events (SSE) for telemetry streaming
  - Endpoint: GET `/api/stream/telemetry`
  - Transport: HTTP long-poll with text/event-stream MIME type
  - Cadence: ~500ms per push (every telemetry update)
  - Content: `TelemetrySnapshot` JSON (all drones' latest readings)
  - Reconnection: Automatic via EventSource API (browser native)
  - No heartbeat; timeout determined by browser defaults

**Client → Server:**
- REST POST for mission dispatch, roster changes, chat
  - `/api/fleet/missions` — POST to launch mission
  - `/api/fleet/missions/{drone_id}` — DELETE to recall
  - `/api/roster` — POST to add drone, DELETE to remove
  - `/api/chat` — POST to send message (not yet implemented)

## Backend-to-Backend

**None at this time**
- Frontend talks only to backend (same origin, no cross-service calls)
- Backend may call MAVLink gateway if `MAVLINK_GATEWAY_URL` configured
- LLM integration will be via OpenRouter (when implemented)

## Data Contracts

**Telemetry Update Schema:**
```json
{
  "drone_id": "FALCON-01",
  "battery_pct": 87.5,
  "previous_battery_pct": 88.0,
  "altitude_m": 118.0,
  "speed_kmh": 41.2,
  "status": "in_flight",
  "timestamp": 1730000000.0,
  "battery_direction": "draining"
}
```

**Mission Dispatch Request:**
```json
{
  "drone_id": "FALCON-03",
  "zone": "Riverside",
  "distance_km": 4.2
}
```

**LLM Response Schema (planned):**
```json
{
  "message": "Launching FALCON-03 to Riverside...",
  "missions": [
    {"drone_id": "FALCON-03", "action": "launch", "zone": "Riverside", "distance_km": 4.2}
  ],
  "roster_changes": [
    {"drone_id": "FALCON-11", "action": "add"}
  ]
}
```

---

*Integration audit: 2026-08-12*
