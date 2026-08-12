# Phase 1: Roster Module - Pattern Map

**Mapped:** 2026-08-12
**Files analyzed:** 11 (5 source, 5 test, 1 modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/app/roster/models.py` | model | CRUD | `backend/app/missions/models.py` (role) + `git show 2ba52a8:backend/app/roster/models.py` (exact, port as-is) | exact (port) |
| `backend/app/roster/repository.py` | service (data access) | CRUD | `backend/app/missions/repository.py` (role) + `git show 2ba52a8:backend/app/roster/repository.py` (exact, port as-is) | exact (port) |
| `backend/app/roster/service.py` | service | CRUD + cross-module orchestration | `backend/app/missions/service.py` | role-match (new file, no ported equivalent) |
| `backend/app/roster/router.py` | router/controller | request-response | `backend/app/missions/router.py` (layering) + `git show 2ba52a8:backend/app/roster/router.py` (starting shape, needs rewrite) | role-match |
| `backend/app/roster/__init__.py` | config (module exports) | n/a | `backend/app/missions/__init__.py` | exact |
| `backend/app/main.py` (modified) | config/wiring | request-response | itself (existing file, targeted edit) | exact |
| `backend/tests/roster/conftest.py` | test | fixture | `backend/tests/missions/conftest.py` | exact |
| `backend/tests/roster/test_models.py` | test | CRUD | `backend/tests/missions/test_models.py` | exact |
| `backend/tests/roster/test_repository.py` | test | CRUD | `backend/tests/missions/test_repository.py` | exact |
| `backend/tests/roster/test_service.py` | test | CRUD + mocking | `backend/tests/missions/test_service.py` | role-match (new cross-module mocking not present in missions tests) |
| `backend/tests/roster/test_router.py` | test | request-response | `backend/tests/missions/test_router.py` | exact |

## Pattern Assignments

### `backend/app/roster/models.py` (model, CRUD)

**Analog:** `git show 2ba52a8:backend/app/roster/models.py` — port unchanged.

```python
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

**Style cross-check** against `backend/app/missions/models.py:44-91` (exception hierarchy convention this must match):
```python
class MissionError(Exception):
    ...
class UnknownDroneError(MissionError):
    reason = "unknown_drone"
```
Confirms the ported branch's `RosterError` hierarchy already matches this exact base-class + `reason` attribute shape. No changes needed.

---

### `backend/app/roster/repository.py` (data access, CRUD)

**Analog:** `git show 2ba52a8:backend/app/roster/repository.py` — port unchanged (verified against current schema/connection API, no drift found).

```python
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

Also port `list_roster_entries(db)` from the same branch file (reads `fleet_roster`, returns `list[RosterEntry]`) — used directly by `router.list_drones()` per the "reads skip service" convention below.

**Cross-module dependency needed for D-03:** `backend/app/missions/repository.py:72` already has `get_active_mission_for_drone(db, drone_id)` — call this from `roster/service.py`, do not duplicate the query.

---

### `backend/app/roster/service.py` (NEW — service, CRUD + orchestration)

**Analog:** `backend/app/missions/service.py` (full file, 111 lines) — mirror shape: thin async functions, explicit `db`/`cache` params, domain exceptions propagate uncaught for the router to translate.

**Core pattern to mirror** (`backend/app/missions/service.py:49-51`):
```python
async def recall_mission(db: Database, drone_id: str) -> Mission:
    """Recall the drone's active mission. Raises NoActiveMissionError if none."""
    return await repository.recall(db, drone_id)
```

**New `add_drone`** — thin delegate + telemetry sync (D-04: log-and-continue, sync happens *after* DB commit, in its own try/except):
```python
import logging

from app.db import Database
from app.telemetry import TelemetryCache, TelemetrySource
from app.missions.repository import get_active_mission_for_drone
from app.missions.service import recall_mission

from . import repository
from .models import RosterEntry

logger = logging.getLogger(__name__)


async def add_drone(
    db: Database, source: TelemetrySource | None, drone_id: str
) -> RosterEntry:
    entry = await repository.add_drone(db, drone_id)
    if source is not None:
        try:
            await source.add_drone(drone_id)
        except Exception:
            logger.exception("telemetry sync failed for add_drone(%s)", drone_id)
    return entry


async def remove_drone(
    db: Database, source: TelemetrySource | None, drone_id: str
) -> None:
    if await get_active_mission_for_drone(db, drone_id) is not None:
        await recall_mission(db, drone_id)  # D-03 auto-recall
    await repository.remove_drone(db, drone_id)
    if source is not None:
        try:
            await source.remove_drone(drone_id)
        except Exception:
            logger.exception("telemetry sync failed for remove_drone(%s)", drone_id)
```

**Import narrowness** (per RESEARCH.md Open Question 2 recommendation): use `from app.missions.repository import get_active_mission_for_drone` and `from app.missions.service import recall_mission` — narrowest possible cross-module surface, not `import app.missions`.

**Ordering** (Pitfall 2): recall-then-remove, check-first (via `get_active_mission_for_drone`) rather than catch `NoActiveMissionError` — keeps the flow readable as "check, then act" and avoids exception-as-control-flow.

---

### `backend/app/roster/router.py` (router, request-response)

**Starting point:** `git show 2ba52a8:backend/app/roster/router.py` (80 lines, full content already retrieved) — rewrite direct `repository.add_drone`/`repository.remove_drone` calls to `service.add_drone`/`service.remove_drone`. Keep `list_drones` calling `repository.list_roster_entries` directly (matches `missions/router.py:53-63`'s `get_fleet_status` reading straight from `repository`, no service indirection for reads).

**Factory-function signature to adopt** (`backend/app/missions/router.py:49-51` shape):
```python
def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:
    """Create the mission-dispatch router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/fleet", tags=["missions"])
```
Roster equivalent: `create_roster_router(db: Database, cache: TelemetryCache, source: TelemetrySource | None = None) -> APIRouter`.

**Import shape to mirror** (`backend/app/missions/router.py:11`):
```python
from . import repository, service
```

**Error translation pattern** (`backend/app/missions/router.py:15-22, 31-37`):
```python
_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_en_route": 409,
    ...
}

def _error_response(exc: MissionError) -> HTTPException:
    status_code = _ERROR_STATUS.get(exc.reason, 400)
    detail: dict = {"reason": exc.reason}
    return HTTPException(status_code=status_code, detail=detail)
```
Roster's existing table (unchanged, still correct): `{"unknown_drone": 404, "drone_already_tracked": 409}`. No new reason needed — per Open Question 1's resolution, `remove_drone` checks eligibility before calling `recall_mission`, so `NoActiveMissionError` is never raised in the roster removal path.

**Response merge helper** (port as-is from branch, `_TELEMETRY_FIELDS = ("battery_pct", "altitude_m", "speed_kmh", "status")` and `_entry_response`):
```python
def _entry_response(entry: RosterEntry, cache: TelemetryCache) -> dict:
    payload = entry.to_dict()
    reading = cache.get(entry.drone_id)
    if reading:
        telemetry = reading.to_dict()
        payload.update({field: telemetry[field] for field in _TELEMETRY_FIELDS})
    return payload
```

**Route handlers, rewritten to call service for writes:**
```python
@router.post("", status_code=201)
async def add_drone(request: AddDroneRequest):
    try:
        entry = await service.add_drone(db, source, request.drone_id)
    except RosterError as exc:
        raise _error_response(exc) from exc
    return _entry_response(entry, cache)

@router.delete("/{drone_id}", status_code=204)
async def remove_drone(drone_id: str):
    try:
        await service.remove_drone(db, source, drone_id)
    except RosterError as exc:
        raise _error_response(exc) from exc
    return Response(status_code=204)
```

---

### `backend/app/roster/__init__.py` (config, module exports)

**Analog:** `backend/app/missions/__init__.py` (full file, 15 lines):
```python
"""Mission scheduling: launch/recall dispatch, auto-assignment queue, and
background lifecycle tasks."""

from .queue import MissionQueue
from .router import create_missions_router
from .scheduler import run_assignment_scheduler, run_budget_snapshot_loop, run_delivery_scheduler

__all__ = [
    "MissionQueue",
    "create_missions_router",
    "run_assignment_scheduler",
    "run_budget_snapshot_loop",
    "run_delivery_scheduler",
]
```

Roster equivalent (module docstring + exports for router factory and public exception/model types, matching CONTEXT.md's canonical-refs list):
```python
"""Fleet roster CRUD: add/remove/list tracked drones."""

from .models import DroneAlreadyTrackedError, RosterEntry, RosterError, UnknownDroneError
from .router import create_roster_router

__all__ = [
    "DroneAlreadyTrackedError",
    "RosterEntry",
    "RosterError",
    "UnknownDroneError",
    "create_roster_router",
]
```

---

### `backend/app/main.py` (modified — wiring)

**Analog:** itself; targeted edit per RESEARCH.md Pitfall 3.

**Current state** (`backend/app/main.py:14-22, 51-53, 56-62, 80-82` — all read this session):
```python
from app.telemetry import TelemetryCache, create_stream_router, create_telemetry_source
...
telemetry_cache = TelemetryCache()
mission_queue = MissionQueue()
database = Database(_default_db_path())

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.ensure_initialized()
    source = create_telemetry_source(telemetry_cache)
    await source.start(DEFAULT_FLEET)
    app.state.telemetry_source = source
    ...

app = FastAPI(title="SkyFleet Ops", lifespan=lifespan)
app.include_router(create_stream_router(telemetry_cache))
app.include_router(create_missions_router(database, telemetry_cache, mission_queue))
```

**Required change:** move `create_telemetry_source(telemetry_cache)` construction to module level (construction is non-blocking per its own docstring: "Returns an unstarted source. Caller must await source.start(drone_ids)."), keep `await telemetry_source.start(DEFAULT_FLEET)` inside `lifespan`, add `roster` import and router mount at the same module-level block as `missions_router`:

```python
from app.roster import create_roster_router
...
telemetry_cache = TelemetryCache()
mission_queue = MissionQueue()
database = Database(_default_db_path())
telemetry_source = create_telemetry_source(telemetry_cache)

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.ensure_initialized()
    await telemetry_source.start(DEFAULT_FLEET)
    app.state.telemetry_source = telemetry_source
    ...
    await telemetry_source.stop()  # replaces `await source.stop()`

app.include_router(create_missions_router(database, telemetry_cache, mission_queue))
app.include_router(create_roster_router(database, telemetry_cache, telemetry_source))
```

This is the only production-code file modified outside `backend/app/roster/`.

---

### Test files (`backend/tests/roster/*.py`)

**Analog:** `backend/tests/missions/{conftest,test_models,test_repository,test_router,test_service}.py`

**Fixture pattern to mirror exactly** (`backend/tests/missions/conftest.py`, full file):
```python
@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "skyfleet.db")
    database.ensure_initialized()
    yield database
    database.close()


@pytest.fixture
def cache():
    return TelemetryCache()


def seed_telemetry(
    cache: TelemetryCache, drone_id: str, battery_pct: float = 90.0, status: str = "idle"
) -> None:
    cache.update(drone_id, battery_pct=battery_pct, altitude_m=100.0, speed_kmh=40.0, status=status)
```
Copy verbatim into `backend/tests/roster/conftest.py` (same `tmp_path`-backed `Database`, same `TelemetryCache` fixture, same `seed_telemetry` helper — roster tests need this to seed telemetry for `_entry_response` merge tests).

**Router test client pattern** (`backend/tests/missions/test_router.py:1-16`):
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.missions import MissionQueue, create_missions_router

from .conftest import seed_telemetry


def _client(db, cache, queue: MissionQueue | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_missions_router(db, cache, queue if queue is not None else MissionQueue()))
    return TestClient(app)


class TestGetFleetStatus:
    def test_returns_budget_and_empty_missions(self, db, cache):
        client = _client(db, cache)
        response = client.get("/api/fleet")
        assert response.status_code == 200
```
Roster equivalent: `_client(db, cache, source=None)` using `create_roster_router(db, cache, source)`; test classes `TestAddDrone`, `TestListDrones`, `TestRemoveDrone` per the RESEARCH.md test map.

**`test_service.py` — new pattern, no direct missions analog** (missions/service.py never needs to mock an external source; roster's D-04 test requires a fake/mock `TelemetrySource`). Use a minimal stub class implementing the `TelemetrySource` ABC's `add_drone`/`remove_drone`/`start`/`stop` methods, or `unittest.mock.AsyncMock`, to test:
1. Normal add/remove path calls `source.add_drone`/`remove_drone`.
2. `source.add_drone`/`remove_drone` raising is caught and logged, DB write still commits (D-04).
3. Removing a drone with an active mission calls `missions.service.recall_mission` first (D-03) — assert via a real `missions/repository.create_mission` call in the DB fixture, then assert the mission's status is `"recalled"` after `roster.service.remove_drone`.

---

## Shared Patterns

### Layered module structure (models / service / repository / router)
**Source:** `backend/app/missions/` (all 5 files)
**Apply to:** All of `backend/app/roster/{models,service,repository,router,__init__}.py`
- `models.py`: dataclasses + domain exception hierarchy with `reason` class attribute
- `repository.py`: raw SQL via `Database.execute`/`fetchall`/`transaction`, raises domain exceptions
- `service.py`: business rules, orchestrates repository calls (and now, cross-module calls)
- `router.py`: FastAPI `APIRouter` via factory function, Pydantic request models, `_ERROR_STATUS` translation table, calls `service` for writes and `repository` for simple reads

### Domain exception → HTTP status translation
**Source:** `backend/app/missions/router.py:15-22, 31-37`
**Apply to:** `backend/app/roster/router.py`
```python
_ERROR_STATUS = {"unknown_drone": 404, "drone_already_tracked": 409}

def _error_response(exc: RosterError) -> HTTPException:
    status_code = _ERROR_STATUS.get(exc.reason, 400)
    return HTTPException(status_code=status_code, detail={"reason": exc.reason})
```

### Atomic transaction via `db.transaction(fn)`
**Source:** `backend/app/db/connection.py:73-89`
**Apply to:** `backend/app/roster/repository.py::remove_drone` (already uses this in the ported branch code)
```python
async def transaction(self, fn: Callable[[sqlite3.Connection], T]) -> T:
    async with self._lock:
        return await asyncio.to_thread(self._transaction_sync, fn)
```
Note: this is a single lock shared by the whole `Database` instance. `roster.service.remove_drone()`'s sequential calls to `missions.service.recall_mission()` and `roster.repository.remove_drone()` are two separate lock acquisitions, not one spanning transaction — accepted tradeoff per D-03's "reversibility: costly" note (see Pitfall 2 in RESEARCH.md).

### Telemetry sync — log-and-continue, never rolls back DB write (D-04)
**Source:** New pattern for this phase (no existing precedent in `missions/` since missions doesn't call `TelemetrySource` directly); apply per D-04's explicit rule.
**Apply to:** `backend/app/roster/service.py::add_drone` and `remove_drone`
```python
if source is not None:
    try:
        await source.add_drone(drone_id)
    except Exception:
        logger.exception("telemetry sync failed for add_drone(%s)", drone_id)
```
Must sit **after** the DB transaction has already committed, in a separate try/except — never inside the same `db.transaction()` callback.

### Module-level singleton + factory-function router mounting
**Source:** `backend/app/main.py:51-53, 80-82`
**Apply to:** `backend/app/main.py`'s roster wiring (`telemetry_source` promoted to module level, `create_roster_router(database, telemetry_cache, telemetry_source)` mounted next to `create_missions_router`)

## No Analog Found

None — every file in scope has at least a role-match analog in `backend/app/missions/` or an exact-content analog on the `agent_team_work` branch.

## Metadata

**Analog search scope:** `backend/app/missions/`, `backend/app/db/`, `backend/app/telemetry/`, `backend/app/main.py`, `backend/tests/missions/`, `git show 2ba52a8:backend/app/roster/*`
**Files scanned:** 11 current-tree files + 4 branch-commit files (all read in full this session)
**Pattern extraction date:** 2026-08-12
