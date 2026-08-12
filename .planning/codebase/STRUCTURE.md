# Codebase Structure

**Analysis Date:** 2026-08-12

## Directory Layout

```
skyfleet-ops/
├── backend/                         # FastAPI Python project (uv-managed)
│   ├── app/                         # Application code (WORKDIR in Docker)
│   │   ├── main.py                  # FastAPI app entry point, lifespan, router registration
│   │   ├── db/                      # Database layer
│   │   │   ├── __init__.py          # Exports Database, ensure_initialized
│   │   │   ├── connection.py        # Database class: lazy init, asyncio.Lock, transaction()
│   │   │   ├── schema.py            # SQL DDL for all tables
│   │   │   └── seed.py              # Default operator profile and fleet roster
│   │   ├── telemetry/               # Real-time fleet telemetry subsystem
│   │   │   ├── __init__.py          # Exports TelemetryCache, TelemetrySource, create_telemetry_source, create_stream_router
│   │   │   ├── models.py            # TelemetryUpdate dataclass, STATUSES constants
│   │   │   ├── cache.py             # TelemetryCache: thread-safe in-memory store
│   │   │   ├── interface.py         # TelemetrySource abstract base class
│   │   │   ├── factory.py           # create_telemetry_source() — selects Simulator or MAVLink based on env
│   │   │   ├── simulator.py         # SimulatorTelemetrySource: Ornstein-Uhlenbeck drain model
│   │   │   ├── seed_fleet.py        # FALCON-01 through FALCON-10 seed telemetry and drain params
│   │   │   ├── mavlink_gateway.py   # MavlinkGatewayTelemetrySource: REST polling of MAVLink bridge
│   │   │   └── stream.py            # SSE router: GET /api/stream/telemetry endpoint, _generate_events()
│   │   ├── missions/                # Mission dispatch and lifecycle
│   │   │   ├── __init__.py          # Exports MissionQueue, create_missions_router, schedulers, service, repository
│   │   │   ├── models.py            # Mission dataclass, MissionError hierarchy, ENERGY_COST_PER_KM_KWH constant
│   │   │   ├── queue.py             # MissionQueue: pending/failed in-memory queues with entry tracking
│   │   │   ├── service.py           # launch_mission(), auto_assign_mission(), recall_mission(), find_eligible_drone()
│   │   │   ├── repository.py        # create_mission(), recall(), list_active_missions(), get_remaining_kwh() — all DB queries
│   │   │   ├── router.py            # FastAPI router: POST/DELETE /api/fleet/missions, GET /api/fleet/*, /api/fleet/history
│   │   │   └── scheduler.py         # run_assignment_scheduler(), run_delivery_scheduler(), run_budget_snapshot_loop()
│   │   ├── roster/                  # Roster management (empty — planned, TBD)
│   │   ├── chat/                    # LLM chat integration (empty — planned, TBD)
│   │   └── demo/                    # Demo/test utilities (internal use)
│   ├── tests/                       # pytest test suite
│   │   ├── telemetry/               # Telemetry tests: simulator, cache, SSE generation
│   │   ├── missions/                # Mission tests: service logic, launch/recall/budget, eligibility
│   │   ├── db/                      # Database tests: connection, schema, transactions
│   │   └── roster/                  # Roster tests (empty — TBD)
│   │   └── chat/                    # Chat tests (empty — TBD)
│   ├── pyproject.toml               # Python project config, dependencies, dev tools (pytest, ruff, etc.)
│   └── uv.lock                      # Locked dependency versions
│
├── frontend/                        # Next.js TypeScript project
│   ├── src/
│   │   ├── app/                     # Next.js App Router
│   │   │   ├── layout.tsx           # Root HTML layout, Tailwind dark theme
│   │   │   └── page.tsx             # Home page: Header, FleetRosterPanel, AI chat sidebar (placeholder)
│   │   ├── components/              # React components
│   │   │   ├── Header.tsx           # Top bar: energy budget, connection status, active mission count
│   │   │   ├── FleetRosterPanel.tsx # Grid/table of drones with latest telemetry, sparklines, selection
│   │   │   └── ConnectionDot.tsx    # Colored indicator: connected/reconnecting/disconnected
│   │   ├── lib/                     # Utilities and hooks
│   │   │   └── useTelemetryStream.ts # Custom hook: EventSource to /api/stream/telemetry, state management
│   │   ├── types/                   # TypeScript type definitions
│   │   │   └── telemetry.ts         # TelemetryUpdate, TelemetrySnapshot types
│   │   └── globals.css              # Tailwind CSS config, custom dark theme vars (ops-bg, ops-panel, ops-border)
│   ├── public/                      # Static assets (if any)
│   ├── out/                         # Next.js static export build output (served by FastAPI)
│   ├── next.config.ts               # Next.js config: output: 'export' for static generation
│   ├── tailwind.config.ts           # Tailwind CSS: dark theme, custom ops-console color palette
│   ├── tsconfig.json                # TypeScript config
│   └── package.json                 # Node.js dependencies, build scripts
│
├── database/                        # SQLite storage (runtime volume mount)
│   ├── .gitkeep                     # Directory marker for git (actual skyfleet.db is gitignored)
│   └── skyfleet.db                  # Created by backend on first run (not in repo)
│
├── docker/
│   ├── Dockerfile                   # Multi-stage: Node build frontend → Python build backend → serve both
│   └── docker-compose.yml           # Optional convenience wrapper (not required for single-container deployment)
│
├── tests/                           # Playwright E2E tests
│   ├── docker-compose.test.yml      # Compose config for E2E: app container + playwright browser
│   └── specs/                       # .spec.ts test files
│
├── scripts/
│   ├── start_mac.sh                 # Bash: build Docker image, run container with volume mount and env
│   ├── stop_mac.sh                  # Bash: stop and remove running container
│   ├── start_windows.ps1            # PowerShell: Windows equivalent of start_mac.sh
│   └── stop_windows.ps1             # PowerShell: Windows equivalent of stop_mac.sh
│
├── planning/                        # Project-wide documentation for coordinating agents
│   ├── PLAN.md                      # Complete specification (sections 1-12): vision, UX, architecture, API, DB schema, etc.
│   ├── TELEMETRY_SUMMARY.md         # Telemetry subsystem design and implementation notes
│   ├── archive/                     # Earlier design docs and decision records
│   └── codebase/                    # Codebase analysis docs (this directory — ARCHITECTURE.md, STRUCTURE.md, etc.)
│
├── docs/                            # Additional documentation (if any)
├── .env.example                     # Template for environment variables (committed)
├── .env                             # Actual env vars (gitignored — contains OPENROUTER_API_KEY)
├── .gitignore                       # Excludes node_modules, .env, database/skyfleet.db, etc.
├── CLAUDE.md                        # Project-level instructions for Claude (this project's conventions)
└── README.md                        # Quick-start guide for running the app
```

## Directory Purposes

**backend/**
- Purpose: FastAPI application serving HTTP API and static frontend files
- Contains: Python source code, tests, dependencies
- Key files: `app/main.py` (entry point), `app/db/schema.py` (database), `app/missions/router.py` (API routes)

**backend/app/db/**
- Purpose: SQLite initialization, schema, seed data, and connection pooling
- Contains: `connection.py` (Database class with asyncio.Lock), `schema.py` (CREATE TABLE statements), `seed.py` (default operator/roster)
- Key interaction: Initialized once in `main.py` lifespan; passed to routers and schedulers

**backend/app/telemetry/**
- Purpose: Real-time telemetry ingestion and streaming
- Contains: Abstract `TelemetrySource`, concrete implementations (Simulator, MAVLink Gateway), in-memory cache, SSE endpoint
- Key files: `simulator.py` (mean-reverting drain model), `cache.py` (thread-safe store), `stream.py` (SSE generation)

**backend/app/missions/**
- Purpose: Mission dispatch, lifecycle, and automatic assignment
- Contains: Validation logic (service.py), database queries (repository.py), HTTP routes (router.py), background schedulers
- Key files: `models.py` (Mission dataclass, error types), `service.py` (business logic), `scheduler.py` (auto-assignment + delivery)

**backend/tests/**
- Purpose: pytest test suite
- Contains: Tests for each subsystem (telemetry, missions, db); mirrors app/ structure
- Run: `uv run --extra dev pytest -v`

**frontend/**
- Purpose: Next.js static export; served as static files by FastAPI
- Contains: React components (TypeScript), custom hooks, Tailwind CSS
- Key files: `src/app/page.tsx` (home page), `src/lib/useTelemetryStream.ts` (SSE hook), `next.config.ts` (static export config)
- Build: `npm run build` → `out/` directory (copied into Docker image)

**database/**
- Purpose: Runtime persistent storage for SQLite
- Contains: `skyfleet.db` (created at runtime, gitignored)
- Docker: Mounted as `/app/database` volume for persistence across container restarts

**docker/**
- Purpose: Containerization configuration
- Contains: Dockerfile (multi-stage Node → Python), optional docker-compose.yml
- Key: Dockerfile copies frontend build output to `backend/static/`, then mounts it with FastAPI's `StaticFiles`

**tests/**
- Purpose: End-to-end browser automation tests
- Contains: Playwright test specs, docker-compose.test.yml
- Run: `docker-compose -f tests/docker-compose.test.yml up --abort-on-container-exit`

**scripts/**
- Purpose: Convenience wrappers for Docker build/run
- Contains: Shell and PowerShell scripts for macOS/Linux/Windows
- Key files: `start_mac.sh` (build, run, print URL), `stop_mac.sh` (stop container)

**planning/**
- Purpose: Shared specification and design docs for coordinating agents
- Contains: PLAN.md (complete spec), TELEMETRY_SUMMARY.md (subsystem notes), archive/ (history), codebase/ (analysis)

## Key File Locations

**Entry Points:**

| File | Role |
|------|------|
| `backend/app/main.py` | FastAPI app initialization, lifespan, router registration, static file serving |
| `frontend/src/app/page.tsx` | React home page, renders Header, FleetRosterPanel, AI chat sidebar |
| `frontend/src/app/layout.tsx` | Root layout: HTML setup, Tailwind CSS applied to body |

**Configuration:**

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Python dependencies, pytest config, ruff linting rules |
| `frontend/package.json` | Node.js dependencies, npm run scripts (build, dev, export) |
| `frontend/next.config.ts` | Next.js: `output: 'export'` for static build, assets prefix |
| `frontend/tailwind.config.ts` | Tailwind: dark theme, ops-console color vars (`ops-bg`, `ops-panel`, `ops-border`) |
| `docker/Dockerfile` | Multi-stage: Node → Python, combine frontend/backend into one image |
| `.env.example` | Template showing required vars (OPENROUTER_API_KEY, MAVLINK_GATEWAY_URL, LLM_MOCK) |

**Core Logic:**

| File | What It Does |
|------|-------------|
| `backend/app/db/schema.py` | SQL DDL: operator_profile, fleet_roster, missions, mission_log, budget_snapshots, chat_messages |
| `backend/app/db/connection.py` | Database class: lazy init, WAL mode, asyncio.Lock for write serialization, transaction() |
| `backend/app/telemetry/cache.py` | TelemetryCache: thread-safe dict, version counter, get_all() for snapshot |
| `backend/app/telemetry/simulator.py` | SimulatorTelemetrySource: Ornstein-Uhlenbeck drain, occasional wind gust events |
| `backend/app/missions/service.py` | launch_mission(), auto_assign_mission(), recall_mission(), find_eligible_drone() |
| `backend/app/missions/repository.py` | Atomic mission create/update, budget deduct, drone availability checks |
| `backend/app/missions/scheduler.py` | Background tasks: assignment (retry queued), delivery (mark en_route as delivered), budget snapshot |
| `frontend/src/lib/useTelemetryStream.ts` | React hook: EventSource to SSE, accumulate readings, provide snapshot to component |

**Testing:**

| Path | Contents |
|------|----------|
| `backend/tests/telemetry/` | Simulator, cache, stream generation tests |
| `backend/tests/missions/` | Service logic, launch/recall/budget validation, eligibility tests |
| `backend/tests/db/` | Connection, transactions, schema tests |
| `tests/specs/` | Playwright E2E test files |

## Naming Conventions

**Files:**

- **Python modules**: snake_case (e.g., `telemetry_cache.py`, `simulator.py`, `create_missions_router.py`)
- **Python test files**: `test_<module>.py` (e.g., `test_cache.py`, `test_service.py`)
- **TypeScript/React components**: PascalCase (e.g., `Header.tsx`, `FleetRosterPanel.tsx`, `ConnectionDot.tsx`)
- **TypeScript/React hooks**: camelCase with `use` prefix (e.g., `useTelemetryStream.ts`)
- **TypeScript types**: PascalCase (e.g., `TelemetryUpdate`, `TelemetrySnapshot`)

**Directories:**

- **Python packages**: snake_case (e.g., `backend/app/telemetry/`, `backend/app/missions/`)
- **React component directories**: PascalCase (e.g., `frontend/src/components/`)
- **Utility directories**: lowercase (e.g., `frontend/src/lib/`, `frontend/src/types/`)

**Python Functions & Classes:**

- **Classes**: PascalCase (e.g., `Database`, `TelemetryCache`, `TelemetrySource`)
- **Functions**: snake_case (e.g., `create_telemetry_source()`, `launch_mission()`, `get_remaining_kwh()`)
- **Constants**: UPPER_CASE (e.g., `ENERGY_COST_PER_KM_KWH`, `DEFAULT_CRUISE_SPEED_KMH`, `MISSION_STATUSES`)

**TypeScript/React:**

- **Components**: PascalCase (e.g., `<Header />`, `<FleetRosterPanel />`)
- **Props interfaces**: `<ComponentName>Props` (e.g., `HeaderProps`, `FleetRosterPanelProps`)
- **Functions**: camelCase (e.g., `formatBattery()`, `calculateETA()`)
- **Constants**: UPPER_CASE for module-level, camelCase for local (e.g., `const TIMEOUT_MS = 5000; const isConnected = ...`)

**Database:**

- **Tables**: snake_case (e.g., `operator_profile`, `fleet_roster`, `budget_snapshots`)
- **Columns**: snake_case (e.g., `drone_id`, `energy_cost_kwh`, `created_at`)
- **Indexes**: `idx_<table>_<column>` (e.g., `idx_missions_drone`)

## Where to Add New Code

**New Feature (e.g., Heatmap Visualization):**

- **Frontend code**: `frontend/src/components/FleetHeatmap.tsx` (new component)
- **Tests**: `frontend/__tests__/FleetHeatmap.test.tsx` (or place alongside component)
- **API calls** (if needed): Add fetch calls in new hook `frontend/src/lib/useFleetStatus.ts`, or extend existing `useTelemetryStream`
- **Backend endpoint** (if needed): New route in `backend/app/missions/router.py` (or new router in `backend/app/<subsystem>/router.py`)

**New Subsystem (e.g., Geofencing):**

- **Backend module**: Create `backend/app/geofencing/` with structure mirroring missions:
  - `models.py` — data models, error types
  - `service.py` — business logic
  - `repository.py` — database queries
  - `router.py` — HTTP endpoints
  - `__init__.py` — public exports
- **Tests**: `backend/tests/geofencing/` mirroring module structure
- **Frontend**: Add component to `frontend/src/components/` if UI is needed
- **Registration**: Import and include router in `backend/app/main.py:82` (app.include_router(...))

**New API Endpoint:**

- If it's mission-related: Add to `backend/app/missions/router.py` (within `create_missions_router()`)
- If it's telemetry-related: Add to `backend/app/telemetry/stream.py` or create new file in `backend/app/telemetry/`
- Always:
  1. Define Pydantic request/response models at the top of the router file
  2. Implement the endpoint, calling service layer for business logic
  3. Catch domain exceptions (`MissionError` etc.) and translate to HTTP status codes
  4. Return JSON via Pydantic model or dict

**New Database Table:**

1. Add CREATE TABLE statement to `backend/app/db/schema.py`
2. If seeding required, add to `backend/app/db/seed.py`
3. Create repository file (e.g., `backend/app/<subsystem>/repository.py`) with query functions
4. Write tests in `backend/tests/db/test_<subsystem>.py`
5. No migration script needed — lazy init on first run

**Telemetry Feature:**

- **Simulator enhancement**: Modify `backend/app/telemetry/simulator.py` (drain model, wind gust events)
- **New telemetry field**: Add to `TelemetryUpdate` dataclass in `backend/app/telemetry/models.py`, update cache to store it, add to SSE JSON in `stream.py`
- **MAVLink gateway enhancement**: Modify `backend/app/telemetry/mavlink_gateway.py` (polling, parsing)

**Frontend Component State Management:**

- For single component: Use `useState()` directly in component
- For cross-component state: Create custom hook in `frontend/src/lib/` and call from multiple components (e.g., `useTelemetryStream` is already shared)
- For global app state: Consider React Context (not yet used; suitable if energy budget, active mission count need to be accessed throughout tree)

## Special Directories

**backend/app/demo/**
- Purpose: Demo/test utilities (internal use, not part of public API)
- Generated: No (hand-written for testing)
- Committed: Yes

**frontend/out/**
- Purpose: Next.js static export build output
- Generated: Yes (`npm run build` → `out/`)
- Committed: No (built fresh in Docker)

**backend/__pycache__, frontend/node_modules, tests/node_modules**
- Purpose: Compiled/cached files and installed dependencies
- Generated: Yes (build artifacts)
- Committed: No (gitignored)

**planning/archive/**
- Purpose: Earlier design decisions and notes (historical, reference only)
- Generated: No (hand-written by agents)
- Committed: Yes (for history and learning)

**planning/codebase/**
- Purpose: Automated codebase analysis (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes (by /gsd-map-codebase agent)
- Committed: Yes (referenced by other agents in planning)

---

*Structure analysis: 2026-08-12*
