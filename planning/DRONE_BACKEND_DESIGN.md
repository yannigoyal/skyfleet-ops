# Drone Backend Architecture — Design Document

## 1. Purpose and Scope

This document specifies the backend architecture for the four subsystems that make up the SkyFleet Ops server, per `planning/PLAN.md`:

1. **Drone telemetry** — already implemented (`backend/app/telemetry/`); summarized here for context and to show how the remaining subsystems consume it.
2. **Mission scheduling** — launching, recalling, and tracking delivery missions against the shared energy budget.
3. **Fleet management** — the operator's drone roster and energy-budget profile.
4. **AI flight control** — the LLM "flight director" chat integration that can read fleet state and auto-execute mission/roster actions.

It follows the conventions already established by the telemetry subsystem: strategy/factory patterns for swappable backends, a thread-safe single point of truth per data domain, FastAPI router factories that take their dependencies as constructor arguments (no globals), and full test coverage per module.

---

## 2. Module Layout

```
backend/app/
├── main.py                 # FastAPI app, lifespan wiring, router mounting
├── telemetry/               # EXISTING — see planning/TELEMETRY_SUMMARY.md
│   ├── models.py
│   ├── interface.py
│   ├── cache.py
│   ├── simulator.py
│   ├── mavlink_gateway.py
│   ├── factory.py
│   └── stream.py
├── db/                      # NEW — shared SQLite layer
│   ├── connection.py         # lazy init, WAL mode, serialized writes
│   ├── schema.py              # CREATE TABLE statements
│   └── seed.py                 # default operator profile + 10-drone roster
├── fleet/                   # NEW — roster + energy budget
│   ├── models.py
│   ├── repository.py
│   └── router.py             # /api/roster, /api/fleet, /api/fleet/history
├── missions/                # NEW — mission dispatch/recall/lifecycle
│   ├── models.py
│   ├── service.py             # launch/recall validation + execution
│   ├── scheduler.py            # background task: delivery completion, budget snapshots
│   └── router.py             # /api/fleet/missions
└── chat/                    # NEW — AI flight director
    ├── models.py              # structured-output schema (Pydantic)
    ├── context.py             # builds the fleet-state prompt
    ├── llm.py                  # LiteLLM → OpenRouter call (cerebras skill)
    ├── mock.py                  # LLM_MOCK deterministic responses
    └── router.py              # /api/chat
```

Each new subsystem gets its own router factory, mirroring `create_stream_router(telemetry_cache)`:

```python
def create_fleet_router(db: Database, telemetry_cache: TelemetryCache) -> APIRouter: ...
def create_missions_router(db: Database, telemetry_cache: TelemetryCache) -> APIRouter: ...
def create_chat_router(db: Database, telemetry_cache: TelemetryCache) -> APIRouter: ...
```

`main.py`'s `lifespan` becomes the single place that constructs the `Database`, `TelemetryCache`, and background tasks (telemetry source, budget-snapshot loop, mission-delivery loop) and wires them into each router.

---

## 3. Drone Telemetry (existing — recap for integration)

Already built and fully tested (69 tests, see `planning/TELEMETRY_SUMMARY.md`). The pieces downstream subsystems depend on:

- `TelemetryCache` — thread-safe, in-memory, holds the latest `TelemetryUpdate` per drone plus a monotonic `version` counter.
- `TelemetryUpdate.status` — one of `idle`, `in_flight`, `charging`, `low_battery`, `offline`, derived by the telemetry source itself (simulator or MAVLink gateway).
- `GET /api/stream/telemetry` — SSE push, ~500ms cadence, version-gated so idle connections don't resend unchanged data.

**Integration contract for mission/fleet code:** telemetry status and mission status are two independent state machines that must stay loosely coupled rather than merged:

- Telemetry `status` describes the drone's *physical* state as reported by the source (real or simulated) — a hardware truth the backend does not control.
- Mission `status` (`en_route` / `delivered` / `recalled`) describes the *business* state of a delivery — something the backend does control.

Mission validation reads telemetry (`cache.get_battery(drone_id)`, `cache.get(drone_id).status`) to decide whether a launch is safe (e.g., reject launch if status is `offline` or `low_battery`), but never writes to the telemetry cache. This keeps the telemetry subsystem's existing test suite and interface untouched.

---

## 4. Database Layer (`app/db/`)

### 4.1 Connection Management

SQLite is single-writer; FastAPI is async. Follow the same pattern `TelemetryCache` uses for thread safety, applied to the DB:

```python
# db/connection.py
class Database:
    """Lazy-initializing, thread-safe SQLite wrapper.

    A single sqlite3.Connection (WAL mode, check_same_thread=False) guarded
    by an asyncio.Lock for writes. Reads that don't need consistency across
    multiple statements can bypass the lock via a short-lived cursor.
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None

    def ensure_initialized(self) -> None:
        """Create tables + seed data if the DB file is new/empty. Called once at startup."""

    async def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        async with self._lock:
            return await asyncio.to_thread(self._conn.execute, sql, params)

    async def executescript_in_transaction(self, statements: list[tuple[str, tuple]]) -> None:
        """Run multiple statements atomically — used by mission launch/recall,
        which must update `missions`, `mission_log`, and `budget_snapshots`
        together or not at all."""
```

Using `asyncio.to_thread` keeps SQLite's blocking calls off the event loop without pulling in an extra dependency (`aiosqlite`); the `asyncio.Lock` serializes writes, which is exactly SQLite's actual concurrency limit anyway. WAL mode (`PRAGMA journal_mode=WAL`) lets concurrent readers (e.g., `GET /api/fleet` and `GET /api/fleet/history` firing at once) proceed without blocking on a writer.

### 4.2 Lazy Initialization

On startup (or first request touching the DB), `Database.ensure_initialized()`:
1. Creates `database/skyfleet.db` if absent (directory is the Docker volume mount point).
2. Runs `CREATE TABLE IF NOT EXISTS` for all six tables from `PLAN.md` §7.
3. If `operator_profile` has no `"default"` row, inserts it plus the ten `FALCON-01..10` roster rows (`db/seed.py`).

This matches the "no manual migration step, fresh volumes start seeded" requirement.

### 4.3 Schema

Implemented verbatim from `PLAN.md` §7 (`operator_profile`, `fleet_roster`, `missions`, `mission_log`, `budget_snapshots`, `chat_messages`), each with `operator_id TEXT DEFAULT 'default'` for future multi-tenancy. No changes proposed here — the plan's schema is sufficient and normalized correctly (mission history in `mission_log` is append-only and separate from the mutable `missions` row per drone).

---

## 5. Fleet Management (`app/fleet/`)

Owns the roster and the operator's energy-budget profile.

### 5.1 Responsibilities

- CRUD on `fleet_roster` (add/remove tracked drones).
- Read `operator_profile.energy_budget_kwh` and compute `remaining_kwh` (budget minus the sum of `energy_cost_kwh` for all `en_route` missions).
- Join roster with live telemetry (from `TelemetryCache`) for `GET /api/roster`.
- Adding a drone to the roster must also register it with the running `TelemetrySource` (`source.add_drone(drone_id)`) so it starts appearing on the SSE stream; removing it does the reverse. This is the one place fleet management touches telemetry, and it's a lifecycle call, not a data write.

### 5.2 Service Sketch

```python
# fleet/repository.py
async def add_drone(db: Database, drone_id: str) -> None: ...
async def remove_drone(db: Database, drone_id: str) -> None: ...
async def list_roster(db: Database) -> list[RosterEntry]: ...
async def get_energy_budget(db: Database) -> float: ...

# fleet/router.py
def create_fleet_router(db: Database, cache: TelemetryCache, telemetry_source: TelemetrySource) -> APIRouter:
    @router.post("/api/roster")
    async def add_to_roster(body: AddDroneRequest):
        await repository.add_drone(db, body.drone_id)
        await telemetry_source.add_drone(body.drone_id)
        return RosterEntry(...)
```

### 5.3 Validation Rules

- `POST /api/roster`: reject duplicate `drone_id` (unique constraint on `(operator_id, drone_id)`) with `409 Conflict`.
- `DELETE /api/roster/{drone_id}`: if the drone has an active (`en_route`) mission, reject with `409 Conflict` — a drone can't be de-fleeted mid-flight. Recall it first.

---

## 6. Mission Scheduling (`app/missions/`)

The most stateful subsystem: it enforces the shared energy budget, keeps `missions` (current state) and `mission_log` (append-only history) in sync, and drives mission lifecycle transitions over time.

### 6.1 Launch Flow (`POST /api/fleet/missions`)

Atomic, single-leg, no partial dispatch — per `PLAN.md`'s explicit simplification:

1. Validate the drone is on the roster and not already `en_route` (one active mission per drone — check `missions` for an existing row with `status='en_route'` for this `drone_id`).
2. Validate telemetry status is not `offline` or `low_battery` (read-only check against `TelemetryCache`).
3. Compute `energy_cost_kwh` from `distance_km` using a fixed energy-per-km constant (e.g., `ENERGY_COST_PER_KM = 0.8`), unless the caller supplies a value directly.
4. Validate `energy_cost_kwh <= remaining_kwh` (budget check — read current `budget - sum(active mission costs)`). If insufficient, return `422` with a machine-readable reason so the chat subsystem can relay it conversationally.
5. In one DB transaction: insert into `missions` (`status='en_route'`), insert into `mission_log` (`action='launch'`), insert a new `budget_snapshots` row with the updated `remaining_kwh`.
6. Return the created mission.

### 6.2 Recall Flow (`DELETE /api/fleet/missions/{drone_id}`)

1. Find the drone's active `missions` row (`status='en_route'`); `404` if none.
2. In one transaction: update `missions.status='recalled'`, insert `mission_log` (`action='recall'`), insert a `budget_snapshots` row. Energy already spent is **not** refunded — matches the "atomic mission, no re-routing" simplification (a recalled drone already burned the energy flying out).

### 6.3 Delivery Completion (background task, `missions/scheduler.py`)

Nothing in the manual API transitions a mission to `delivered` — it happens on its own once a drone arrives. A lightweight background loop (started in `main.py`'s `lifespan`, alongside the telemetry source):

```python
async def run_delivery_scheduler(db: Database, interval: float = 5.0) -> None:
    while True:
        await asyncio.sleep(interval)
        for mission in await repository.get_overdue_en_route_missions(db):
            await repository.mark_delivered(db, mission.id)
```

ETA is computed at launch time (not stored redundantly as a column beyond what's needed) as `distance_km / assumed_cruise_speed_kmh`, or, more realistically, refined using the drone's live `speed_kmh` from `TelemetryCache` at read time — `GET /api/fleet` can report a dynamic "ETA remaining" without needing a scheduler write. The scheduler only needs a stored `launched_at` timestamp (already covered by `updated_at` at insert time) plus distance to decide when a mission has "arrived," at which point it flips status to `delivered`. This keeps ETA display (frontend-facing, needs to be live and recalculated) separate from delivery-completion (backend-facing, needs to be a one-time state transition).

### 6.4 Budget Snapshots (background task)

Per `PLAN.md` §7: recorded every 30 seconds *and* immediately after every launch/recall. The periodic half is a second small background loop:

```python
async def run_budget_snapshot_loop(db: Database, interval: float = 30.0) -> None:
    while True:
        await asyncio.sleep(interval)
        remaining = await repository.compute_remaining_kwh(db)
        await repository.insert_budget_snapshot(db, remaining)
```

The launch/recall-triggered snapshot happens inline inside the mission service's transaction (§6.1/6.2), not via this loop.

### 6.5 Concurrency Note

Two simultaneous launch requests against the same drone, or two launches that together would overdraw the budget, are the real race condition here. Because `Database.execute`/transactions are serialized behind the single `asyncio.Lock`, and the budget check + insert happen inside one locked transaction, this is safe by construction — no separate optimistic-locking scheme is needed at this scale.

---

## 7. AI Flight Control (`app/chat/`)

### 7.1 Flow (`POST /api/chat`)

1. **Context build** (`context.py`): pull `remaining_kwh`, active missions, full roster with live telemetry (battery/status per drone), and a fleet-health rollup (e.g., average battery, count of `low_battery` drones) — reads `Database` + `TelemetryCache`, writes nothing.
2. **History**: load the last N (~10) rows from `chat_messages` for this `operator_id`, ordered by `created_at`.
3. **Prompt assembly**: system message ("SkyFleet flight director...", per `PLAN.md` §9) + serialized fleet context + history + the new user message.
4. **LLM call** (`llm.py`): via the `cerebras` skill, LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` on Cerebras, requesting structured output against the Pydantic schema below. If `LLM_MOCK=true`, `mock.py` short-circuits with deterministic canned responses instead (keyed on simple heuristics over the user message, e.g. containing "launch" → a mock launch action) so E2E tests stay fast and offline.
5. **Parse**: validate the LLM's JSON against the `ChatResponse` Pydantic model. On a malformed/non-conforming response, retry once, then fall back to `{"message": "I had trouble processing that — could you rephrase?", "missions": [], "roster_changes": []}` rather than surfacing a 500 to the operator.
6. **Auto-execute**: for each entry in `missions`/`roster_changes`, call the *same* `missions.service` / `fleet.repository` functions the manual REST endpoints use — no parallel code path, so validation (budget, roster uniqueness, active-mission checks) is identical whether a human or the LLM triggered it. Collect per-action success/failure into an `actions` result list.
7. **Persist**: insert a `chat_messages` row for the user's message (`actions=null`) and one for the assistant's reply (`actions=<JSON of what was executed>`).
8. **Respond**: return the full structured response plus executed-action results in one JSON payload (no token streaming, per `PLAN.md` — Cerebras is fast enough that a loading spinner suffices).

### 7.2 Structured Output Schema (`chat/models.py`)

```python
class MissionAction(BaseModel):
    drone_id: str
    action: Literal["launch", "recall"]
    zone: str | None = None        # required for launch
    distance_km: float | None = None  # required for launch

class RosterChange(BaseModel):
    drone_id: str
    action: Literal["add", "remove"]

class ChatResponse(BaseModel):
    message: str
    missions: list[MissionAction] = []
    roster_changes: list[RosterChange] = []
```

This is passed to LiteLLM as a JSON-schema response format, matching `PLAN.md` §9's example exactly.

### 7.3 Why Auto-Execution Reuses the REST Service Layer

Keeping `missions/service.py` and `fleet/repository.py` as the single source of truth for "is this action valid and how do I apply it" means the chat subsystem is a thin orchestration layer: build context → call LLM → call the same functions `missions/router.py` and `fleet/router.py` call. This also means unit tests for launch/recall validation (insufficient budget, drone already in flight, etc.) only need to be written once and cover both entry points.

---

## 8. Example APIs

### 8.1 `GET /api/fleet`

```json
{
  "energy_budget_kwh": 500.0,
  "remaining_kwh": 412.4,
  "active_mission_count": 3,
  "missions": [
    {
      "id": "6f3e...",
      "drone_id": "FALCON-03",
      "zone": "Riverside",
      "distance_km": 4.2,
      "energy_cost_kwh": 3.36,
      "status": "en_route",
      "eta_minutes": 6.1,
      "updated_at": "2026-08-05T14:02:11Z"
    }
  ]
}
```

### 8.2 `POST /api/fleet/missions`

Request:
```json
{ "drone_id": "FALCON-03", "zone": "Riverside", "distance_km": 4.2 }
```

Response `201`:
```json
{
  "id": "6f3e...",
  "drone_id": "FALCON-03",
  "zone": "Riverside",
  "distance_km": 4.2,
  "energy_cost_kwh": 3.36,
  "status": "en_route",
  "updated_at": "2026-08-05T14:02:11Z"
}
```

Response `422` (insufficient budget):
```json
{ "detail": { "reason": "insufficient_budget", "requested_kwh": 3.36, "remaining_kwh": 1.2 } }
```

### 8.3 `DELETE /api/fleet/missions/{drone_id}`

Response `200`:
```json
{ "id": "6f3e...", "drone_id": "FALCON-03", "status": "recalled", "updated_at": "2026-08-05T14:05:33Z" }
```

### 8.4 `GET /api/fleet/history`

```json
{
  "snapshots": [
    { "remaining_kwh": 500.0, "recorded_at": "2026-08-05T14:00:00Z" },
    { "remaining_kwh": 496.64, "recorded_at": "2026-08-05T14:02:11Z" }
  ]
}
```

### 8.5 `GET /api/roster`

```json
{
  "drones": [
    {
      "drone_id": "FALCON-01",
      "added_at": "2026-08-01T00:00:00Z",
      "telemetry": { "battery_pct": 87.5, "altitude_m": 120.0, "speed_kmh": 38.2, "status": "in_flight" }
    }
  ]
}
```

### 8.6 `POST /api/roster` / `DELETE /api/roster/{drone_id}`

Request: `{ "drone_id": "FALCON-11" }` → `201` with the new `RosterEntry`.
`DELETE` → `204`, or `409` with `{"detail": {"reason": "active_mission"}}` if in flight.

### 8.7 `POST /api/chat`

Request:
```json
{ "message": "Send a drone to Riverside, we've got a backlog there" }
```

Response:
```json
{
  "message": "FALCON-03 has the healthiest battery (91%) and is idle, so I launched it to Riverside — 3.4 kWh, ETA ~6 min. Budget now at 496.6/500 kWh.",
  "missions": [
    { "drone_id": "FALCON-03", "action": "launch", "zone": "Riverside", "distance_km": 4.2 }
  ],
  "roster_changes": [],
  "actions_executed": [
    { "type": "mission_launch", "drone_id": "FALCON-03", "success": true }
  ]
}
```

---

## 9. Testing Strategy for New Modules

Following the bar set by the telemetry suite (69 tests, 83% coverage):

- **`db/`**: schema creation is idempotent, seed data only inserts once, WAL mode is active, concurrent writes serialize correctly.
- **`fleet/`**: roster add/remove (including duplicate/not-found/active-mission-conflict paths), budget arithmetic, roster+telemetry join shape.
- **`missions/`**: launch validation matrix (happy path, insufficient budget, drone already en route, drone offline/low-battery, unknown drone), recall validation (no active mission), delivery-scheduler transition timing, budget-snapshot insertion on every launch/recall and on the 30s tick.
- **`chat/`**: structured-output parsing against valid and malformed LLM responses, mock-mode determinism, auto-execution delegating to (and respecting failures from) the same validation used by the REST endpoints, chat history persistence and ordering.
- **API-level (`backend/tests/`)**: status codes and response shapes for every endpoint in §8, using FastAPI's `TestClient` against an in-memory/temp-file SQLite DB and `LLM_MOCK=true`.

E2E scenarios (`tests/`, Playwright) remain as scoped in `PLAN.md` §12 and exercise these APIs end-to-end through the real frontend.
