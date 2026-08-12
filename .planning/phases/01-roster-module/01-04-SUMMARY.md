---
phase: 01-roster-module
plan: 04
subsystem: api
tags: [fastapi, sqlite, roster, missions, concurrency, gap-closure]

# Dependency graph
requires:
  - phase: 01-roster-module plan 02
    provides: "roster.service.remove_drone with D-03 auto-recall (check-first, then recall, then delete)"
provides:
  - "roster.service.remove_drone with the mid-window (check->recall) race guarded: NoActiveMissionError caught narrowly, logged, and treated as recall-complete"
  - "Regression coverage for both winning writers of the race (delivery scheduler, concurrent manual recall) at both the HTTP and service layers"
affects: [chat phase (roster_changes 'remove' action delegates to roster.service.remove_drone and now inherits the fixed race behavior)]

# Actuals (#2632)
actuals:
  tokens: 2650
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Narrow exception guard around a single call inside a check-first flow (except NoActiveMissionError around recall_mission only) rather than widening the router's error vocabulary or catching MissionError/Exception broadly"
    - "Interleaving-wrapper test pattern: monkeypatch a real check function with a wrapper that awaits the real check, then performs a caller-supplied resolution coroutine on the result before returning it — reproduces a concurrent writer winning a check->act race deterministically without real threads/timing"
    - "HTTP-level race test mounts two routers (roster + missions) on one FastAPI app so a real mission can be launched over the TestClient's own event loop before the race is triggered"

key-files:
  created: []
  modified:
    - backend/app/roster/service.py
    - backend/tests/roster/test_router.py
    - backend/tests/roster/test_service.py

key-decisions:
  - "Caught exactly NoActiveMissionError, not the MissionError base class and not bare Exception — a different mission-layer failure (e.g. DroneUnavailableError) must still abort the removal and leave the roster row in place, proven by TestRemoveDroneCatchNarrowness"
  - "The guard skips the recall entirely on the raced path — no missions/mission_log/budget_snapshots write happens there, since repository.recall() raises before its first statement — so the audit trail (terminal status, recall-row count, remaining_kwh) is provably untouched by the removal itself"
  - "The interleaving wrapper is reused (as _racing_check in test_service.py, and a bespoke async wrapper in test_router.py) rather than sleeping/threading — deterministic, no flakiness risk"

requirements-completed: [ROST-02]

coverage:
  - id: G1
    description: "DELETE /api/roster/{drone_id} returns 204 (not 500) when the delivery scheduler resolves the drone's mission to 'delivered' between remove_drone's check and its recall call"
    requirement: "ROST-02"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestRemoveDroneMidWindowRace::test_scheduler_delivers_mission_inside_check_recall_window_returns_204"
        status: pass
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestRemoveDroneMidWindowRace::test_scheduler_delivery_variant_preserves_terminal_status_and_no_recall_log"
        status: pass
    human_judgment: false
  - id: G2
    description: "A concurrent manual recall winning the same race still yields a clean removal: mission reads 'recalled', exactly one mission_log recall row exists, and remaining_kwh is unchanged from what the resolving recall alone produced"
    requirement: "ROST-02"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestRemoveDroneMidWindowRace::test_concurrent_manual_recall_variant_preserves_single_recall_log_and_budget"
        status: pass
    human_judgment: false
  - id: G3
    description: "The catch is narrow: a different MissionError subclass from recall_mission still propagates out of remove_drone and the fleet_roster row stays in place"
    requirement: "ROST-02"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestRemoveDroneCatchNarrowness::test_different_mission_error_propagates_and_leaves_roster_row"
        status: pass
    human_judgment: false
  - id: G4
    description: "The skipped recall is diagnosable: an INFO log record naming the drone_id is emitted"
    requirement: "ROST-02"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestRemoveDroneCatchNarrowness::test_skipped_recall_logs_drone_id"
        status: pass
    human_judgment: false
  - id: G5
    description: "A second removal after a raced removal still raises UnknownDroneError with an unchanged roster and mission_log — the mid-window race case needs no operator retry"
    requirement: "ROST-02"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_service.py::TestRemoveDroneMidWindowRace::test_idempotent_after_race_second_removal_raises_unknown_drone"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-12
status: complete
---

# Phase 1 Plan 4: Close ROST-02 Check-Recall Race (ROST-02-TOCTOU) Summary

**`DELETE /api/roster/{drone_id}` now returns 204 (never an unhandled 500) when the drone's en_route mission resolves to a terminal state — via the delivery scheduler or a concurrent manual recall — inside the window between `remove_drone`'s active-mission check and its `recall_mission` call, closing the one blocking gap from Phase 1's verification/review/security passes.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 3 (`backend/app/roster/service.py`, `backend/tests/roster/test_router.py`, `backend/tests/roster/test_service.py`)

## Accomplishments

- **Fail-first proof of the bug.** Task 1 wrote `TestRemoveDroneMidWindowRace` in `test_router.py` first, launched a real mission over HTTP inside a TestClient mounting both the roster and missions routers, then monkeypatched `roster_service.get_active_mission_for_drone` with a wrapper that calls `mark_delivered` on the mission before returning it — reproducing exactly what the 5-second `run_delivery_scheduler` tick does in production. Run against the pre-fix code, this test failed with `app.missions.models.NoActiveMissionError` escaping the DELETE handler unhandled (the router's `except RosterError` never sees it, since `NoActiveMissionError` is a `MissionError`, not a `RosterError`) — the same 500-then-204-on-retry behavior `01-SECURITY.md` T-01-09 live-reproduced against the running app.
- **Narrow fix.** `roster/service.py::remove_drone` now imports `NoActiveMissionError` from `app.missions.models` and wraps the `recall_mission` call (only that call, not the whole function) in `try/except NoActiveMissionError`, logging `"mission for %s already resolved before recall; treating roster removal as recall-complete"` at INFO and falling through to the deletion. The check-first structure, the two-transaction ordering, and D-04's best-effort telemetry deregistration are all unchanged. Re-running the Task-1 test now passes (204).
- **Both racing writers pinned.** Task 2 added `TestRemoveDroneMidWindowRace` (3 tests) and `TestRemoveDroneCatchNarrowness` (2 tests) to `test_service.py`, reusing a new `_racing_check(resolve)` helper that wraps the real `get_active_mission_for_drone` and runs a caller-supplied resolution coroutine on the mission before returning it — a deterministic, non-flaky way to land exactly inside the check→recall window. Covers: the scheduler-delivery variant (terminal status preserved, zero recall-log rows), the concurrent-manual-recall variant (single recall-log row, `remaining_kwh` unchanged from the resolving recall alone), idempotency after a raced removal, catch narrowness (a different `MissionError` subclass still propagates and the roster row survives), and the diagnosability of the skipped-recall log line.
- **Full-suite and coverage gates green.** Full backend pytest suite: 216 passed (up from the 210-test baseline recorded in `01-VERIFICATION.md`). `app/roster/` statement coverage: 100% (all 5 files, 126 statements, 0 missing). `ruff check app/ tests/`: clean.
- **Grep-level closure checks pass.** `grep -c 'from app.missions.models import NoActiveMissionError' app/roster/service.py` → `1`. `grep -rn 'from app.roster' app/missions/` → no match (dependency stays one-directional). `inspect.getsource` check confirms the `except NoActiveMissionError` guard sits on the recall step, before `repository.remove_drone`.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — DELETE returns 204 when the scheduler resolves the mission mid-window** — `20e11a6` (fix)
2. **Task 2: Cover the second race variant, the audit trail, the catch's narrowness, and the log trace** — `e4a9f83` (test)

_Note: no separate plan-metadata commit — this is a parallel worktree plan; the orchestrator commits shared docs after the wave merges._

## Files Created/Modified

- `backend/app/roster/service.py` — Added narrow import of `NoActiveMissionError`; wrapped the `recall_mission` call in `try/except NoActiveMissionError` with an INFO log on skip; extended the `remove_drone` docstring to explain the guard and name the delivery scheduler as the concurrent writer it protects against.
- `backend/tests/roster/test_router.py` — Added `_client_with_missions()` helper (mounts roster + missions routers on one app) and `TestRemoveDroneMidWindowRace` (HTTP-level proof of the 204 contract under the scheduler race).
- `backend/tests/roster/test_service.py` — Added `_racing_check()` helper, `TestRemoveDroneMidWindowRace` (3 tests: scheduler-delivery variant, concurrent-manual-recall variant, idempotency after a race), and `TestRemoveDroneCatchNarrowness` (2 tests: a different `MissionError` subclass still propagates; the skipped recall is logged).

## Pre-Fix Failure Evidence (Task 1, Step 1)

Run before the fix landed:
```
uv run --extra dev pytest tests/roster/test_router.py::TestRemoveDroneMidWindowRace -x
```
Result: **FAILED** — `app.missions.models.NoActiveMissionError: no active mission for drone: FALCON-01` propagated unhandled through `app/roster/router.py:62` → `app/roster/service.py:60` → `app/missions/service.py:51` → `app/missions/repository.py:174`. FastAPI's `TestClient` (default `raise_server_exceptions=True`) surfaces this as an escaping exception rather than a captured 500 response body, but it is the identical unhandled-exception condition `01-SECURITY.md` T-01-09 observed as a literal HTTP 500 against the running server. After the fix (Task 1, Step 2), the same test passes with `response.status_code == 204`.

## Decisions Made

- Caught exactly `NoActiveMissionError`, never the `MissionError` base class or bare `Exception` — `TestRemoveDroneCatchNarrowness::test_different_mission_error_propagates_and_leaves_roster_row` proves a `DroneUnavailableError` raised from `recall_mission` still aborts the removal and leaves the `fleet_roster` row in place, so the guard cannot silently absorb a genuine failure and report a fake success.
- No new write path was introduced on the guarded branch: because `repository.recall()` raises `NoActiveMissionError` before its first SQL statement, the guarded path performs zero writes to `missions`, `mission_log`, or `budget_snapshots` — verified directly (terminal status preserved, recall-log row count exactly 0 for the scheduler variant and exactly 1, not 2, for the concurrent-recall variant, `remaining_kwh` unchanged).
- Reused a single `_racing_check(resolve)` / interleaving-wrapper pattern across both test files rather than real threading or `asyncio.sleep`-based races — deterministic and non-flaky, landing precisely inside the check→recall window every run.

## Deviations from Plan

None — plan executed exactly as written. Every acceptance criterion (test counts, grep checks, the `inspect.getsource` ordering check, coverage, ruff) passed on first attempt after the fix.

## Issues Encountered

- Same `uv` cache-directory issue documented in prior plans in this phase (`~/.cache/uv` is read-only in this sandbox): worked around by setting `UV_CACHE_DIR` to a writable scratch directory for all `uv run`/`uv sync` invocations. No source files affected — test-invocation detail only.

## Gap Closure Confirmation

This plan closes `ROST-02-TOCTOU`, the single blocking gap identified by four independent Phase 1 artifacts:
- `01-VERIFICATION.md` Gap 1 (blocker, truth #9) — now passes: `grep -rn 'NoActiveMissionError' app/roster/` matches `app/roster/service.py`.
- `01-REVIEW.md` CR-01 (Critical) + IN-01 (missing test) — both addressed: the guard matches the review's proposed fix shape, and the missing regression test now exists at both layers.
- `01-SECURITY.md` T-01-09 — disposition flips from `accept` (granted against a stale crash-window assumption) to `mitigate`, now fully implemented and tested. T-01-16 (over-broad catch) and T-01-17 (audit-trail falsification) are also closed by this same change, per the plan's threat register.
- `01-PATTERNS.md` line 192's assumption ("`NoActiveMissionError` is never raised in the roster removal path") is now corrected by the code itself: it is raised and caught, narrowly, exactly where the scheduler's window makes it reachable.

## Next Phase Readiness

- `roster.service.remove_drone` is now race-safe end-to-end; the chat phase's planned `roster_changes` "remove" action can call it directly with no further plumbing changes and inherits this fix automatically.
- Two items remain explicitly open per this plan's `flagged_assumptions` (unchanged by this run, by orchestrator scope): the ROST-04 structural-mirroring edge probe (unclassified, carried forward), and VERIFICATION Gap 2 / REVIEW WR-02 (telemetry source seeded from `DEFAULT_FLEET` rather than the persisted roster — non-blocking, needs its own plan before the Phase 4 Docker work where restarts become routine).
- No blockers.

---
*Phase: 01-roster-module*
*Completed: 2026-08-12*

## Self-Check: PASSED

Verified `backend/app/roster/service.py`, `backend/tests/roster/test_router.py`, and `backend/tests/roster/test_service.py` modifications present via `git diff d2a0c53d..HEAD --stat`; verified both commit hashes (`20e11a6`, `e4a9f83`) present in `git log --oneline`; re-ran `uv run --extra dev pytest -q` (216 passed), `uv run --extra dev pytest tests/roster/ --cov=app.roster --cov-report=term-missing` (100% coverage, 0 missing), and `uv run --extra dev ruff check app/ tests/` (clean) as the final state.
