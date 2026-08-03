# SkyFleet Ops — AI Drone Delivery Command Center

## Project Specification

## 1. Vision

SkyFleet Ops is a real-time operations console for a simulated last-mile drone delivery fleet. It streams live telemetry for a fleet of delivery drones, lets a dispatcher launch and monitor delivery missions against a shared energy budget, and integrates an LLM "flight director" that can analyze fleet health and dispatch missions on the dispatcher's behalf. It looks and feels like a modern air-traffic-control console with an AI copilot.

This is a demonstration capstone for an agentic AI coding course. It is built by orchestrated coding agents working from a shared specification in `planning/`, showing how independent frontend/backend workstreams can be developed against a common contract.

## 2. User Experience

### First Launch

The dispatcher runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A fleet roster of 10 default drones with live-updating telemetry in a grid
- A 500 kWh energy budget for launching new missions
- A dark, data-dense ops-console aesthetic
- An AI flight-director chat panel ready to assist

### What the Dispatcher Can Do

- **Watch telemetry stream** — battery levels flash amber (draining fast) or green (charging/stable) with subtle CSS animations that fade
- **View battery sparklines** — per-drone battery history beside each roster row, accumulated on the frontend from the SSE stream since page load
- **Click a drone** to see a larger detail panel — battery, altitude, speed, and current mission
- **Launch and recall missions** — pick a drone and a delivery zone, launch instantly, no fees, no confirmation dialog
- **Monitor fleet health** — a heatmap (treemap) showing drones sized by mission value and colored by battery health, plus an energy-budget chart tracking remaining kWh over time
- **View a missions table** — drone, zone, distance, energy cost, status, ETA
- **Chat with the AI flight director** — ask about fleet status, get recommendations, and have the AI launch/recall missions through natural language
- **Manage the fleet roster** — add/remove drones manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0a0e14` or `#12161f`, muted slate borders, no pure black
- **Telemetry flash animations**: brief amber/green background highlight on battery change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by ATC / mission-control consoles — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Amber: `#f2a900`
- Teal Primary: `#17a2b8`
- Signal Orange: `#e8622c` (launch/dispatch actions)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: fleet telemetry simulation     │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `database/skyfleet.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → OpenRouter (Cerebras for fast inference), with structured outputs for mission dispatch
- **Telemetry**: Environment-variable driven — simulator by default, real telemetry via a MAVLink gateway bridge if configured

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-tenant = no need for a database server; self-contained, zero config |
| Single Docker container | Operators run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Mission launches are atomic | Eliminates partial dispatch, en-route re-routing, and multi-leg logic — dramatically simpler fleet math |

---

## 4. Directory Structure

```
skyfleet-ops/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── app/db/               # Schema definitions, seed data, migration logic
├── database/                 # Runtime volume mount target (SQLite file lives here)
│   └── .gitkeep               # Directory exists in repo; skyfleet.db is gitignored
├── planning/                  # Project-wide documentation for agents
│   ├── PLAN.md                # This document
│   └── ...                    # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh           # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh            # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1      # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1       # Stop Docker container (Windows PowerShell)
├── docker/
│   ├── Dockerfile             # Multi-stage build (Node → Python)
│   └── docker-compose.yml     # Optional convenience wrapper
├── tests/                     # Playwright E2E tests + docker-compose.test.yml
├── .env                       # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, telemetry, and LLM integration. Internal structure is up to the Backend/Telemetry agents.
- **`backend/app/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`database/`** at the top level is the runtime volume mount point. The SQLite file (`database/skyfleet.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`tests/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.
- **`docker/`** contains the Dockerfile and compose files, kept separate from application code.

---

## 5. Environment Variables

```bash
# Required: OpenRouter API key for LLM chat functionality
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: MAVLink telemetry gateway URL for real drone hardware
# If not set, the built-in fleet simulator is used (recommended for most users)
MAVLINK_GATEWAY_URL=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MAVLINK_GATEWAY_URL` is set and non-empty → backend polls the MAVLink gateway bridge for real telemetry
- If `MAVLINK_GATEWAY_URL` is absent or empty → backend uses the built-in fleet simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

---

## 6. Fleet Telemetry

### Two Implementations, One Interface

Both the simulator and the MAVLink gateway client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, telemetry cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates battery/altitude/speed using a mean-reverting (Ornstein-Uhlenbeck-style) drain model with configurable drain rate and volatility per drone
- Updates at ~500ms intervals
- Correlated moves within a squadron (e.g., drones flying the same weather cell drain together)
- Occasional random "wind gust" events — sudden extra battery drain on a drone for drama
- Starts from realistic seed telemetry (e.g., FALCON-01 at 95% battery, cruising altitude 120m)
- Runs as an in-process background task — no external dependencies

### MAVLink Gateway (Optional)

- REST polling of a MAVLink bridge service (not a raw MAVLink socket) — simpler, works behind any network boundary
- Polls for the union of all fleet drones on a configurable interval
- Parses the bridge's JSON response into the same format as the simulator

### Shared Telemetry Cache

- A single background task (simulator or gateway poller) writes to an in-memory telemetry cache
- The cache holds the latest reading, previous reading, and timestamp for each drone
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-fleet scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/telemetry`
- Long-lived SSE connection; client uses native `EventSource` API
- Server pushes telemetry updates for all drones known to the system at a regular cadence (~500ms) — in the single-fleet model this is equivalent to the full roster
- Each SSE event contains drone_id, battery_pct, altitude_m, speed_kmh, status, timestamp, and battery direction
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include an `operator_id` column defaulting to `"default"`. This is hardcoded for now (single-operator) but enables future multi-tenant support without schema migration.

**operator_profile** — Operator state (energy budget)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `energy_budget_kwh` REAL (default: `500.0`)
- `created_at` TEXT (ISO timestamp)

**fleet_roster** — Drones the operator is tracking
- `id` TEXT PRIMARY KEY (UUID)
- `operator_id` TEXT (default: `"default"`)
- `drone_id` TEXT (e.g., `"FALCON-01"`)
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(operator_id, drone_id)`

**missions** — Active and historical delivery missions (one active row per in-flight drone)
- `id` TEXT PRIMARY KEY (UUID)
- `operator_id` TEXT (default: `"default"`)
- `drone_id` TEXT
- `zone` TEXT (delivery zone name)
- `distance_km` REAL
- `energy_cost_kwh` REAL
- `status` TEXT (`"en_route"`, `"delivered"`, `"recalled"`)
- `updated_at` TEXT (ISO timestamp)

**mission_log** — Mission history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `operator_id` TEXT (default: `"default"`)
- `drone_id` TEXT
- `action` TEXT (`"launch"` or `"recall"`)
- `zone` TEXT
- `energy_cost_kwh` REAL
- `executed_at` TEXT (ISO timestamp)

**budget_snapshots** — Remaining energy budget over time (for the budget chart). Recorded every 30 seconds by a background task, and immediately after each mission launch/recall.
- `id` TEXT PRIMARY KEY (UUID)
- `operator_id` TEXT (default: `"default"`)
- `remaining_kwh` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with the LLM flight director
- `id` TEXT PRIMARY KEY (UUID)
- `operator_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — missions launched/recalled, roster changes made; null for operator messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One operator profile: `id="default"`, `energy_budget_kwh=500.0`
- Ten fleet roster entries: FALCON-01 through FALCON-10

---

## 8. API Endpoints

### Telemetry
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/telemetry` | SSE stream of live drone telemetry updates |

### Fleet Operations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/fleet` | Current missions, energy budget, remaining kWh, active drone count |
| POST | `/api/fleet/missions` | Launch a mission: `{drone_id, zone, distance_km}` |
| DELETE | `/api/fleet/missions/{drone_id}` | Recall an in-flight drone |
| GET | `/api/fleet/history` | Energy-budget snapshots over time (for the budget chart) |

### Roster
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/roster` | Current fleet roster with latest telemetry |
| POST | `/api/roster` | Add a drone: `{drone_id}` |
| DELETE | `/api/roster/{drone_id}` | Remove a drone |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive a complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use the `cerebras` skill to call LiteLLM via OpenRouter to the `openrouter/openai/gpt-oss-120b` model with Cerebras as the inference provider. Structured Outputs should be used to interpret the results.

There is an `OPENROUTER_API_KEY` in the `.env` file in the project root.

### How It Works

When the operator sends a chat message, the backend:

1. Loads the current fleet context (energy budget, active missions, roster with live telemetry, total fleet battery health)
2. Loads recent conversation history from the `chat_messages` table
3. Constructs a prompt with a system message, fleet context, conversation history, and the operator's new message
4. Calls the LLM via LiteLLM → OpenRouter, requesting structured output, using the cerebras-inference skill
5. Parses the complete structured JSON response
6. Auto-executes any mission launches/recalls or roster changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — Cerebras inference is fast enough that a loading indicator is sufficient)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the operator",
  "missions": [
    {"drone_id": "FALCON-03", "action": "launch", "zone": "Riverside", "distance_km": 4.2}
  ],
  "roster_changes": [
    {"drone_id": "FALCON-11", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the operator
- `missions` (optional): Array of mission actions to auto-execute. Each goes through the same validation as manual dispatch (sufficient energy budget for launches, drone must be in flight for recalls)
- `roster_changes` (optional): Array of fleet roster modifications

### Auto-Execution

Missions specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with virtual drones and budget, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a mission fails validation (e.g., insufficient energy budget), the error is included in the chat response so the LLM can inform the operator.

### System Prompt Guidance

The LLM should be prompted as "SkyFleet flight director, an AI fleet operations assistant" with instructions to:
- Analyze fleet battery health, mission load, and remaining energy budget
- Suggest mission launches/recalls with reasoning
- Execute missions when the operator asks or agrees
- Manage the fleet roster proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, ops-console-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Fleet roster panel** — grid/table of tracked drones with: drone ID, battery % (flashing amber/green on change), altitude, speed, status, and a sparkline mini-chart (accumulated from SSE since page load)
- **Main detail panel** — larger view for the currently selected drone, with at minimum battery over time. Clicking a drone in the roster selects it here.
- **Fleet heatmap** — treemap visualization where each rectangle is a drone, sized by mission energy cost, colored by battery health (green = healthy, red = critical)
- **Energy-budget chart** — line chart showing remaining kWh over time, using data from `budget_snapshots`
- **Missions table** — tabular view of all missions: drone, zone, distance, energy cost, status, ETA
- **Dispatch bar** — simple input area: drone field, zone field, distance field, launch button, recall button. Instant dispatch, no confirmation.
- **AI flight director panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Mission launches and roster changes shown inline as confirmations.
- **Header** — remaining energy budget (updating live), connection status indicator, active mission count

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/telemetry`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Telemetry flash effect: on receiving a new reading, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v skyfleet-data:/app/database -p 8000:8000 --env-file .env skyfleet-ops
```

The `database/` directory in the project root maps to `/app/database` in the container. The backend writes `skyfleet.db` to this path.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Telemetry: simulator generates valid readings, OU-drain math is correct, MAVLink gateway response parsing works, both implementations conform to the abstract interface
- Fleet operations: mission launch/recall logic, energy budget calculations, edge cases (launching with insufficient budget, recalling a drone not in flight)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, mission validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Telemetry flash animation triggers correctly on battery change
- Roster CRUD operations
- Fleet display calculations
- Chat message rendering and loading state

### E2E Tests (in `tests/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `tests/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default roster appears, 500 kWh budget shown, telemetry is streaming
- Add and remove a drone from the roster
- Launch a mission: energy budget decreases, mission appears, fleet updates
- Recall a mission: drone returns to base, mission status updates
- Fleet visualization: heatmap renders with correct colors, budget chart has data points
- AI chat (mocked): send a message, receive a response, mission dispatch appears inline
- SSE resilience: disconnect and verify reconnection
