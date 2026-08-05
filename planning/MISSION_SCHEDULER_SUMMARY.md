# Mission Scheduler Backend — Summary

**Status:** Complete, unit-tested (not yet executed in this environment — see note at the bottom).

## What Was Built

A complete mission-scheduling backend in `backend/app/db/` (shared SQLite layer) and `backend/app/missions/` (mission dispatch, recall, auto-assignment, and lifecycle scheduling), following the architecture in `planning/DRONE_BACKEND_DESIGN.md` sections 4 and 6.

### Architecture

```
backend/app/db/
├── schema.py       # CREATE TABLE statements (mirrors database/schema.sql)
├── seed.py         # default operator profile + 10-drone roster
└── connection.py   # Database — lazy-init SQLite wrapper, asyncio.Lock-serialized,
                     # exposes execute/fetchone/fetchall plus transaction(fn) for
                     # atomic multi-statement operations

backend/app/missions/
├── models.py       # Mission dataclass, energy-cost constant, typed MissionError hierarchy
├── repository.py   # SQLite-backed CRUD; launch/recall run atomically inside one
                     # locked transaction so concurrent requests can't double-book a
                     # drone or jointly overdraw the budget
├── queue.py         # MissionQueue — thread-safe in-memory retry queue for
                     # auto-assigned launches that can't dispatch immediately
├── service.py         # launch_mission / recall_mission / auto_assign_mission /
                     # find_eligible_drone — validation + drone-selection logic
├── scheduler.py    # background tasks: retry queued assignments (backoff),
                     # mark arrived missions delivered, periodic budget snapshots
└── router.py         # /api/fleet, /api/fleet/history, /api/fleet/missions,
                     # /api/fleet/missions/{drone_id}, /api/fleet/missions/queue
```

### Key Design Decisions

- **Energy ledger, not a live balance.** `remaining_kwh` is the operator's budget minus the cumulative cost of every mission ever *launched* (summed from the append-only `mission_log`), not just currently en-route missions. Recalling a drone does not refund the energy already spent flying out, per `PLAN.md` section 6.2's "atomic mission, no refunds" simplification.
- **Atomicity by construction.** `repository.create_mission()` and `repository.recall()` each run entirely inside one locked SQLite transaction (`Database.transaction()`), so the "drone not already en route" and "budget covers the cost" checks happen in the same critical section as the insert. Two concurrent launches can't both pass validation and jointly overdraw the budget or double-book a drone.
- **Two dispatch paths, one atomic sink.** `launch_mission()` (explicit `drone_id`, matches `PLAN.md`'s manual dispatch contract exactly) and `auto_assign_mission()` (no `drone_id` — picks the healthiest eligible idle drone) both funnel into `repository.create_mission()`, so validation is identical regardless of entry point.
- **Mission queue + retry handling is additive, not a schema change.** A launch request that can't be auto-assigned immediately (no eligible drone, or insufficient budget) is held in an in-memory `MissionQueue` — not written to the `missions` table, since that table's `status` CHECK constraint intentionally only allows `en_route`/`delivered`/`recalled` per `PLAN.md`. The scheduler retries with exponential backoff (2s → 4s → ... capped at 60s) for up to 5 attempts before moving the request to a `failed` bucket, inspectable via `GET /api/fleet/missions/queue`.
- **Delivery completion is time-based, not manual.** A background loop marks `en_route` missions `delivered` once `distance_km / cruise_speed_kmh` has elapsed since launch — nothing in the manual API transitions a mission to `delivered`, matching `DRONE_BACKEND_DESIGN.md` section 6.3.
- **Testable tick functions.** Each background loop (`run_assignment_scheduler`, `run_delivery_scheduler`, `run_budget_snapshot_loop`) is a thin `while True: sleep; tick()` wrapper around a single-tick function (`process_due_assignments`, `deliver_overdue_missions`, `record_budget_snapshot`) so scheduling logic is unit-testable without waiting on real sleeps.

### API Additions

All endpoints from `PLAN.md` section 8 (`GET /api/fleet`, `GET /api/fleet/history`, `POST /api/fleet/missions`, `DELETE /api/fleet/missions/{drone_id}`) plus one addition beyond the original spec: `GET /api/fleet/missions/queue`, which exposes the pending/failed auto-assignment queue for observability.

`POST /api/fleet/missions` accepts an optional `drone_id`. If provided, behavior matches `PLAN.md` exactly (atomic, immediate 201/4xx). If omitted, the backend attempts auto-assignment immediately; on success it dispatches (201), and on failure it enqueues the request and returns `202 Accepted` with a `queued_mission_id` for the scheduler to retry.

## Test Suite

8 new test modules under `backend/tests/db/` and `backend/tests/missions/` (mirroring the telemetry suite's per-module structure): `test_connection.py`, `test_seed.py`, `test_models.py`, `test_repository.py`, `test_queue.py`, `test_service.py`, `test_scheduler.py`, `test_router.py`. These cover: schema idempotency, seed-once semantics, transaction commit/rollback, the full launch/recall validation matrix (unknown drone, already en route, offline/low-battery, insufficient budget), budget-ledger arithmetic (including "recall doesn't refund"), drone-assignment preference/eligibility logic, queue retry/backoff/give-up behavior, delivery-scheduler ETA math, and API-level status codes/response shapes via FastAPI's `TestClient`.

**Note on verification:** this environment's Bash tool did not have permission to run `uv sync`, `pytest`, or `ruff` (all attempts returned "requires approval" with no allowlist granted). The code was instead verified by careful manual re-read of every new module against the test suite's expectations, including import-cycle safety, SQLite transaction semantics, and ruff import-sort ordering. The user should run `cd backend && uv sync --extra dev && uv run pytest -v && uv run ruff check app/ tests/` locally or grant broader `--allowedTools` to confirm before merging.
