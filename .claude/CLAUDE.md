<!-- GSD:project-start source:PROJECT.md -->

## Project

**SkyFleet Ops**

SkyFleet Ops is a real-time operations console for a simulated last-mile drone delivery fleet. It streams live telemetry for 10 delivery drones, lets a dispatcher launch and monitor missions against a shared energy budget, and integrates an LLM "flight director" that can analyze fleet health and dispatch missions on the dispatcher's behalf. It's a demonstration capstone for an agentic AI coding course, showing how independent frontend/backend workstreams develop against a shared spec.

**Core Value:** The dispatcher can watch a fleet of drones stream live telemetry, launch/recall missions against an energy budget, and delegate that same dispatching to an AI flight director through natural-language chat — all in one ATC-style console, single Docker command to run.

### Constraints

- **Tech stack**: Backend is FastAPI (Python) managed via `uv`; frontend is Next.js/TypeScript as a static export; database is SQLite. These are fixed by PLAN.md, not open decisions.
- **Architecture**: Single Docker container, single port (8000), FastAPI serves both `/api/*` routes and the static frontend build — no CORS configuration needed, no docker-compose in production.
- **LLM integration**: Must use the `cerebras` skill to call LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` on Cerebras inference, with structured outputs. `OPENROUTER_API_KEY` is available in the project root `.env`.
- **Telemetry interface**: All downstream code (mission validation, SSE, frontend) must consume telemetry through the existing `TelemetryCache` / `TelemetrySource` interface — do not bypass or duplicate it.
- **Testing**: E2E tests must default to `LLM_MOCK=true` for speed/determinism; Playwright infra stays isolated in `tests/` via `docker-compose.test.yml`, not in the production image.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- TypeScript 5.6 - Frontend (React components, app logic)
- Python 3.12 - Backend (FastAPI application, telemetry simulation, database)
- JavaScript (minimal, package configuration)
- SQL - SQLite schema definitions in `backend/app/db/schema.py`

## Runtime

- Node.js 20 (LTS) - Frontend build and dev server
- Python 3.12 - Backend runtime
- npm - Frontend dependencies and scripts
- uv - Python package manager for backend (modern, fast, reproducible lockfiles)

## Frameworks

- Next.js 15.0.0 - Frontend framework with TypeScript support, SSR/SSG, static export via `output: "export"`
- FastAPI 0.115.0+ - Backend REST API framework, async/await native, automatic OpenAPI docs
- Uvicorn 0.32.0+ - ASGI server for FastAPI, production-ready
- pytest 8.3.0+ - Backend unit/integration tests
- pytest-asyncio 0.24.0+ - Async test support for FastAPI
- pytest-cov 5.0.0+ - Coverage reporting
- Vitest 2.1.0 - Frontend unit tests (Vite-based)
- Playwright 1.48.0 - E2E tests, browser automation
- Tailwind CSS 3.4.0 - Utility-first CSS framework for ops-console styling
- PostCSS 8.4.0 - CSS processing pipeline
- Autoprefixer 10.4.0 - Browser vendor prefix injection
- Ruff 0.7.0+ - Python linter and formatter

## Key Dependencies

- httpx 0.27.0+ - Async HTTP client used by MAVLink gateway telemetry source (`backend/app/telemetry/mavlink_gateway.py`)
- numpy 2.0.0+ - Numeric computations for fleet telemetry simulator; Ornstein-Uhlenbeck correlated drain model with Cholesky decomposition (`backend/app/telemetry/simulator.py`)
- recharts 2.13.0 - React charting library for fleet visualizations (battery trends, energy budget, fleet heatmap)
- rich 13.0.0+ - Console formatting and logging for backend
- react-dom 18.3.0 - React DOM rendering for frontend
- Testing Library React 16.0.0+ - React component testing utilities

## Configuration

- Variables read from `.env` file at project root (not in repo, see `.env.example`)
- Critical var: `OPENROUTER_API_KEY` - OpenRouter API key for future LLM integration (planned)
- Optional var: `MAVLINK_GATEWAY_URL` - URL of MAVLink telemetry gateway (if unset, uses built-in simulator)
- Optional var: `LLM_MOCK` - Set to "true" for deterministic mock LLM responses (testing only)
- Optional var: `DATABASE_PATH` - Override SQLite database location (defaults to `database/skyfleet.db`)
- `frontend/next.config.js` - Static export output, unoptimized images
- `frontend/tsconfig.json` - ES2017 target, strict mode, path alias `@/*` → `./src/*`
- `frontend/tailwind.config.ts` - Dark theme colors (ops.bg, ops.panel, ops.amber, ops.teal, ops.signal), flash animations for battery state changes
- `backend/pyproject.toml` - Project metadata, dependencies, dev tools config

## Database

- SQLite - Single-file database at `database/skyfleet.db` (volume-mounted in Docker, gitignored)
- Connection: Python `sqlite3` standard library via `backend/app/db/connection.py`
- Mode: WAL (Write-Ahead Logging) for concurrent reads, foreign keys enabled
- Initialization: Lazy schema creation and seeding on first request (no manual migrations)
- Tables: `operator_profile`, `fleet_roster`, `missions`, `mission_log`, `budget_snapshots`, `chat_messages`

## Platform Requirements

- Node.js 20+ (npm bundled)
- Python 3.12+ (uv installed as dependency)
- Docker 20+ (for containerized deployment)
- Modern browser with EventSource API (Chrome, Firefox, Safari, Edge)
- Docker container, single image serves frontend static export + backend API
- Single port exposure: 8000
- Volume mount: `database/` directory for SQLite persistence
- Environment file: `.env` with `OPENROUTER_API_KEY` and optional `MAVLINK_GATEWAY_URL`

## Build Pipeline

- `npm run build` → Next.js static export to `frontend/out/`
- Included in Docker via multi-stage: Node 20 → build stage copies output to Python image as `static/`
- `uv sync` → Install dependencies from lockfile to `.venv/`
- No compilation step; Python runs directly via `uv run uvicorn`
- Stage 1: Node 20-slim, build Next.js static export
- Stage 2: Python 3.12-slim, install uv, sync backend deps, copy static output, expose 8000

## Performance Characteristics

- numpy-based mean-reverting drain model updates at ~500ms intervals
- Cholesky decomposition for correlated squadron battery moves
- In-memory cache holds latest reading per drone, no DB writes per update (snapshots periodic)
- Server pushes telemetry to all connected clients at ~500ms cadence
- EventSource handles reconnection automatically
- Stateless streaming; no session memory
- SQLite with single async lock serializes writes; no bottleneck at current scale
- Transactions atomic for mission dispatch (energy budget, one-per-drone constraint)
- Indexes on drone_id, recorded_at, created_at for query efficiency

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Lowercase with underscores: `telemetry_models.py`, `mission_queue.py`, `conftest.py`
- Avoid abbreviations unless standard: `repo` → `repository`
- Test files: `test_*.py` (e.g., `test_models.py`, `test_queue.py`)
- Private/internal modules: single leading underscore in variables/functions (e.g., `_error_response()`)
- Snake_case: `launch_mission()`, `get_battery()`, `seed_if_empty()`
- Boolean functions may use `is_*` or `get_*` prefix: `is_drone_on_roster()`, `is_eligible()`
- Async functions: same snake_case, no special prefix: `async def launch_mission()`
- Factory functions: `create_*` prefix: `create_telemetry_source()`, `create_stream_router()`
- Lifecycle/scheduler: `run_*` prefix: `run_assignment_scheduler()`, `run_delivery_scheduler()`
- PascalCase: `TelemetryUpdate`, `MissionQueue`, `TelemetryCache`
- Exception classes: PascalCase ending with `Error`: `MissionError`, `UnknownDroneError`, `InsufficientBudgetError`
- Dataclasses: `@dataclass(frozen=True, slots=True)` for immutable value types
- Snake_case: `drone_id`, `battery_pct`, `distance_km`, `energy_cost_kwh`
- Private instance variables: `_readings`, `_lock`, `_version`
- Module-level constants: UPPER_SNAKE_CASE: `UNSAFE_TELEMETRY_STATUSES`, `ENERGY_COST_PER_KM_KWH`, `MAX_ASSIGNMENT_ATTEMPTS`
- Type hint variables: use full names, not abbreviations: `battery_pct` not `batt_pct`, `altitude_m` not `alt_m`
- Component files: PascalCase: `FleetRosterPanel.tsx`, `ConnectionDot.tsx`, `Header.tsx`
- Hook files: `use*.ts` prefix: `useTelemetryStream.ts`
- Type/constant files: lowercase: `telemetry.ts`
- Utility/lib files: lowercase: `useTelemetryStream.ts`
- Exported components: PascalCase: `FleetRosterPanel()`, `ConnectionDot()`
- Exported hooks: camelCase with `use` prefix: `useTelemetryStream()`
- Internal functions: camelCase: `batteryColor()`, `seed_telemetry()`
- Factory functions: `create*`: `createTelemetrySource()`, `createStreamRouter()`
- Constants: UPPER_SNAKE_CASE: `COLORS`, `LABELS`, `STATUS_LABEL`
- Type names: PascalCase: `TelemetryReading`, `ConnectionStatus`, `DroneStatus`
- Interface names: PascalCase with `Props` suffix for component props: `interface Props { ... }`
- Regular variables: camelCase: `droneId`, `selectedDroneId`, `maxHistoryPoints`

## Code Style

- Python: Ruff formatter (configured in `pyproject.toml`):
- TypeScript: Next.js default (Prettier-compatible via `next lint`)
- Python backend: `uv run --extra dev ruff check app/ tests/`
- TypeScript frontend: `npm run lint` (Next.js built-in linting)
- Run before committing for code quality checks
- Python: f-strings preferred for all string interpolation
- Python docstrings: Triple-quoted, concise, describe purpose and behavior
- TypeScript: Template literals for dynamic strings, JSX expressions for React

## Import Organization

- Frontend: `@/*` maps to `./src/*` (configured in `tsconfig.json`)
- Use `@/` for all internal imports (types, components, lib, utilities)

## Error Handling

- Inherit from domain-specific base: `MissionError` (not `Exception` directly) for validation failures
- Domain exceptions have a `reason` class attribute (string key): `reason = "unknown_drone"`
- Each exception captures relevant data as instance attributes: `drone_id`, `requested_kwh`, `remaining_kwh`
- Provide detailed messages in `super().__init__()`: `f"drone not on roster: {drone_id}"`
- Router layer catches exceptions and maps to HTTP status codes via a lookup table (e.g., `_ERROR_STATUS`)
- No custom error types yet (components are minimal/growing)
- Use native `EventSource` error handling for SSE reconnection
- Pass error info through component props or return values where needed

## Logging

- Python: `logging` module (configured in `app/main.py`):
- TypeScript: `console` (no structured logging library yet)
- Application lifecycle: `"SkyFleet Ops backend started"`, `"SkyFleet Ops backend stopped"`
- Errors/warnings: caught exceptions, startup issues
- Debug info: spawned background tasks, telemetry updates (use `logger.debug()` if verbose)
- Do NOT log in tests unless debugging a failure

## Comments

- Clarify *why*, not *what*: Code reads clearly; comments explain intent
- Algorithm complexity: Exponential backoff calculation, retry logic
- Non-obvious behavior: OU-drain model assumptions, thread-safety guarantees
- Design decisions documented in module docstrings
- Triple-quoted, first line: one-sentence purpose
- Blank line, then details (if complex)
- For packages (`__init__.py`): list public API with `__all__`
- One-liner for simple functions; multi-line for complex ones
- Describe parameters, return value, and any exceptions raised
- Use NumPy/Google style format
- Rare; only for non-obvious logic
- Use `#` with space: `# comment here`
- Keep brief and above the relevant code

## Function Design

- Functions should be small and focused (typically < 50 lines)
- Single responsibility: one logical task per function
- If logic is complex, break into helper functions (prefix with `_` if internal to module)
- Explicit is better than implicit: pass all dependencies as arguments
- No reliance on module-level mutable state (except for DI containers like `app.state.*`)
- Use type hints for all parameters and return types
- Python: use `*` to force keyword-only args when appropriate (e.g., `async def launch_mission(..., *, drone_id: str, zone: str)`)
- Consistent types: function always returns the same type (or `None`)
- Avoid returning tuples without names; use dataclasses or dicts with keys
- Dataclass instances preferred for structured returns: `Mission`, `TelemetryUpdate`, `QueuedMission`
- `None` for operations with no meaningful return (e.g., `remove()`, `update()` that modifies in-place returns the created object, not None)

## Module Design

- Explicit `__all__` list in `__init__.py` files
- Only export public API; private helpers stay in their module
- Group related exports together (e.g., models before routers)
- `models.py`: Data types, constants, exceptions
- `cache.py` or `store.py`: Stateful stores (thread-safe)
- `router.py`: FastAPI endpoints (dependency injection at factory-function level)
- `service.py`: Business logic (validation, domain rules)
- `repository.py`: Database queries (CRUD, transactions)
- `interface.py`: Abstract base classes (if multiple implementations)
- `factory.py`: Constructors that select implementations (e.g., simulator vs. MAVLink)
- No global singletons; pass dependencies as function/constructor arguments
- Router factories accept dependencies: `def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:`
- Thread-safety achieved via class-level locks, not module-level state manipulation

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| **Frontend Entry Point** | Render main page, connect SSE, bind telemetry stream to UI | `frontend/src/app/page.tsx` |
| **Telemetry Cache** | Thread-safe in-memory storage of latest drone readings | `backend/app/telemetry/cache.py` |
| **Telemetry Source** | Abstract interface; Simulator generates readings, MAVLink gateway fetches them | `backend/app/telemetry/interface.py` |
| **SSE Stream Router** | Accept GET /api/stream/telemetry, yield JSON events from cache every ~500ms | `backend/app/telemetry/stream.py` |
| **Missions Service** | Validate drone eligibility, check budget, execute launches/recalls | `backend/app/missions/service.py` |
| **Missions Repository** | Execute atomic database transactions: mission create/update, budget deduct | `backend/app/missions/repository.py` |
| **Missions Router** | Accept POST/DELETE /api/fleet/missions, delegate to service, return status | `backend/app/missions/router.py` |
| **Mission Queue** | Hold pending/failed mission dispatch requests for retry by scheduler | `backend/app/missions/queue.py` |
| **Assignment Scheduler** | Periodically pop queued missions, try auto-assign to eligible drones | `backend/app/missions/scheduler.py` |
| **Database** | Lazy init connection, serialize writes via asyncio.Lock, provide transaction() | `backend/app/db/connection.py` |
| **Schema/Seed** | Define SQL DDL and populate default operator/roster on first run | `backend/app/db/schema.py`, `backend/app/db/seed.py` |
| **FastAPI App Lifespan** | Bootstrap telemetry source, start background tasks, graceful shutdown | `backend/app/main.py` |

## Pattern Overview

- **Single-threaded async event loop** — FastAPI on uvicorn; all I/O (database, external APIs) runs off the main thread via `asyncio.to_thread()`
- **Separation of concerns via layers** — Router → Service → Repository → Database
- **Database write serialization** — Single `asyncio.Lock` in `Database` class eliminates race conditions and enforces atomicity for multi-statement operations (mission dispatch, budget deduction)
- **Pluggable telemetry source** — Abstract `TelemetrySource` interface lets simulator and MAVLink gateway coexist without changing downstream code
- **Optimistic, not defensive** — Trust inputs at module boundaries; raise specific exceptions if validation fails (service layer catches and translates to HTTP status codes)

## Layers

- Purpose: Render mission control UI, consume SSE stream, make API calls for dispatch/recall
- Location: `frontend/src/`
- Contains: React components (TypeScript), custom hooks for SSE (`useTelemetryStream`), CSS styling
- Depends on: HTTP API at `/api/*`, SSE endpoint at `/api/stream/*`
- Used by: Browser; mounted by FastAPI as static files under `/`
- Purpose: Accept HTTP requests, parse JSON, call service layer, return JSON responses
- Location: `backend/app/*/router.py` (missions, telemetry stream, etc.)
- Contains: Pydantic request/response models, error-to-HTTP-status translation, endpoint logic
- Depends on: Service layer, TelemetryCache, Database
- Used by: Frontend, external tooling (curl, Postman)
- Purpose: Validate inputs, implement business logic, raise domain exceptions on failure
- Location: `backend/app/missions/service.py`, `backend/app/telemetry/factory.py`
- Contains: `launch_mission()`, `auto_assign_mission()`, `recall_mission()`, drone eligibility checks, budget validation
- Depends on: Repository, TelemetryCache, Models
- Used by: Routers, background schedulers
- Purpose: Execute SQL queries and transactions against the database
- Location: `backend/app/missions/repository.py`
- Contains: `create_mission()`, `recall()`, `list_active_missions()`, `get_remaining_kwh()`
- Depends on: Database class
- Used by: Service layer, routers
- Purpose: Serialize writes, provide async interface to SQLite, enforce atomicity
- Location: `backend/app/db/connection.py`
- Contains: `asyncio.Lock`-protected connection, `execute()`, `fetchall()`, `transaction()`
- Depends on: sqlite3 (stdlib)
- Used by: Repository, schema initialization
- Purpose: Generate or fetch telemetry readings, push to cache on a timer
- Location: `backend/app/telemetry/simulator.py`, `backend/app/telemetry/mavlink_gateway.py`
- Contains: Mean-reverting drain model (simulator), REST polling logic (gateway), background task lifetime
- Depends on: TelemetryCache, models
- Used by: Lifespan manager in main.py
- Purpose: Store the latest reading for each drone, provide thread-safe access
- Location: `backend/app/telemetry/cache.py`
- Contains: In-memory dict, version counter, lock-protected reads/writes
- Depends on: TelemetryUpdate model
- Used by: SSE streaming, service validation, mission eligibility checks

## Data Flow

### Primary Request Path: Launch a Mission (Manual Dispatch)

### Telemetry Streaming Path

### Mission Delivery (Background Scheduler)

### Assignment Scheduler (Auto-Retry Queued Missions)

### State Management

- **Operator energy budget**: Stored in `operator_profile.energy_budget_kwh`, read/written atomically in mission transaction
- **Active missions**: Queried from `missions` table WHERE status='en_route'
- **Fleet telemetry**: Stored in `TelemetryCache` (in-memory, ephemeral); populated by Simulator/Gateway, consumed by SSE and service validation
- **Budget history**: `budget_snapshots` table; recorded every 30s by scheduler and immediately after mission launch/recall
- **Mission history**: `mission_log` table (append-only); every launch/recall action logged here

## Key Abstractions

- Purpose: Represent any provider that can push telemetry to a cache (simulator, real hardware gateway, mock)
- Examples: `SimulatorTelemetrySource`, `MavlinkGatewayTelemetrySource`
- Pattern: Abstract class with concrete implementations; factory function `create_telemetry_source(cache)` selects based on env var
- Purpose: Immutable record of a delivery task
- Examples: `Mission(id="...", drone_id="FALCON-05", zone="Downtown", distance_km=3.5, energy_cost_kwh=2.8, status="en_route", updated_at="2026-08-12T...")`
- Pattern: Dataclass with `to_dict()` for JSON serialization; `energy_cost_for(distance_km)` static method
- Purpose: Domain-specific exceptions raised by service layer when validation fails
- Examples: `UnknownDroneError`, `DroneAlreadyEnRouteError`, `InsufficientBudgetError`, `NoActiveMissionError`, `NoEligibleDroneError`
- Pattern: Exception hierarchy with `reason` attribute for HTTP status code translation
- Purpose: Immutable snapshot of a drone's state at one instant
- Includes: battery_pct, previous_battery_pct, altitude_m, speed_kmh, status, timestamp
- Provides: battery_delta (pct change), battery_direction ("draining", "charging", "flat")

## Entry Points

- Initialize Database, TelemetryCache, MissionQueue
- Load .env file (OPENROUTER_API_KEY, MAVLINK_GATEWAY_URL, LLM_MOCK)
- Create telemetry source (Simulator or MAVLink gateway based on env)
- Start three background schedulers as asyncio tasks
- Mount routers and static files
- Call `useTelemetryStream()` hook
- Establish SSE connection to `/api/stream/telemetry`
- Render Header, FleetRosterPanel with live telemetry snapshot, AI chat sidebar (placeholder)
- Use EventSource API to subscribe to `/api/stream/telemetry`
- On each event, update React state with latest readings
- Provide snapshot to component, status indicator (connected/reconnecting/disconnected)

## Architectural Constraints

- **Threading:** Single async event loop (uvicorn worker). All blocking I/O (SQLite, network) runs in a thread pool via `asyncio.to_thread()`. No multi-worker deployment yet (would require Postgres + Redis for shared state).
- **Global state:** Three module-level objects initialized at startup: `telemetry_cache`, `mission_queue`, `database` (`backend/app/main.py:51-53`). They are passed to routers and schedulers, not accessed globally in route handlers.
- **Circular imports:** None observed. Layers import down (router → service → repository → database), not up.
- **Single-writer database:** SQLite 3.x with WAL mode allows multiple readers but enforces one writer at a time. `Database` class wraps all writes behind a single `asyncio.Lock`, making concurrent mission launches safe and atomic.
- **One active mission per drone:** Enforced by database constraint (CHECK in schema) and transaction logic (repository checks before INSERT).

## Anti-Patterns

### Fully Manual Mission Dispatch (to be replaced)

### Direct Database Queries in Routers

### Mission Status Hardcoded as String

## Error Handling

- **Domain validation**: Service layer raises subclasses of `MissionError` (e.g., `InsufficientBudgetError`, `UnknownDroneError`)
- **HTTP translation**: Router catches `MissionError`, looks up HTTP status code in `_ERROR_STATUS` dict, returns HTTPException (`backend/app/missions/router.py:15-37`)
- **Telemetry issues**: If telemetry source fails (e.g., MAVLink gateway offline), the background task logs and continues; cache retains last-known readings
- **Database errors**: If SQLite write fails (disk full, corruption), transaction rolls back and exception propagates up to router, which returns 500

## Cross-Cutting Concerns

- Input validation: Pydantic models in router layer (e.g., `LaunchMissionRequest` with `distance_km > 0`)
- Business logic validation: Service layer (e.g., drone on roster? budget sufficient? telemetry safe?)
- Database constraints: Schema includes CHECK clauses and UNIQUE constraints to prevent invalid states

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| project-review | >- Use this skill when reviewing the SkyFleet Ops project structure, documentation, architecture, or implementation before adding new features. | `.claude/skills/project-review/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
