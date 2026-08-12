---
phase: 01-roster-module
plan: 01
subsystem: api
tags: [fastapi, sqlite, roster, telemetry]

# Dependency graph
requires:
  - phase: telemetry
    provides: TelemetryCache / TelemetrySource interface consumed by roster GET and POST
  - phase: missions
    provides: layered router/service/repository pattern and _ERROR_STATUS convention mirrored here
provides:
  - "backend/app/roster/ package: models, repository, service, router, __init__"
  - "GET /api/roster and POST /api/roster mounted on the real FastAPI app"
  - "telemetry_source module-level singleton in backend/app/main.py, shared by roster and lifespan"
affects: [01-roster-module plan 02, 01-roster-module plan 03, chat phase (roster_changes action delegates to roster.service)]

# Actuals (#2632)
actuals:
  tokens: 4128
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "roster/ package mirrors missions/ layering: router -> service -> repository -> Database"
    - "Module-level singleton construction (telemetry_source) before app.include_router, avoiding lifespan-local shadowing (RESEARCH Pitfall 3)"
    - "D-04 telemetry-sync-failure pattern: persist first, then best-effort external sync in a try/except that only logs"

key-files:
  created:
    - backend/app/roster/models.py
    - backend/app/roster/repository.py
    - backend/app/roster/service.py
    - backend/app/roster/router.py
    - backend/app/roster/__init__.py
    - backend/tests/roster/__init__.py
    - backend/tests/roster/conftest.py
    - backend/tests/roster/test_router.py
    - backend/tests/roster/test_service.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Ported models.py/repository.py/__init__.py unchanged from branch 2ba52a8 per D-01; router.py adapted from that branch to drop the DELETE handler (arrives in plan 02) and delegate POST to the new service layer per D-02"
  - "service.add_drone persists via repository first, then registers telemetry in a try/except that only logs on failure (D-04) — the fleet_roster row is never rolled back"
  - "telemetry_source promoted to a fourth module-level singleton in main.py, constructed before lifespan runs, so create_roster_router can receive the same instance lifespan starts/stops"

patterns-established:
  - "roster/service.py: thin async functions taking explicit dependencies (db, source), mirroring missions/service.py's shape — no globals"

requirements-completed: [ROST-01, ROST-03, ROST-04]

coverage:
  - id: D1
    description: "POST /api/roster with {\"drone_id\": \"FALCON-11\"} returns 201 with the created entry and registers the drone with the TelemetrySource"
    requirement: "ROST-01"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDrone::test_adds_drone_and_lists_it"
        status: pass
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDrone::test_registers_with_telemetry_source"
        status: pass
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDrone::test_duplicate_returns_409"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /api/roster returns every tracked drone merged with its latest TelemetryCache reading"
    requirement: "ROST-03"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestListRoster::test_returns_seeded_fleet_in_drone_id_order"
        status: pass
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestListRoster::test_merges_latest_telemetry"
        status: pass
    human_judgment: false
  - id: D3
    description: "backend/app/roster/ is organized as models/service/repository/router/__init__, with the write path running router -> service -> repository, and is mounted on the real app.main:app"
    requirement: "ROST-04"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_router.py::TestAppWiring::test_roster_route_mounted_and_telemetry_source_is_singleton"
        status: pass
      - kind: unit
        ref: "backend backend/uv-venv command: python -c \"import app.main; print(sorted(app.main.app.openapi()['paths'].keys()))\" includes /api/roster"
        status: pass
    human_judgment: false
  - id: D4
    description: "A TelemetrySource.add_drone() failure during POST /api/roster is logged with the drone_id and the fleet_roster row stays committed (D-04)"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestTelemetrySyncFailure::test_row_survives_a_raising_source"
        status: pass
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestTelemetrySyncFailure::test_failure_is_logged_with_drone_id"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-08-12
status: complete
---

# Phase 1 Plan 1: Roster Tracer Slice Summary

**End-to-end `POST/GET /api/roster` wired through a new `roster/` service layer into `fleet_roster` and the shared `TelemetryCache`/`TelemetrySource`, mounted on the real FastAPI app with telemetry-sync failures degrading to a logged no-op instead of a rollback.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-12T14:29:30Z
- **Completed:** 2026-08-12T14:41:52Z
- **Tasks:** 2
- **Files modified:** 10 (9 created, 1 modified)

## Accomplishments
- New `backend/app/roster/` package (models, repository, service, router, `__init__`) mirroring the `missions/` layered pattern
- `POST /api/roster` persists to `fleet_roster` and registers the drone with the live `TelemetrySource`; `GET /api/roster` merges each entry with its latest `TelemetryCache` reading
- `backend/app/main.py` promotes `telemetry_source` to a module-level singleton constructed before `lifespan`, fixing the construction-timing pitfall the RESEARCH doc flagged, and mounts `create_roster_router`
- `service.add_drone` survives a raising `TelemetrySource`: the DB write is never rolled back, and the failure is logged at ERROR with the drone_id (D-04)

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "add a drone and see it in the roster" — one path only** - `0542dc3` (feat)
2. **Task 2: Telemetry registration survives a failing TelemetrySource (D-04)** - `fa00792` (feat)

_Note: no separate plan-metadata commit — this is a parallel worktree plan; the orchestrator commits shared docs after the wave merges._

## Files Created/Modified
- `backend/app/roster/models.py` - `RosterEntry` dataclass, `RosterError` hierarchy (`DroneAlreadyTrackedError`, `UnknownDroneError`); ported unchanged from branch `2ba52a8`
- `backend/app/roster/repository.py` - Parameterized SQL against `fleet_roster`: `list_roster`, `list_roster_entries`, `add_drone`, `remove_drone`; ported unchanged from branch `2ba52a8`
- `backend/app/roster/service.py` - New service layer (ROST-04, D-02): `add_drone` persists then best-effort registers telemetry, logging failures per D-04
- `backend/app/roster/router.py` - `create_roster_router(db, cache, source)`; `GET`/`POST` handlers only (DELETE deferred to plan 02)
- `backend/app/roster/__init__.py` - Public exports mirroring `missions/__init__.py`
- `backend/app/main.py` - `telemetry_source` promoted to a module-level singleton; `create_roster_router` mounted
- `backend/tests/roster/__init__.py` - Empty, mirrors `tests/missions/__init__.py`
- `backend/tests/roster/conftest.py` - `db`/`cache` fixtures, `seed_telemetry()`, and shared `FakeSource`/`RaisingSource` telemetry test doubles
- `backend/tests/roster/test_router.py` - End-to-end coverage: `TestListRoster`, `TestAddDrone`, `TestAppWiring`
- `backend/tests/roster/test_service.py` - Service-layer coverage: `TestAddDrone`, `TestTelemetrySyncFailure`

## Decisions Made
- Ported `models.py`, `repository.py`, and `__init__.py` unchanged from branch `2ba52a8` (D-01) — verified against the current schema with no drift
- `router.py` dropped the branch's `DELETE` handler and inline `source.add_drone` call; POST now delegates to `service.add_drone` (D-02 layering)
- `service.add_drone` wraps the telemetry call in `try/except Exception` strictly after `repository.add_drone` commits, per D-04 — the database stays the roster's source of truth
- `FakeSource`/`RaisingSource` test doubles were moved into `tests/roster/conftest.py` (task 2) so router and service tests share one definition instead of duplicating per module

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `TestAppWiring` adapted to the installed FastAPI/Starlette route API**
- **Found during:** Task 1 (App wiring test)
- **Issue:** The plan's literal verification snippet (`{r.path for r in app.main.app.routes}`) and the initial test both assumed `app.routes` yields flat `Route`/`APIRoute` objects with a `.path` attribute. The actually-installed `fastapi==0.141.1` (pinned in `backend/uv.lock`, matching `>=0.115.0`) wraps `include_router()`-mounted routers in an internal `fastapi.routing._IncludedRouter` object that has no `.path` attribute at the top level, so both the raw snippet and the naive test raised `AttributeError`.
- **Fix:** Rewrote `TestAppWiring` to enumerate mounted paths via `app.main.app.openapi()["paths"]`, a stable, version-independent way to confirm `/api/roster` is mounted. Verified manually that the plan's literal `python -c` snippet does fail in this environment and that the openapi-based check gives the same assurance (proves the roster router is registered) without depending on FastAPI's internal routing-object shape.
- **Files modified:** `backend/tests/roster/test_router.py`
- **Verification:** `TestAppWiring::test_roster_route_mounted_and_telemetry_source_is_singleton` passes; full suite (176 tests) green; ruff clean
- **Committed in:** `0542dc3` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — environment/dependency-version mismatch)
**Impact on plan:** No scope creep. The plan's literal acceptance-criteria snippet (`import app.main; print(sorted({r.path for r in app.main.app.routes}))`) will also raise `AttributeError` if run verbatim against this environment's pinned FastAPI version — anyone re-verifying by hand should use `app.main.app.openapi()["paths"]` instead. The intent (confirm `/api/roster` is mounted on the real app) is fully proven either way.

## Issues Encountered
- The sandboxed execution environment's default `uv` cache directory (`~/.cache/uv`) is read-only, and `uv run` under a fresh `UV_CACHE_DIR` attempted to resolve Python 3.13 and re-download wheels from `pypi.org`, which the sandbox's network allowlist blocks. Worked around by invoking the pre-built `backend/.venv` (Python 3.12, already synced with the project's locked dependencies) directly via its `python`/`ruff` binaries from within the worktree's `backend/` directory — `sys.path`'s leading empty entry ensures `import app` resolves to the worktree's own `app/` package, not any editable install elsewhere. No source files were affected; this is a local test-invocation detail only.

## Next Phase Readiness
- The tracer slice proves router → service → repository → SQLite → TelemetryCache/TelemetrySource → app mount end-to-end; plan 02 can build the `DELETE /api/roster/{drone_id}` auto-recall flow (D-03) directly on top of this `service.py` and `repository.py` without further plumbing changes
- `FakeSource`/`RaisingSource` in `tests/roster/conftest.py` are ready for plan 02/03 to reuse for recall-path telemetry-failure coverage
- No blockers

---
*Phase: 01-roster-module*
*Completed: 2026-08-12*
