---
phase: 01-roster-module
reviewed: 2026-08-12T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - backend/app/main.py
  - backend/app/roster/__init__.py
  - backend/app/roster/models.py
  - backend/app/roster/repository.py
  - backend/app/roster/router.py
  - backend/app/roster/service.py
  - backend/tests/roster/conftest.py
  - backend/tests/roster/__init__.py
  - backend/tests/roster/test_models.py
  - backend/tests/roster/test_repository.py
  - backend/tests/roster/test_router.py
  - backend/tests/roster/test_service.py
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-08-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the fleet roster module (models, repository, service, router) plus its wiring in `app/main.py` and the accompanying pytest suite. Overall the module follows the project's layering conventions well (router → service → repository → db), uses parameterized SQL throughout, and has solid, deliberate test coverage for its documented "accepted tradeoff" crash windows (D-03/D-04).

The most serious problem is a genuine, reachable TOCTOU race in `roster/service.remove_drone`: it checks for an active mission and then recalls it as two separate steps, but the exception raised if the mission resolves in between (`app.missions.models.NoActiveMissionError`) is not a `RosterError` and is not caught anywhere in the roster router, so it surfaces as an unhandled 500. This isn't a purely theoretical race — the app runs a delivery scheduler every 5 seconds that can mark an en-route mission `delivered` at any time, including inside this exact window. Beyond that, there are several quality issues: an overly broad exception translation in the repository, a startup wiring bug in `main.py` where the telemetry source is always seeded from a hardcoded default fleet instead of the persisted roster, unvalidated/unnormalized `drone_id` input, and a module-boundary violation where the roster service reaches into `app.missions.repository` (a non-exported submodule) instead of going through that module's public API.

## Critical Issues

### CR-01: Unhandled `NoActiveMissionError` can leak out of `DELETE /api/roster/{drone_id}` as a 500

**File:** `backend/app/roster/service.py:59-60`
**Issue:**
`remove_drone` uses a check-then-act pattern to auto-recall an active mission before deleting the roster row:

```python
if await get_active_mission_for_drone(db, drone_id) is not None:
    await recall_mission(db, drone_id)
```

`get_active_mission_for_drone` and `recall_mission` are two separate `Database.transaction()` acquisitions (by design, per the module docstring — see `service.py:53-57`). Between the check and the recall, the mission can stop being `en_route`:

- `app.missions.scheduler.run_delivery_scheduler` (`backend/app/missions/scheduler.py:65-70`) runs every 5 seconds in production (started from `backend/app/main.py:67`) and calls `deliver_overdue_missions`, which flips overdue `en_route` missions to `delivered`.
- A concurrent `DELETE /api/fleet/missions/{drone_id}` (manual recall) could do the same.

If either happens between the check and the `recall_mission` call, `repository.recall()` (`backend/app/missions/repository.py:165-190`) finds no `en_route` row and raises `NoActiveMissionError` (`backend/app/missions/models.py:74-79`). This class inherits from `app.missions.models.MissionError`, **not** `app.roster.models.RosterError`. The roster router only catches `RosterError` (`backend/app/roster/router.py:61-64`):

```python
try:
    await service.remove_drone(db, source, drone_id)
except RosterError as exc:
    raise _error_response(exc) from exc
```

so `NoActiveMissionError` propagates unhandled, and FastAPI returns a generic 500 instead of the roster module's documented error contract. The mission itself ends up in a correct state (delivered), but the roster-removal request the operator issued fails opaquely, with the roster row left in place (the operator has to retry).

This is not covered by any test in `backend/tests/roster/test_service.py` — the existing `TestRemoveIdempotency` tests only cover the recall-then-crash and re-delete scenarios, not a mission resolving out from under the check between steps 1 and 2.

**Fix:** Treat "the mission is no longer active" as success for the purposes of roster removal — the goal (no en-route mission for a drone being removed) is already satisfied:

```python
from app.missions.models import NoActiveMissionError

async def remove_drone(db: Database, source: TelemetrySource | None, drone_id: str) -> None:
    if await get_active_mission_for_drone(db, drone_id) is not None:
        try:
            await recall_mission(db, drone_id)
        except NoActiveMissionError:
            pass  # resolved (delivered/recalled) between the check and the recall
    ...
```

## Warnings

### WR-01: `repository.add_drone` masks any `sqlite3.IntegrityError` as "already tracked"

**File:** `backend/app/roster/repository.py:50-56`
**Issue:**
```python
try:
    await db.execute(
        "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
        (entry.id, entry.operator_id, entry.drone_id, entry.added_at),
    )
except sqlite3.IntegrityError as exc:
    raise DroneAlreadyTrackedError(drone_id) from exc
```
The `fleet_roster` table has two constraints that can raise `IntegrityError`: the `UNIQUE (operator_id, drone_id)` constraint (the intended case) and the `PRIMARY KEY` on `id` (a UUID4 collision, effectively impossible but not impossible-in-principle). Any future schema change adding a `NOT NULL`/`CHECK` constraint on `fleet_roster` would also be silently mapped to "drone already tracked", which is a misleading error for the caller and makes debugging future constraint violations harder.

**Fix:** Narrow the catch to the specific SQLite error class/message, or re-check the cause before mapping:
```python
except sqlite3.IntegrityError as exc:
    if "UNIQUE" in str(exc):
        raise DroneAlreadyTrackedError(drone_id) from exc
    raise
```

### WR-02: `main.py` seeds the telemetry source from a hardcoded fleet, not the persisted roster

**File:** `backend/app/main.py:28, 62`
**Issue:**
```python
DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]
...
await telemetry_source.start(DEFAULT_FLEET)
```
On every process start, the telemetry source is initialized with the fixed 10-drone default list, regardless of what's actually in `fleet_roster`. Since `telemetry_source` is a fresh in-process object each restart (per the architecture notes: telemetry is ephemeral, in-memory), this means:
- A drone added via `POST /api/roster` before a restart no longer has telemetry started for it after the restart, and there is no way to re-register it through the API afterward — `POST /api/roster` with that `drone_id` will now fail with 409 `drone_already_tracked` (the DB row is still there), so the operator can't simply "re-add" it. The only recovery is `DELETE` then `POST` again.
- A drone removed via `DELETE /api/roster/{drone_id}` before a restart will still be tracked by the new telemetry source instance (since `DEFAULT_FLEET` includes it unconditionally), producing telemetry for a drone that no longer appears anywhere in the roster/UI — silently wasted background work, though not user-visible.

This undermines the roster module's core promise that roster changes persist. It's outside the roster module's own files but is exercised directly by `create_roster_router(database, telemetry_cache, telemetry_source)` at `main.py:84`, so the two are coupled at the point of wiring.

**Fix:** Seed the telemetry source from the persisted roster at startup instead of (or in addition to) the default fleet:
```python
async def lifespan(app: FastAPI):
    database.ensure_initialized()
    roster_drone_ids = await roster_repository.list_roster(database)
    await telemetry_source.start(roster_drone_ids or DEFAULT_FLEET)
```

### WR-03: `AddDroneRequest.drone_id` isn't normalized — whitespace-only/padded IDs are accepted

**File:** `backend/app/roster/router.py:22-23`
**Issue:**
```python
class AddDroneRequest(BaseModel):
    drone_id: str = Field(min_length=1)
```
`min_length=1` only rejects the empty string. A payload like `{"drone_id": " "}` or `{"drone_id": "FALCON-01 "}` (trailing space) passes validation and is persisted verbatim. The latter would create a roster entry that looks identical to `FALCON-01` in any UI rendering but is a distinct DB row with no telemetry (since the telemetry cache is keyed by the exact `drone_id` string), producing a confusing "duplicate-looking" roster entry that's awkward to address via `DELETE /api/roster/{drone_id}` (the caller must reproduce the exact whitespace).

**Fix:** Strip and re-validate in the model:
```python
class AddDroneRequest(BaseModel):
    drone_id: str = Field(min_length=1)

    @field_validator("drone_id")
    @classmethod
    def _strip_and_check(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("drone_id must not be blank")
        return v
```

### WR-04: Roster service reaches into `app.missions.repository` directly, bypassing the missions package's public API

**File:** `backend/app/roster/service.py:8`
**Issue:**
```python
from app.missions.repository import get_active_mission_for_drone
from app.missions.service import recall_mission
```
`app.missions/__init__.py` exports `MissionQueue`, `create_missions_router`, and the three `run_*` scheduler functions — `get_active_mission_for_drone` is not part of that public surface (`backend/app/missions/__init__.py:8-14`). The roster service correctly goes through the missions *service* layer for the write path (`recall_mission`), but for the read/check it drops down to the missions *repository* layer directly, coupling roster to an internal implementation detail of another domain module and inconsistently mixing layer depths within the same function. Per this project's documented module design conventions ("Only export public API; private helpers stay in their module"), this is a boundary violation that will make future refactors of `app.missions.repository` more likely to silently break `app.roster.service`.

**Fix:** Either export a service-level helper from `app.missions` (e.g. `has_active_mission(db, drone_id)`) for roster to call, or accept the check inside `recall_mission`'s own transaction so roster doesn't need to pre-check at all.

## Info

### IN-01: No test exercises the check-then-recall race in `remove_drone`

**File:** `backend/tests/roster/test_service.py`
**Issue:** `TestRemoveDroneWithActiveMission` and `TestRemoveIdempotency` cover "no active mission," "active mission gets recalled," and "recall-then-crash-then-retry," but nothing simulates a mission resolving (delivered or recalled by another caller) between the `get_active_mission_for_drone` check and the `recall_mission` call in `service.py:59-60` — the scenario in CR-01. Once CR-01 is fixed, a regression test should monkeypatch/interleave a `recall_mission`/`mark_delivered` call between the check and the recall to prove the 500 no longer occurs.
**Fix:** Add a test that pre-empts the mission (e.g., call `repository.mark_delivered` or `recall_mission` directly right after the active-mission check would run, via monkeypatching `get_active_mission_for_drone` to return a mission that's already been resolved by the time `recall_mission` executes).

### IN-02: Redundant explicit 204 response alongside route decorator's `status_code=204`

**File:** `backend/app/roster/router.py:59-65`
**Issue:**
```python
@router.delete("/{drone_id}", status_code=204)
async def remove_drone(drone_id: str):
    try:
        await service.remove_drone(db, source, drone_id)
    except RosterError as exc:
        raise _error_response(exc) from exc
    return Response(status_code=204)
```
The decorator already sets `status_code=204`; returning an explicit `Response(status_code=204)` is redundant (harmless, but adds noise — a bare `return` or `return Response(status_code=204)` without the decorator argument would be equally correct and less duplicative).
**Fix:** Drop one of the two — e.g. `return Response(status_code=204)` and remove `status_code=204` from the decorator, or vice versa, to keep a single source of truth for the status code.

---

_Reviewed: 2026-08-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
