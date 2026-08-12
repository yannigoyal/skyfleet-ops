<!-- refreshed: 2026-08-12 -->
# Architecture

**Analysis Date:** 2026-08-12

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js Static Export)                  │
│             Served by FastAPI as static files under /                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Home Page (page.tsx) / Components / Telemetry Stream Consumer  │  │
│  │  `frontend/src/app/page.tsx`, `frontend/src/components/`        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│           │                    │                   │                  │
│           ▼                    ▼                   ▼                  │
│      /api/stream/          /api/fleet/*          /api/roster/*       │
│      telemetry             missions, budget      fleet roster ops    │
└──────────────────────────────────────────────────────────────────────┘
           │                    │                   │
           ▼                    ▼                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│           FastAPI Backend (async request handlers)                    │
│  `backend/app/main.py` entry point, routers:                         │
│  - Stream Router: SSE telemetry streaming                            │
│  - Missions Router: launch/recall/status endpoints                   │
│  - Roster Router: (planned) add/remove drone endpoints               │
│  - Chat Router: (planned) LLM integration                            │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Three Background Task Schedulers                         │
│  - Assignment Scheduler: auto-assign pending missions to drones      │
│  - Delivery Scheduler: mark en_route missions delivered              │
│  - Budget Snapshot Loop: record remaining energy every 30s           │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Core Service Layers                             │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Telemetry Subsystem                                            │  │
│  │ - TelemetryCache: thread-safe in-memory store of live readings │  │
│  │ - TelemetrySource interface (Simulator or MAVLink Gateway)     │  │
│  │ - SSE event generation from cache updates                      │  │
│  │ Location: `backend/app/telemetry/`                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Missions Subsystem                                             │  │
│  │ - Service layer: launch_mission, auto_assign_mission, recall   │  │
│  │ - Repository layer: database queries, atomicity via txn()      │  │
│  │ - Queue: pending/failed missions for retry scheduling          │  │
│  │ Location: `backend/app/missions/`                              │  │
│  └────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Database Layer                                                 │  │
│  │ - Lazy initialization with schema auto-create on first run     │  │
│  │ - Single asyncio.Lock for write serialization (SQLite 3.x)     │  │
│  │ - transaction() for atomic multi-statement ops (missions,      │  │
│  │   budget, mission_log updates)                                 │  │
│  │ Location: `backend/app/db/`                                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│              SQLite Database (WAL mode, persistent)                   │
│  File: `database/skyfleet.db` (volume-mounted in Docker)             │
│  Tables: operator_profile, fleet_roster, missions, mission_log,      │
│          budget_snapshots, chat_messages (schema in section 7)        │
└──────────────────────────────────────────────────────────────────────┘
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

**Overall:** Async request-response with background steady-state data producers.

**Key Characteristics:**
- **Single-threaded async event loop** — FastAPI on uvicorn; all I/O (database, external APIs) runs off the main thread via `asyncio.to_thread()`
- **Separation of concerns via layers** — Router → Service → Repository → Database
- **Database write serialization** — Single `asyncio.Lock` in `Database` class eliminates race conditions and enforces atomicity for multi-statement operations (mission dispatch, budget deduction)
- **Pluggable telemetry source** — Abstract `TelemetrySource` interface lets simulator and MAVLink gateway coexist without changing downstream code
- **Optimistic, not defensive** — Trust inputs at module boundaries; raise specific exceptions if validation fails (service layer catches and translates to HTTP status codes)

## Layers

**Frontend (Next.js):**
- Purpose: Render mission control UI, consume SSE stream, make API calls for dispatch/recall
- Location: `frontend/src/`
- Contains: React components (TypeScript), custom hooks for SSE (`useTelemetryStream`), CSS styling
- Depends on: HTTP API at `/api/*`, SSE endpoint at `/api/stream/*`
- Used by: Browser; mounted by FastAPI as static files under `/`

**FastAPI Router Layer:**
- Purpose: Accept HTTP requests, parse JSON, call service layer, return JSON responses
- Location: `backend/app/*/router.py` (missions, telemetry stream, etc.)
- Contains: Pydantic request/response models, error-to-HTTP-status translation, endpoint logic
- Depends on: Service layer, TelemetryCache, Database
- Used by: Frontend, external tooling (curl, Postman)

**Service Layer:**
- Purpose: Validate inputs, implement business logic, raise domain exceptions on failure
- Location: `backend/app/missions/service.py`, `backend/app/telemetry/factory.py`
- Contains: `launch_mission()`, `auto_assign_mission()`, `recall_mission()`, drone eligibility checks, budget validation
- Depends on: Repository, TelemetryCache, Models
- Used by: Routers, background schedulers

**Repository Layer:**
- Purpose: Execute SQL queries and transactions against the database
- Location: `backend/app/missions/repository.py`
- Contains: `create_mission()`, `recall()`, `list_active_missions()`, `get_remaining_kwh()`
- Depends on: Database class
- Used by: Service layer, routers

**Database Layer:**
- Purpose: Serialize writes, provide async interface to SQLite, enforce atomicity
- Location: `backend/app/db/connection.py`
- Contains: `asyncio.Lock`-protected connection, `execute()`, `fetchall()`, `transaction()`
- Depends on: sqlite3 (stdlib)
- Used by: Repository, schema initialization

**Telemetry Source Layer:**
- Purpose: Generate or fetch telemetry readings, push to cache on a timer
- Location: `backend/app/telemetry/simulator.py`, `backend/app/telemetry/mavlink_gateway.py`
- Contains: Mean-reverting drain model (simulator), REST polling logic (gateway), background task lifetime
- Depends on: TelemetryCache, models
- Used by: Lifespan manager in main.py

**Cache Layer:**
- Purpose: Store the latest reading for each drone, provide thread-safe access
- Location: `backend/app/telemetry/cache.py`
- Contains: In-memory dict, version counter, lock-protected reads/writes
- Depends on: TelemetryUpdate model
- Used by: SSE streaming, service validation, mission eligibility checks

## Data Flow

### Primary Request Path: Launch a Mission (Manual Dispatch)

1. **User clicks "Launch" button** with drone_id="FALCON-05", zone="Downtown", distance_km=3.5 (`frontend/src/app/page.tsx`)
2. **Frontend POST /api/fleet/missions** with LaunchMissionRequest JSON (`frontend/src/lib/useTelemetryStream.ts` or similar — not yet implemented)
3. **Missions router** receives request, validates schema, calls `service.launch_mission(db, cache, drone_id="FALCON-05", zone="Downtown", distance_km=3.5) → Mission` (`backend/app/missions/router.py:76-89`)
4. **Service layer** checks:
   - Is FALCON-05 on the roster? → `repository.is_drone_on_roster(db, "FALCON-05")` (queries `fleet_roster` table)
   - Does FALCON-05 have safe telemetry? → `cache.get("FALCON-05").status` is not in ["offline", "low_battery"]
   - Calculate energy cost: `Mission.energy_cost_for(3.5)` → 2.8 kWh (`backend/app/missions/models.py:40`)
5. **Service calls** `repository.create_mission(db, "FALCON-05", "Downtown", 3.5, 2.8)` (`backend/app/missions/repository.py`)
6. **Repository wraps in transaction**:
   ```python
   def _create(conn):
       # Check remaining budget sufficient?
       # Check no active mission for FALCON-05?
       # INSERT into missions table
       # INSERT into mission_log table
       # UPDATE operator_profile.energy_budget_kwh
       # INSERT into budget_snapshots
       return mission
   await db.transaction(_create)
   ```
   All four statements execute atomically; if any fails (e.g., insufficient budget), all roll back. (`backend/app/db/connection.py:73-89`)
7. **Router returns** 201 Created with Mission JSON including calculated `eta_minutes` based on drone's current speed from cache (`backend/app/missions/router.py:40-46`)
8. **Frontend receives** mission object, updates UI to show new active mission

### Telemetry Streaming Path

1. **Frontend establishes EventSource** connection to `GET /api/stream/telemetry` on page load (`frontend/src/lib/useTelemetryStream.ts`)
2. **SSE endpoint** in stream router (`backend/app/telemetry/stream.py:26-46`) returns StreamingResponse
3. **_generate_events() async generator** runs every ~500ms:
   - Checks `if telemetry_cache.version != last_version` (change detection)
   - If changed, calls `cache.get_all()` → dict of all TelemetryUpdate objects
   - Yields SSE event: `data: JSON\n\n`
4. **Frontend EventSource** receives `message` event, parses JSON, accumulates battery readings in state for sparkline
5. **UI re-renders** with new battery%, altitude, speed; battery flash animation triggered on direction change (`frontend/src/components/FleetRosterPanel.tsx`)

### Mission Delivery (Background Scheduler)

1. **Delivery scheduler** runs every 10 seconds (`backend/app/missions/scheduler.py:run_delivery_scheduler()`)
2. Lists all en_route missions from DB
3. For each mission, calculates ETA from launch time and distance / expected speed
4. If ETA elapsed, updates mission.status from "en_route" → "delivered"
5. Mission no longer appears in active list; freed drone can be assigned new mission

### Assignment Scheduler (Auto-Retry Queued Missions)

1. **Assignment scheduler** runs every 30 seconds (`backend/app/missions/scheduler.py:run_assignment_scheduler()`)
2. Pops pending missions from `MissionQueue` (in-memory FIFO)
3. Calls `service.auto_assign_mission(db, cache, zone=..., distance_km=...)` for each
4. If a drone becomes eligible (battery recharged, previous mission delivered), assignment succeeds, mission dispatches
5. If still no eligible drone, mission is re-enqueued (or moved to failed queue)

### State Management

- **Operator energy budget**: Stored in `operator_profile.energy_budget_kwh`, read/written atomically in mission transaction
- **Active missions**: Queried from `missions` table WHERE status='en_route'
- **Fleet telemetry**: Stored in `TelemetryCache` (in-memory, ephemeral); populated by Simulator/Gateway, consumed by SSE and service validation
- **Budget history**: `budget_snapshots` table; recorded every 30s by scheduler and immediately after mission launch/recall
- **Mission history**: `mission_log` table (append-only); every launch/recall action logged here

## Key Abstractions

**TelemetrySource:**
- Purpose: Represent any provider that can push telemetry to a cache (simulator, real hardware gateway, mock)
- Examples: `SimulatorTelemetrySource`, `MavlinkGatewayTelemetrySource`
- Pattern: Abstract class with concrete implementations; factory function `create_telemetry_source(cache)` selects based on env var

**Mission:**
- Purpose: Immutable record of a delivery task
- Examples: `Mission(id="...", drone_id="FALCON-05", zone="Downtown", distance_km=3.5, energy_cost_kwh=2.8, status="en_route", updated_at="2026-08-12T...")`
- Pattern: Dataclass with `to_dict()` for JSON serialization; `energy_cost_for(distance_km)` static method

**MissionError (and subclasses):**
- Purpose: Domain-specific exceptions raised by service layer when validation fails
- Examples: `UnknownDroneError`, `DroneAlreadyEnRouteError`, `InsufficientBudgetError`, `NoActiveMissionError`, `NoEligibleDroneError`
- Pattern: Exception hierarchy with `reason` attribute for HTTP status code translation

**TelemetryUpdate:**
- Purpose: Immutable snapshot of a drone's state at one instant
- Includes: battery_pct, previous_battery_pct, altitude_m, speed_kmh, status, timestamp
- Provides: battery_delta (pct change), battery_direction ("draining", "charging", "flat")

## Entry Points

**FastAPI app startup** (`backend/app/main.py:80-82`):
- Initialize Database, TelemetryCache, MissionQueue
- Load .env file (OPENROUTER_API_KEY, MAVLINK_GATEWAY_URL, LLM_MOCK)
- Create telemetry source (Simulator or MAVLink gateway based on env)
- Start three background schedulers as asyncio tasks
- Mount routers and static files

**Frontend page load** (`frontend/src/app/page.tsx:11-33`):
- Call `useTelemetryStream()` hook
- Establish SSE connection to `/api/stream/telemetry`
- Render Header, FleetRosterPanel with live telemetry snapshot, AI chat sidebar (placeholder)

**Browser WebSocket/SSE** (`frontend/src/lib/useTelemetryStream.ts`):
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

**What happens:** Today, mission launch requires an explicit drone_id in the request. If no drone is specified, the system must pick one.

**Why it's wrong:** Manual selection is error-prone at scale (dispatcher might pick an offline drone, leading to cascade failures). Auto-assignment is specified in PLAN.md but not yet implemented for the chat-based LLM integration.

**Do this instead:** Use `service.auto_assign_mission()` which filters by roster, telemetry safety, and active missions, then sorts by battery to pick the best candidate. Router already supports this path (POST /api/fleet/missions with no drone_id), but frontend dispatch UI hasn't been built yet (`frontend/src/app/page.tsx:8-10` notes this).

### Direct Database Queries in Routers

**What happens:** If route handler calls `db.fetchall()` directly instead of delegating to repository.

**Why it's wrong:** Breaks the service → repository layering; makes validation hard to test; couples HTTP concerns to SQL details.

**Do this instead:** Always route requests through the service layer (`backend/app/missions/service.py`). Service raises domain exceptions; router translates them to HTTP status codes. Keeps concerns separated.

### Mission Status Hardcoded as String

**What happens:** Mission.status is a string ("en_route", "delivered", "recalled"), not an enum.

**Why it's wrong:** Typos go undetected; downstream code must string-compare in multiple places.

**Do this instead:** Define a Python Enum (`MISSION_STATUSES` is close, but just a tuple; consider `from enum import Enum`). This is a low-risk refactor for a future phase.

## Error Handling

**Strategy:** Exceptions propagate up; converted to HTTP responses at the router boundary.

**Patterns:**
- **Domain validation**: Service layer raises subclasses of `MissionError` (e.g., `InsufficientBudgetError`, `UnknownDroneError`)
- **HTTP translation**: Router catches `MissionError`, looks up HTTP status code in `_ERROR_STATUS` dict, returns HTTPException (`backend/app/missions/router.py:15-37`)
- **Telemetry issues**: If telemetry source fails (e.g., MAVLink gateway offline), the background task logs and continues; cache retains last-known readings
- **Database errors**: If SQLite write fails (disk full, corruption), transaction rolls back and exception propagates up to router, which returns 500

## Cross-Cutting Concerns

**Logging:** Uses Python stdlib `logging` module with basicConfig at INFO level. Routers, service, and background tasks all log significant events (mission dispatch, drone assignment, SSE connection/disconnect). No structured logging (JSON) yet; suitable for ops-console output.

**Validation:** 
- Input validation: Pydantic models in router layer (e.g., `LaunchMissionRequest` with `distance_km > 0`)
- Business logic validation: Service layer (e.g., drone on roster? budget sufficient? telemetry safe?)
- Database constraints: Schema includes CHECK clauses and UNIQUE constraints to prevent invalid states

**Authentication:** None. Single-operator mode hardcoded (`operator_id="default"` in all tables). Chat and roster management (planned features) will need to extend this.

---

*Architecture analysis: 2026-08-12*
