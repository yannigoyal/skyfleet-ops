# Phase 1: Roster Module - Research

**Researched:** 2026-08-12
**Domain:** FastAPI/SQLite CRUD module, in-process cross-module service composition, pluggable telemetry-source lifecycle
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Reuse of prior unmerged work**
- **D-01:** Port and extend the roster code found on the unmerged `agent_team_work` branch
  (commit `2ba52a8`, files `backend/app/roster/{models,repository,router,__init__}.py`) as the
  starting point, rather than writing from scratch. — **Reversibility:** reversible — it's a
  starting point for this phase's plan, not a merged dependency; the planner/executor can still
  rewrite pieces that don't fit.
- **D-02:** That branch's code is missing the `service.py` layer required by ROST-04 (router calls
  `repository` directly) and has no handling for removing a drone with an active mission. Both must
  be added — the ported code is not a drop-in, it needs a service layer inserted between router and
  repository, following `missions/service.py`'s shape.

**Active-mission handling on removal**
- **D-03:** Removing a drone that has an active (`en_route`) mission auto-recalls that mission
  (same effect as `DELETE /api/fleet/missions/{drone_id}`) before deleting the roster row, so one
  operator action always leaves the system consistent. This requires `roster.service` to call
  `missions.service.recall_mission()` (or equivalent) as part of the remove flow — a new
  cross-module dependency from `roster/` into `missions/` that doesn't exist in the ported branch
  code. — **Reversibility:** costly — **rationale:** changing this later means either adding a
  migration path for orphaned missions already created under the old behavior, or reworking the
  remove endpoint's response contract if callers start relying on the auto-recall side effect.

**Telemetry sync failure handling**
- **D-04:** If the roster DB write succeeds but `TelemetrySource.add_drone()` /
  `remove_drone()` raises, log the error and continue — do not roll back the DB write. The
  database (`fleet_roster` table) is the source of truth for the roster; a telemetry cache miss
  self-heals on the next update cycle or a later retry. Matches the project's existing pattern of
  telemetry issues being logged, not fatal.

**Drone ID validation**
- **D-05:** Accept any non-empty string as `drone_id` when adding a drone (matches the prior
  branch's `Field(min_length=1)` and how `missions.drone_id` is already treated — a plain string,
  no enforced naming convention).

### Claude's Discretion
- Exact SQL/transaction shape for the auto-recall-then-remove flow (single transaction vs.
  sequential calls) — follow whatever `missions/repository.py` conventions make this safe under
  concurrent access, consistent with the project's single-writer-lock pattern.
- Response payload shape for `_entry_response`-equivalent helper (which telemetry fields to merge
  into each roster entry) — the ported branch's `_TELEMETRY_FIELDS = (battery_pct, altitude_m,
  speed_kmh, status)` is a reasonable default; adjust only if `GET /api/roster` needs more per
  Phase 3's frontend requirements.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ROST-01 | Operator can add a drone to the fleet roster via `POST /api/roster` | Ported branch `repository.add_drone()` + new `service.add_drone()` layer; see Code Examples and Pattern 1 |
| ROST-02 | Operator can remove a drone from the fleet roster via `DELETE /api/roster/{drone_id}` | Ported branch `repository.remove_drone()` + new `service.remove_drone()` with D-03 auto-recall (see Pitfall 2, Open Question 1) and D-04 telemetry-failure handling |
| ROST-03 | Operator can view the current fleet roster with latest telemetry via `GET /api/roster` | Ported branch `router.py`'s `_entry_response()` telemetry-merge helper, reading from `TelemetryCache.get()` |
| ROST-04 | Roster module (`backend/app/roster/`) follows the same models/service/repository/router layering as `backend/app/missions/` | See Recommended Project Structure and Pitfall 1 — requires adding the missing `service.py` the ported branch lacks |
</phase_requirements>

## Summary

This phase ports a working but incomplete roster implementation from an unmerged git branch
(`agent_team_work` @ `2ba52a8`) into `backend/app/roster/`, adds the missing `service.py` layer,
and wires an active-mission auto-recall on drone removal. No new external packages are required —
everything needed (`fastapi`, `pydantic`, stdlib `sqlite3`) is already a dependency of the existing
`missions` module this phase mirrors.

All of the ported branch code (`models.py`, `repository.py`, `router.py`, `__init__.py`) was
retrieved via `git show 2ba52a8:backend/app/roster/<file>` and diffed conceptually against the
current `backend/app/db/schema.py` and `backend/app/db/connection.py`. **No drift was found** — the
ported code's SQL (`INSERT INTO fleet_roster (id, operator_id, drone_id, added_at)`, `DELETE FROM
fleet_roster WHERE operator_id = ? AND drone_id = ?`) matches the current `fleet_roster` schema
exactly, and its `Database` calls (`db.execute`, `db.fetchall`, `db.transaction`) match the current
`Database` class's public API exactly. The ported code is safe to reuse as-is for `models.py` and
`repository.py`; `router.py` needs its direct `repository` calls replaced with `service` calls per
D-02/D-03.

One integration gap was found that the ported branch code does not address and that CONTEXT.md's
canonical refs don't fully surface: **`backend/app/main.py` currently constructs the
`TelemetrySource` instance *inside* the `lifespan` async context manager**, as a local variable, and
mounts `missions_router` at *module level* before `lifespan` ever runs. The roster router's
factory function needs a live `TelemetrySource` reference at mount time (`create_roster_router(db,
cache, source)`), but under the current wiring there is no such reference available at module
level — `source` doesn't exist until the app starts serving. This must be resolved by moving the
`create_telemetry_source(cache)` call (which only *constructs* the source, does not start it) to
module level, alongside `telemetry_cache`/`mission_queue`/`database`, and leaving the `await
source.start(DEFAULT_FLEET)` call inside `lifespan`. This is a one-line-move refactor, not a design
change, and it exactly matches the project's existing pattern of module-level singletons passed
into router factories.

**Primary recommendation:** Port `models.py` and `repository.py` from the branch unchanged; rewrite
`router.py` to call a new `service.py` (which owns the add/remove business logic, including the
D-03 auto-recall-into-`missions.service.recall_mission()` call and the D-04 log-and-continue
`TelemetrySource` sync); move `create_telemetry_source()` construction to module level in
`main.py` so the roster router factory can receive a live `source` reference at the same place
`missions_router` is currently mounted.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Roster CRUD (add/remove/list drones) | API/Backend | Database/Storage | `fleet_roster` table (`backend/app/db/schema.py:12-18`) is the source of truth; validated and persisted through `roster/repository.py` |
| Telemetry merge into `GET /api/roster` response | API/Backend | — | In-process read from `TelemetryCache` (`backend/app/telemetry/cache.py:56-59`), no separate service call |
| Telemetry source sync on add/remove | API/Backend | — | `TelemetrySource.add_drone()`/`remove_drone()` (`backend/app/telemetry/interface.py:42-54`) runs in-process, same asyncio event loop, no network hop for the simulator path |
| Auto-recall on roster removal (D-03) | API/Backend | Database/Storage | `roster.service` calls `missions.service.recall_mission()` (`backend/app/missions/service.py:49-51`), which delegates to `missions/repository.py::recall()`'s atomic transaction |

## Standard Stack

### Core
No new packages. This phase reuses the exact dependency set already declared in
`backend/pyproject.toml:6-11` (`fastapi>=0.115.0`, plus stdlib `sqlite3`, `uuid`, `datetime`) and
already exercised identically by `backend/app/missions/router.py:1-6` (`fastapi.APIRouter`,
`fastapi.HTTPException`, `fastapi.Response`, `pydantic.BaseModel`, `pydantic.Field`).

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.115.0 [VERIFIED: backend/pyproject.toml:6] | Router, request models, HTTP error mapping | Already the project's REST framework; `missions/router.py` uses identical primitives |
| pydantic | bundled with fastapi (v2) [ASSUMED — not pinned directly in pyproject.toml, transitive via fastapi] | `AddDroneRequest` request validation | Same pattern as `missions/router.py:25-28`'s `LaunchMissionRequest` |

### Supporting
None — no new supporting libraries needed.

### Alternatives Considered
None — CONTEXT.md D-01 locks the ported branch code as the starting point; no alternative
implementation approach was explored per the "don't research alternatives to locked decisions"
scoping rule.

**Installation:** None required — no new dependencies.

## Package Legitimacy Audit

Not applicable. This phase installs zero new external packages; it reuses `fastapi`/`pydantic`
already present in `backend/pyproject.toml` and exercised by the sibling `missions` module.

## Architecture Patterns

### System Architecture Diagram

```
Operator (HTTP client)
   │
   │ POST /api/roster {drone_id}          GET /api/roster        DELETE /api/roster/{drone_id}
   ▼
roster/router.py  (create_roster_router(db, cache, source))
   │  - AddDroneRequest validation (Pydantic)
   │  - RosterError → HTTPException via _ERROR_STATUS
   ▼
roster/service.py   ◄──────────────────────────────┐
   │  - add_drone(): delegate to repository          │  cross-module call (D-03)
   │  - remove_drone(): if active mission exists →   │
   │      call missions.service.recall_mission()  ───┘
   │      then delegate to repository.remove_drone()
   ▼
roster/repository.py  (async db.execute / db.transaction)
   │
   ▼
fleet_roster table (SQLite, via app/db/connection.py::Database)
   │
   └─ on success, roster/service.py also calls source.add_drone()/remove_drone()
        (TelemetrySource — simulator or MAVLink gateway)
        │  success → TelemetryCache updated, next GET /api/roster reflects it
        └  exception → logged, NOT rolled back (D-04) — DB is source of truth
```

Primary use case trace (remove a drone with an active mission):
`DELETE /api/roster/FALCON-03` → `router.py` calls `service.remove_drone()` → service checks
`missions.repository.get_active_mission_for_drone()` → if found, calls
`missions.service.recall_mission()` (writes to `missions`, `mission_log`, `budget_snapshots` inside
one locked transaction, per `missions/repository.py:165-190`) → service calls
`roster.repository.remove_drone()` (deletes the `fleet_roster` row, per ported
`repository.py::remove_drone`) → service calls `source.remove_drone(drone_id)` (best-effort,
log-and-continue on failure) → router returns `204 No Content`.

### Recommended Project Structure
```
backend/app/roster/
├── __init__.py      # exports: create_roster_router, RosterError, RosterEntry, DroneAlreadyTrackedError, UnknownDroneError
├── models.py         # RosterEntry dataclass, RosterError hierarchy — port unchanged from branch
├── service.py         # NEW — add_drone(), remove_drone() with auto-recall + telemetry sync; mirrors missions/service.py shape
├── repository.py     # port unchanged from branch — SQL against fleet_roster
└── router.py           # rewritten to call service.* instead of repository.* directly
```

### Pattern 1: Factory-function router with explicit dependencies
**What:** `create_roster_router(db: Database, cache: TelemetryCache, source: TelemetrySource) ->
APIRouter` — no module-level globals inside `roster/`, dependencies passed at construction time.
**When to use:** Always, for consistency with `missions/router.py`.
**Example:**
```python
# Source: backend/app/missions/router.py:49-51 (read this session)
def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:
    """Create the mission-dispatch router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/fleet", tags=["missions"])
```
The roster equivalent (per CONTEXT.md's own note, `backend/app/roster/router.py` on the branch
already has this shape minus the `service` split):
```python
# Source: git show 2ba52a8:backend/app/roster/router.py (read this session, lines as shown)
def create_roster_router(
    db: Database, cache: TelemetryCache, source: TelemetrySource | None = None
) -> APIRouter:
    """Create the roster router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/roster", tags=["roster"])
```

### Pattern 2: Domain exception hierarchy + `_ERROR_STATUS` lookup
**What:** Base exception with a `reason: str` class attribute; router-level dict maps `reason` →
HTTP status code.
**When to use:** All roster validation failures.
**Example — current missions convention (must be mirrored, not copied literally, since reasons differ):**
```python
# Source: backend/app/missions/router.py:15-22 (read this session)
_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_en_route": 409,
    "drone_unavailable": 409,
    "no_active_mission": 404,
    "insufficient_budget": 422,
    "no_eligible_drone": 422,
}
```
**Example — ported roster branch's existing (smaller) table, verified to still compile against
current schema:**
```python
# Source: git show 2ba52a8:backend/app/roster/router.py (read this session)
_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_tracked": 409,
}
```
This table needs no new entries for D-03's auto-recall failure path *if* recall failures are
swallowed rather than surfaced (see Common Pitfalls below) — but if the plan chooses to surface a
recall failure during remove, a new reason (e.g., `"recall_failed"`) and status code must be added.

### Pattern 3: Atomic multi-statement transaction via `db.transaction(fn)`
**What:** `Database.transaction()` runs a synchronous callback against one `sqlite3.Connection`
inside a commit/rollback boundary, executed off the event loop via `asyncio.to_thread` and
serialized by a single `asyncio.Lock`.
**When to use:** Any multi-statement roster operation that must be atomic under concurrent access
(per Claude's Discretion note in CONTEXT.md).
**Example:**
```python
# Source: backend/app/db/connection.py:73-89 (read this session)
async def transaction(self, fn: Callable[[sqlite3.Connection], T]) -> T:
    """Run `fn(conn)` synchronously under the write lock, inside one SQLite
    transaction. `fn` may issue multiple statements and raise to abort —
    the transaction is rolled back and the exception propagates.
    """
    async with self._lock:
        return await asyncio.to_thread(self._transaction_sync, fn)
```
Note this lock is a *single* `asyncio.Lock` shared by the whole `Database` instance
(`backend/app/db/connection.py:28`). If `roster.service.remove_drone()` calls
`missions.service.recall_mission()` (which itself calls `db.transaction(...)`) and *then*
separately calls `roster.repository.remove_drone()` (which also calls `db.transaction(...)`), these
are **two separate lock acquisitions**, not one atomic unit spanning both the `missions` and
`fleet_roster` tables. See Common Pitfalls — this is a real (if narrow) TOCTOU risk that the planner
should decide how to handle (see Open Questions).

### Anti-Patterns to Avoid
- **Router calling `repository` directly:** The ported branch's `router.py` does this
  (`repository.add_drone(db, request.drone_id)` called directly from the route handler,
  `git show 2ba52a8:backend/app/roster/router.py`). D-02 requires this go through a new
  `service.py` instead, matching `missions/router.py:11` (`from . import repository, service`) —
  the router should only import `service`, not `repository`, once the rewrite is done (see
  `missions/router.py:11` for the exact import shape to mirror... note it imports `repository` too,
  for `get_fleet_status`'s reads — so roster's router importing both `service` for writes and
  `repository` for the plain `list_drones()` read is consistent with the existing pattern, not a
  violation of it).
- **Rolling back the DB write when telemetry sync fails:** D-04 explicitly forbids this. Do not
  wrap the `source.add_drone()`/`remove_drone()` call inside the same `db.transaction()` callback —
  it must happen *after* the DB transaction commits, in a separate try/except that only logs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Recall-mission-then-remove-roster-row transaction shape | A new bespoke SQL transaction spanning both `missions` and `fleet_roster` tables | Sequential calls: `missions.service.recall_mission(db, drone_id)` then `roster.repository.remove_drone(db, drone_id)` | The codebase's `Database` class already serializes all writes behind one `asyncio.Lock` (`backend/app/db/connection.py:28`), so two sequential locked transactions cannot interleave with a *third* concurrent writer — the only residual risk is a crash between the two calls, which D-03's "reversibility: costly" note already acknowledges as an accepted tradeoff, not a bug to engineer away with two-phase commit |
| Telemetry drone-registration retry logic | A custom retry/backoff wrapper around `source.add_drone()`/`remove_drone()` | Plain try/except + log (D-04) | The project's own telemetry source implementations (`simulator.py:280-292`, `mavlink_gateway.py:72-82`) never raise in normal operation — `add_drone`/`remove_drone` are simple in-memory list mutations for the simulator, and the MAVLink gateway's versions (`mavlink_gateway.py:72-82`) are also non-raising (list mutation only; the actual network I/O happens in the separate `_poll_loop`) — a retry mechanism would be solving a problem that doesn't exist in either implementation today |

**Key insight:** Both `TelemetrySource` implementations' `add_drone()`/`remove_drone()` methods are
synchronous-in-effect (no I/O that can fail) as of this commit — `simulator.py:280-292` and
`mavlink_gateway.py:72-82`, both read this session. D-04's log-and-continue handling is a safety
net for future implementations (e.g., a MAVLink gateway variant that does an immediate registration
call), not a currently-exercised failure path. Don't over-engineer retry/circuit-breaker logic here.

## Common Pitfalls

### Pitfall 1: Missing `service.py` import surface breaks the mirror requirement (ROST-04)
**What goes wrong:** Copying the ported branch's `router.py` verbatim (which calls `repository`
directly) technically satisfies ROST-01/02/03 but fails ROST-04's explicit requirement that the
module "follows the same models/service/repository/router layering as `backend/app/missions/`".
**Why it happens:** The branch code was written before this requirement existed (CONTEXT.md D-02).
**How to avoid:** Add `roster/service.py` with at least `add_drone()` and `remove_drone()` async
functions; route handlers call `service.*`, not `repository.*`, for all writes (reads like
`list_drones()` can go straight to `repository.list_roster_entries()`, matching how
`missions/router.py`'s `get_fleet_status` calls `repository.get_remaining_kwh()` directly rather
than through `service`).
**Warning signs:** `roster/router.py` importing `repository` for anything beyond simple reads, or
`roster/service.py` not existing at all.

### Pitfall 2: Auto-recall-then-remove is not one atomic transaction
**What goes wrong:** Because `missions.service.recall_mission()` and `roster.repository.remove_drone()`
each open and close their own `db.transaction()` (separate lock acquisitions on the same
`asyncio.Lock`), a crash or exception between the two calls leaves a recalled mission but the drone
still on the roster (or vice versa, if remove is attempted first).
**Why it happens:** `missions/repository.py::recall()` (lines 165-190, read this session) and the
ported `roster/repository.py::remove_drone()` are each self-contained atomic units; nothing in the
current codebase composes two `Database.transaction()` calls into one wider transaction — the
`Database` class's public API (`execute`, `fetchall`, `fetchone`, `transaction`) has no
"begin nested / two-repo" primitive (`backend/app/db/connection.py:53-94`, read this session).
**How to avoid:** Recall first, then remove — if recall fails with `NoActiveMissionError`, treat it
as "no active mission, proceed to remove" (not a real error, since the point was just to clear an
active mission if one exists). If recall succeeds and remove then fails, the drone stays recalled
but on the roster — safe (idempotent-ish) since a re-attempt of the DELETE will just recall a
no-op and remove cleanly. This ordering makes the failure mode "roster row still present after
mission recalled" rather than "mission still active after roster row removed," which is the safer
of the two to leave inconsistent.
**Warning signs:** Any design that tries to wrap both calls in a single new cross-module
`db.transaction()` callback — this would require `roster/repository.py` and `missions/repository.py`
functions to accept a raw `conn` parameter instead of a `Database` instance, a bigger refactor not
scoped to this phase (see Open Questions).

### Pitfall 3: Router-level construction timing for `TelemetrySource`
**What goes wrong:** `backend/app/main.py:56-77`'s `lifespan()` currently constructs the
`TelemetrySource` *inside* the async context manager (`source = create_telemetry_source(telemetry_cache)`
at line 60) — a local variable never available outside `lifespan`. Meanwhile router mounting
(`app.include_router(create_missions_router(...))`) happens at module level, lines 81-82, *before*
`lifespan` ever executes. If a plan naively tries to call
`create_roster_router(database, telemetry_cache, source)` at module level using the `source` name
from inside `lifespan`, it will hit a `NameError` — that `source` variable doesn't exist there.
**Why it happens:** The `missions` router never needed a `TelemetrySource` reference, so this
timing mismatch was never exercised before.
**How to avoid:** Move `create_telemetry_source(telemetry_cache)` (construction only — cheap,
non-blocking, verified by its own docstring: "Returns an unstarted source. Caller must await
source.start(drone_ids)." — `backend/app/telemetry/factory.py:16-23`, read this session) to module
level, alongside `telemetry_cache = TelemetryCache()` / `mission_queue = MissionQueue()` / `database
= Database(...)` (`backend/app/main.py:51-53`, read this session). Keep `await
telemetry_source.start(DEFAULT_FLEET)` inside `lifespan`. Then `app.include_router(create_roster_router(database,
telemetry_cache, telemetry_source))` can sit next to the other `include_router` calls at module
level, exactly like `missions_router`.
**Warning signs:** Any plan step that tries to mount `roster_router` from *inside* `lifespan()`
(e.g., `app.include_router(...)` after `await source.start(...)` but before `yield`) — this works
technically (FastAPI allows route registration before the app starts serving) but breaks the
project's established "all routers mounted at module level" convention and complicates
`TestClient`-based testing, since tests construct their own minimal `FastAPI()` app + router
without invoking `main.py`'s `lifespan` at all (see `backend/tests/missions/test_router.py:13-16`,
read this session — `_client()` builds a bare `FastAPI()` and calls `app.include_router(...)`
directly, no lifespan involved).

## Code Examples

### Existing roster branch models (port as-is)
```python
# Source: git show 2ba52a8:backend/app/roster/models.py (read this session)
@dataclass(frozen=True, slots=True)
class RosterEntry:
    """A tracked drone — mirrors a row in the `fleet_roster` table."""

    id: str
    operator_id: str
    drone_id: str
    added_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"drone_id": self.drone_id, "added_at": self.added_at}


class RosterError(Exception):
    reason: str = "roster_error"


class DroneAlreadyTrackedError(RosterError):
    reason = "drone_already_tracked"


class UnknownDroneError(RosterError):
    reason = "unknown_drone"
```

### Existing roster branch repository (port as-is — verified against current schema/connection API)
```python
# Source: git show 2ba52a8:backend/app/roster/repository.py (read this session)
async def add_drone(
    db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID
) -> RosterEntry:
    entry = RosterEntry(
        id=str(uuid.uuid4()), operator_id=operator_id, drone_id=drone_id, added_at=_now()
    )
    try:
        await db.execute(
            "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
            (entry.id, entry.operator_id, entry.drone_id, entry.added_at),
        )
    except sqlite3.IntegrityError as exc:
        raise DroneAlreadyTrackedError(drone_id) from exc
    return entry


async def remove_drone(db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID) -> None:
    def _txn(conn: sqlite3.Connection) -> None:
        cursor = conn.execute(
            "DELETE FROM fleet_roster WHERE operator_id = ? AND drone_id = ?",
            (operator_id, drone_id),
        )
        if cursor.rowcount == 0:
            raise UnknownDroneError(drone_id)

    await db.transaction(_txn)
```
This relies on the `UNIQUE (operator_id, drone_id)` constraint
(`backend/app/db/schema.py:17`, read this session — `UNIQUE (operator_id, drone_id)`) to trigger
`sqlite3.IntegrityError` on duplicate add, exactly as the branch code assumes. Confirmed still
correct against the current schema.

### Missions recall — the function `roster.service.remove_drone()` must call for D-03
```python
# Source: backend/app/missions/service.py:49-51 (read this session)
async def recall_mission(db: Database, drone_id: str) -> Mission:
    """Recall the drone's active mission. Raises NoActiveMissionError if none."""
    return await repository.recall(db, drone_id)
```
`NoActiveMissionError` (`backend/app/missions/models.py:74-79`, read this session:
`class NoActiveMissionError(MissionError): reason = "no_active_mission"`) is the exception to catch
and treat as "nothing to recall, proceed" in the roster removal flow — not a failure to surface to
the operator.

### `main.py` module-level singleton pattern to extend
```python
# Source: backend/app/main.py:51-53 (read this session)
telemetry_cache = TelemetryCache()
mission_queue = MissionQueue()
database = Database(_default_db_path())
```
Add a fourth module-level singleton here: `telemetry_source = create_telemetry_source(telemetry_cache)`
— construction only, matching the factory's documented contract
(`backend/app/telemetry/factory.py:22`, read this session: `"Returns an unstarted source. Caller
must await source.start(drone_ids)."`).

```python
# Source: backend/app/main.py:81-82 (read this session)
app.include_router(create_stream_router(telemetry_cache))
app.include_router(create_missions_router(database, telemetry_cache, mission_queue))
```
Add: `app.include_router(create_roster_router(database, telemetry_cache, telemetry_source))` on the
next line, same module-level block.

```python
# Source: backend/app/main.py:56-77 (read this session)
@asynccontextmanager
async def lifespan(app: FastAPI):
    database.ensure_initialized()

    source = create_telemetry_source(telemetry_cache)
    await source.start(DEFAULT_FLEET)
    app.state.telemetry_source = source
```
Change to use the module-level `telemetry_source` instead of a local `source`:
`await telemetry_source.start(DEFAULT_FLEET)`, drop the now-redundant local construction line, keep
`app.state.telemetry_source = telemetry_source` for any code that reads it off `Request.app.state`.

## State of the Art

Not applicable — this is an internal architectural pattern-matching exercise (port + extend
existing sibling-module conventions), not a fast-moving external library integration. No
deprecation/versioning concerns.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pydantic` is bundled as a transitive dependency of `fastapi>=0.115.0` and is v2 (matching `BaseModel`/`Field` usage already in `missions/router.py`) — not independently verified via `pip show`/`uv pip list` due to a sandboxed `uv` cache write failure in this session | Standard Stack | Low — `missions/router.py` already imports and uses `pydantic.BaseModel`/`Field` successfully in the current codebase, so the dependency is de facto proven to be present and working; the only unverified detail is the exact version string |
| A2 | Neither `TelemetrySource` implementation's `add_drone()`/`remove_drone()` can raise in normal operation (verified by reading both implementations, but "normal operation" assumes no future implementation changes this) | Don't Hand-Roll, Pitfall discussion | Low — D-04's log-and-continue handling already covers this defensively regardless; the assumption only affects how much test coverage to prioritize for the exception path |

## Open Questions

1. **Should a failed auto-recall during roster removal be surfaced to the caller, or silently
   proceed to removal anyway?**
   - What we know: D-03 requires auto-recall to happen; `NoActiveMissionError` (no mission to
     recall) is expected and should be treated as success-equivalent. `InsufficientBudgetError` and
     other `MissionError` subtypes cannot occur during a *recall* (only during *launch* — verified:
     `missions/repository.py::recall()` lines 165-190 has no budget check, only the "no active
     mission" check), so in practice recall can only fail with `NoActiveMissionError`.
   - What's unclear: Whether the plan should still wrap the recall call in an explicit
     `except NoActiveMissionError: pass` for defensive clarity, or just call `recall_mission()`
     unconditionally after checking `repository.get_active_mission_for_drone()` returns non-None
     first (avoiding the exception path entirely).
   - Recommendation: Check first with `missions.repository.get_active_mission_for_drone(db,
     drone_id)` (already exists, `missions/repository.py:72-79`, read this session), and only call
     `recall_mission()` if it returns non-None. This avoids relying on exception-as-control-flow and
     keeps `roster/service.py` reading cleanly as "check, then act."

2. **Does `roster.service` importing from `app.missions` create a circular import risk?**
   - What we know: `app.missions` package (`backend/app/missions/__init__.py:1-14`, read this
     session) exports `MissionQueue`, `create_missions_router`,
     `run_assignment_scheduler`/`run_budget_snapshot_loop`/`run_delivery_scheduler` — it does not
     import anything from `app.roster` (roster doesn't exist yet on `main`). A one-directional
     `roster → missions` import is safe.
   - What's unclear: Whether `roster/service.py` should import `from app.missions import service as
     missions_service` (whole module) or `from app.missions.service import recall_mission`
     (specific function) — both work; the latter is more explicit about the exact cross-module
     dependency surface CONTEXT.md flags as new (line 125-127 of CONTEXT.md).
   - Recommendation: `from app.missions.service import recall_mission` — narrowest possible import,
     easiest to grep for if this coupling ever needs to be found/removed later.

## Environment Availability

Not applicable — this phase has no external tool/service/runtime dependencies beyond what's already
running (Python 3.12, the existing SQLite file, the existing in-process telemetry simulator). No
new environment probing needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0+ with pytest-asyncio (`asyncio_mode = "auto"`) [VERIFIED: backend/pyproject.toml:29-30 lines "pytest>=8.3.0", "pytest-asyncio>=0.24.0"; config at lines shown below] |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `python_files = ["test_*.py"]`, `asyncio_mode = "auto"` [VERIFIED: backend/pyproject.toml, read this session] |
| Quick run command | `uv run --extra dev pytest tests/roster/ -v` |
| Full suite command | `uv run --extra dev pytest -v` (per `backend/CLAUDE.md` "Running Tests" section) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROST-01 | `POST /api/roster` adds a drone, appears with live telemetry | unit (router) | `pytest tests/roster/test_router.py::TestAddDrone -x` | ❌ Wave 0 |
| ROST-01 | `repository.add_drone()` inserts row, raises on duplicate | unit (repository) | `pytest tests/roster/test_repository.py::TestAddDrone -x` | ❌ Wave 0 |
| ROST-02 | `DELETE /api/roster/{drone_id}` removes drone; drone with active mission is auto-recalled first | unit (service) | `pytest tests/roster/test_service.py::TestRemoveDrone -x` | ❌ Wave 0 |
| ROST-02 | Telemetry sync failure on remove is logged, not fatal (D-04) | unit (service, mocked source) | `pytest tests/roster/test_service.py::TestTelemetrySyncFailure -x` | ❌ Wave 0 |
| ROST-03 | `GET /api/roster` merges roster with latest `TelemetryCache` reading | unit (router) | `pytest tests/roster/test_router.py::TestListDrones -x` | ❌ Wave 0 |
| ROST-04 | `roster/` module layering matches `missions/` (models/service/repository/router) | structural (import check) | `pytest tests/roster/test_service.py -x` (service.py existing + importable is a precondition of the whole test file running) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run --extra dev pytest tests/roster/ -v`
- **Per wave merge:** `uv run --extra dev pytest -v` (full backend suite, including `tests/missions/`
  to catch any regression from the new `roster → missions` cross-module call)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/roster/__init__.py` — new test package (mirrors `tests/missions/`)
- [ ] `backend/tests/roster/conftest.py` — `db`/`cache` fixtures, mirroring
      `backend/tests/missions/conftest.py:11-27` (read this session) exactly — same `tmp_path`-backed
      `Database` fixture pattern, same `seed_telemetry()` helper shape
- [ ] `backend/tests/roster/test_models.py` — mirrors `tests/missions/test_models.py`
- [ ] `backend/tests/roster/test_repository.py` — mirrors `tests/missions/test_repository.py`
- [ ] `backend/tests/roster/test_service.py` — new; no missions equivalent to copy verbatim since
      this is where the D-03 cross-module recall logic and D-04 telemetry-failure-swallowing logic
      live — will need a fake/mock `TelemetrySource` (e.g., a simple stub class implementing the
      4-method `TelemetrySource` ABC, or `unittest.mock.AsyncMock` against the interface) to test
      the "source raises, service logs and continues" path deterministically
- [ ] `backend/tests/roster/test_router.py` — mirrors `tests/missions/test_router.py:13-16`'s
      `_client(db, cache, ...)` helper pattern, using `create_roster_router` in place of
      `create_missions_router`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Explicitly out of scope project-wide (single-operator demo, `.planning/REQUIREMENTS.md` "Out of Scope" table, read this session: "Authentication / multi-tenant support — Single-operator demo app") |
| V3 Session Management | No | Same as above |
| V4 Access Control | No | Same as above — no per-operator authorization boundary to enforce beyond the existing `operator_id = 'default'` hardcode already used throughout `missions/repository.py` |
| V5 Input Validation | Yes | Pydantic `AddDroneRequest` with `Field(min_length=1)` — already present in the ported branch code (`git show 2ba52a8:backend/app/roster/router.py`, read this session: `drone_id: str = Field(min_length=1)`), matches D-05's decision to accept any non-empty string |
| V6 Cryptography | No | No secrets, tokens, or cryptographic material handled by this module |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via `drone_id` | Tampering | Already mitigated — every query in both the ported `repository.py` and the current `missions/repository.py` uses parameterized `?` placeholders exclusively (verified by reading both files this session; no string-formatted SQL anywhere) |
| Resource exhaustion via unbounded roster growth (no drone-count limit on `POST /api/roster`) | Denial of Service | Not currently mitigated anywhere in the codebase (no `MAX_FLEET_SIZE` constant found in `missions/models.py` or elsewhere); low severity for a single-operator local demo app — flag as a known gap, not a blocker, consistent with `security_block_on: "high"` in `.planning/config.json` |

## Sources

### Primary (HIGH confidence — all read directly this session)
- `backend/app/missions/{models,service,repository,router,__init__}.py` — full read, current state
- `backend/app/db/{schema,connection,seed}.py` — full read, current state
- `backend/app/telemetry/{interface,cache,models,factory,simulator,mavlink_gateway,__init__}.py` — full read, current state
- `backend/app/main.py` — full read, current state
- `backend/tests/{conftest,missions/conftest,missions/test_router}.py` — full read, current state
- `backend/pyproject.toml` — full read, current state
- `git show 2ba52a8:backend/app/roster/{models,repository,router,__init__}.py` — full read of the unmerged branch commit
- `.planning/phases/01-roster-module/01-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/config.json` — full read

### Secondary (MEDIUM confidence)
None — all findings in this research were sourced from direct file reads of the target repository;
no external documentation lookups were needed since this phase is pure internal architecture
pattern-matching with zero new third-party libraries.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — no new dependencies; every primitive used is already proven working in `missions/router.py`
- Architecture: HIGH — every pattern cited was read directly from current repository files this session, not inferred from training data
- Pitfalls: HIGH — the `main.py` timing gap (Pitfall 3) was discovered by directly tracing `lifespan()`'s local-variable scoping against module-level router mounting, not assumed

**Research date:** 2026-08-12
**Valid until:** No expiry — internal codebase research tied to this exact commit state; re-verify only if `backend/app/missions/`, `backend/app/db/`, `backend/app/telemetry/`, or `backend/app/main.py` change before this phase is planned/executed
