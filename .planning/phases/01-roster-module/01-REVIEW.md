---
phase: 01-roster-module
reviewed: 2026-08-12T16:57:55Z
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
  critical: 0
  warning: 2
  info: 0
  total: 2
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-08-12T16:57:55Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

This review supersedes the prior `01-REVIEW.md`. That review's CR-01 (check-then-act TOCTOU race between `remove_drone`'s active-mission check and its `recall_mission()` call) and IN-01 (missing regression coverage for that race) are both re-verified here against the gap-closure fix landed in plan 01-04.

**CR-01 — verified resolved.** The fix in `backend/app/roster/service.py:68-77` wraps `await recall_mission(db, drone_id)` in a narrow `except NoActiveMissionError` guard. Tracing the actual concurrency model: `Database.transaction()` and `Database.fetchall()` both serialize through the same `asyncio.Lock` (`backend/app/db/connection.py:53-79`), so `repository.recall()` (`backend/app/missions/repository.py:165-190`) is itself atomic — it re-checks `status = 'en_route'` inside its own locked transaction rather than trusting the earlier read. The only window that matters is between the check's `fetchall` (lock released) and the recall's `transaction` (lock re-acquired); if a concurrent writer (delivery scheduler marking the mission `delivered`, or another manual recall) wins that window, `recall()`'s own re-check finds no `en_route` row and raises `NoActiveMissionError` — which is exactly what the new guard catches. This closes the race correctly: the second, authoritative check inside `recall()`'s locked transaction is what actually resolves the TOCTOU, and the guard just stops that expected outcome from surfacing as an unhandled 500.

Audit-trail correctness holds: when the guard fires, `recall()` raised before writing anything (its `mission_log`/`budget_snapshots` inserts only happen after the row-found check succeeds), so there is no duplicate or orphaned `mission_log` "recall" row — confirmed by `test_service.py::TestRemoveDroneMidWindowRace::test_scheduler_delivery_variant_preserves_terminal_status_and_no_recall_log` (asserts `recall` log count == 0 when the scheduler wins the race) and `...test_concurrent_manual_recall_variant_preserves_single_recall_log_and_budget` (asserts exactly 1 `recall` log entry, and that the budget delta from the concurrent writer's own recall is preserved, not double-applied).

The catch is appropriately narrow, not a blanket `except MissionError`: `test_service.py::TestRemoveDroneCatchNarrowness::test_different_mission_error_propagates_and_leaves_roster_row` proves a different `MissionError` subtype (`DroneUnavailableError`) still propagates out of `remove_drone` and leaves the roster row intact, rather than being swallowed.

**IN-01 — resolved.** Regression coverage now exists at both layers: `test_service.py::TestRemoveDroneMidWindowRace` (service-layer, both a "delivery scheduler wins" and a "concurrent manual recall wins" variant, monkeypatching `service.get_active_mission_for_drone` to inject the race inside the check→recall window) and `test_router.py::TestRemoveDroneMidWindowRace::test_scheduler_delivers_mission_inside_check_recall_window_returns_204` (HTTP-level, real mission launched over `TestClient`, asserts `DELETE /api/roster/{drone_id}` returns 204 rather than an unhandled 500).

No new critical issues were introduced by the fix. Two pre-existing, non-blocking robustness/architecture concerns are noted below — neither is a regression caused by this change, but both are directly adjacent to the code touched by it.

## Warnings

### WR-01: Roster service reaches into the missions module's repository layer directly

**File:** `backend/app/roster/service.py:9-10`
**Issue:** `from app.missions.repository import get_active_mission_for_drone` imports directly from another domain's repository module. Per this project's own layering convention (Router → Service → Repository → Database, one domain's service depends on *its own* repository, or on another domain's *service*, not another domain's repository), this creates tight coupling to `missions`' internal persistence details. `app.missions`'s `__all__` (`backend/app/missions/__init__.py`) does not export `repository` or `get_active_mission_for_drone` at all — the import bypasses the intended public surface. It works today because `missions.repository`'s query shape happens to match what roster needs, but it means any change to how "active mission" is represented in the `missions` module (e.g. a status rename, or adding a required parameter) will silently break `roster` without either module's own test suite reliably catching the coupling.
**Fix:** Expose a small public function on `app.missions` (e.g. `has_active_mission(db, drone_id)` re-exported from `missions/__init__.py` or `missions/service.py`) and have `roster/service.py` import that instead of reaching into `missions.repository` directly.

### WR-02: `remove_drone`'s recall step can only ever raise one caught type today, but the router doesn't defend against others

**File:** `backend/app/roster/router.py:59-65`, `backend/app/roster/service.py:68-77`
**Issue:** `router.remove_drone` only catches `RosterError` (`_ERROR_STATUS` only maps `unknown_drone` / `drone_already_tracked`). `service.remove_drone` calls into `app.missions.service.recall_mission`, which is a `MissionError` producer, not a `RosterError` producer. Today this is safe only because `repository.recall()` (the sole thing `recall_mission()` calls) raises exactly one exception type, `NoActiveMissionError`, which the new guard fully absorbs — confirmed by `test_service.py::TestRemoveDroneCatchNarrowness::test_different_mission_error_propagates_and_leaves_roster_row`, which shows that if `recall_mission` ever raises a *different* `MissionError` subtype (e.g. `DroneUnavailableError`), it propagates out of `service.remove_drone` uncaught. Since the router only translates `RosterError`, that would surface to the HTTP client as an unhandled exception → framework default 500, not a structured `{"detail": {"reason": ...}}` response consistent with every other error path in this API surface.
**Fix:** Either (a) have `router.remove_drone`'s except clause also catch `MissionError` and translate via a small combined status map, or (b) have `service.remove_drone` explicitly re-raise any non-`NoActiveMissionError` `MissionError` as a roster-domain error so the router's existing `RosterError` handling stays sufficient. Low urgency since no current code path can trigger it, but it's a latent gap the next mission-side change could open silently.

---

_Reviewed: 2026-08-12T16:57:55Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
