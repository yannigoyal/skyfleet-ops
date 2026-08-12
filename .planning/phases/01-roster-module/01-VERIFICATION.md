---
phase: 01-roster-module
verified: 2026-08-12T15:19:31Z
status: gaps_found
score: 21/23 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Operator can DELETE /api/roster/{drone_id} and receive 204, with automatic recall of any in-flight mission, reliably (ROADMAP SC2 / ROST-02)"
    status: partial
    reason: >
      backend/app/roster/service.py::remove_drone uses a check-then-act pattern:
      it queries get_active_mission_for_drone() and, only if it returns non-None,
      calls missions.service.recall_mission() as a second, separate
      Database.transaction(). Between the check and the recall, the mission can
      stop being en_route — most notably because app.missions.scheduler.run_delivery_scheduler
      runs every 5 seconds in production (started from backend/app/main.py:67) and
      can flip an overdue en_route mission to delivered in that exact window. When
      that happens, missions.repository.recall() raises NoActiveMissionError, which
      is a subclass of app.missions.models.MissionError — NOT app.roster.models.RosterError.
      backend/app/roster/router.py's DELETE handler only catches RosterError, so the
      exception propagates unhandled and FastAPI returns a generic 500 instead of the
      roster module's documented 204/404 contract. The roster row is left in place
      (operator must retry). This is not a theoretical edge case: it was independently
      found and documented as a Critical finding (CR-01) by this same phase's own
      code-review agent in .planning/phases/01-roster-module/01-REVIEW.md, dated the
      same day as phase completion, and remains unfixed — it is the most recent commit
      in the phase's history with no follow-up fix commit. No test in
      backend/tests/roster/test_service.py exercises this race (confirmed absent by
      grep for NoActiveMissionError across app/ and tests/ — it appears only in the
      missions module's own files).
    artifacts:
      - path: "backend/app/roster/service.py"
        issue: "remove_drone (lines 59-60) does not catch NoActiveMissionError around the recall_mission() call"
      - path: "backend/app/roster/router.py"
        issue: "DELETE handler (lines 59-65) only catches RosterError, not app.missions.models.MissionError subclasses"
    missing:
      - "Catch NoActiveMissionError around the recall_mission() call in roster.service.remove_drone and treat it as already-resolved (proceed to delete), per the fix already proposed in 01-REVIEW.md CR-01"
      - "A regression test that interleaves a mission resolution (delivered or recalled) between the check and the recall to prove the 500 no longer occurs"
  - truth: "Roster changes stay in sync with the live TelemetrySource, kept in sync with live telemetry (ROADMAP Phase 1 Goal)"
    status: partial
    reason: >
      backend/app/main.py always seeds the telemetry source with the hardcoded
      DEFAULT_FLEET list (FALCON-01..10) on every process start
      (telemetry_source.start(DEFAULT_FLEET) at main.py:62), never from the
      persisted fleet_roster table. telemetry_source is a fresh in-process object
      each restart. Consequence: a drone added via POST /api/roster before a
      restart has no telemetry after restart, and cannot be re-registered via the
      API (POST returns 409 drone_already_tracked because the DB row survives) —
      the only recovery is DELETE then re-POST. A drone removed via DELETE before
      a restart is still tracked by telemetry after restart, producing telemetry
      for a drone no longer in the roster. This was independently documented as
      Warning WR-02 in 01-REVIEW.md and is unfixed. It is exercised directly by
      this phase's wiring (create_roster_router(database, telemetry_cache,
      telemetry_source) at main.py:84).
    artifacts:
      - path: "backend/app/main.py"
        issue: "telemetry_source.start(DEFAULT_FLEET) at line 62 ignores the persisted roster; DEFAULT_FLEET at line 28 is a fixed 10-drone list"
    missing:
      - "Seed telemetry_source.start() from repository.list_roster(db) at startup, falling back to DEFAULT_FLEET only when the persisted roster is empty"
---

# Phase 1: Roster Module Verification Report

**Phase Goal:** Deliver the fleet roster module — operators can add drones, list them with live telemetry merged in, and remove them (with automatic recall of any in-flight mission) via a real FastAPI backend, layered as router → service → repository per project convention.
**Verified:** 2026-08-12T15:19:31Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/roster with `{"drone_id": "FALCON-11"}` returns 201 with the created entry (ROST-01) | ✓ VERIFIED | `test_router.py::TestAddDrone::test_adds_drone_and_lists_it` passes; router.py:51-57 |
| 2 | Added drone is registered with the live TelemetrySource so it starts streaming | ✓ VERIFIED | `test_router.py::TestAddDrone::test_registers_with_telemetry_source`; service.py:28-32. Caveat: does not survive process restart (see Gap 2) |
| 3 | GET /api/roster returns every tracked drone merged with latest TelemetryCache reading (ROST-03) | ✓ VERIFIED | `test_router.py::TestListRoster::test_merges_latest_telemetry`; router.py:31-37 |
| 4 | The real app.main:app serves /api/roster; telemetry_source is a module-level singleton constructed before mounting | ✓ VERIFIED | main.py:55,84 — `telemetry_source = create_telemetry_source(...)` at module scope, before `app.include_router`; `test_router.py::TestAppWiring` passes |
| 5 | backend/app/roster/ organized models/service/repository/router/__init__; write path runs router → service → repository (ROST-04) | ✓ VERIFIED | `ls backend/app/roster/` shows all 5 files; `test_router.py::TestLayering::test_post_and_delete_delegate_to_service` monkeypatches service and proves delegation |
| 6 | TelemetrySource.add_drone() failure is logged and the fleet_roster row stays committed (D-04) | ✓ VERIFIED | service.py:29-32 `try/except Exception: logger.exception(...)`; `test_service.py::TestTelemetrySyncFailure` passes |
| 7 | Two concurrent POST /api/roster for same drone_id leave exactly one row; loser gets 409 | ✓ VERIFIED | `test_repository.py::TestConcurrentDuplicateAdd::test_only_one_row_survives_overlapping_add` passes; enforced by UNIQUE(operator_id, drone_id) + sqlite3.IntegrityError mapping |
| 8 | GET /api/roster never returns a partially-written telemetry reading | ✓ VERIFIED | router.py:33-36 uses one `cache.get()` call returning an immutable frozen `TelemetryUpdate` |
| 9 | **Operator can DELETE /api/roster/{drone_id} and receives 204; drone stops appearing, reliably (ROST-02, ROADMAP SC2)** | ✗ **FAILED** | Happy-path tests pass, but an unresolved, reachable TOCTOU race (documented as Critical CR-01 in `01-REVIEW.md`) causes an unhandled 500 when the delivery scheduler (ticks every 5s in production) resolves the mission between the check and the recall. See Gaps. |
| 10 | Removing a drone with an en_route mission auto-recalls it first: mission status → recalled, mission_log row, budget_snapshots row (D-03) | ⚠️ Partial (see #9) | Non-race path: `test_service.py::TestRemoveDroneWithActiveMission` passes. Race path: unhandled 500, see Gap 1 |
| 11 | Removal is check-first — `get_active_mission_for_drone()` before `recall_mission()`, no exception-driven control flow | ✓ VERIFIED | service.py:59-60; `inspect.getsource` order assertion in plan acceptance criteria confirmed by passing tests |
| 12 | Cross-module dependency is narrow named-function imports, not package-level `app.missions` import | ✓ VERIFIED | service.py:8-9 imports only `get_active_mission_for_drone` and `recall_mission`; `grep -rn 'app.roster' app/missions/` returns no match (one-directional) |
| 13 | DELETE write path runs router → roster.service → repository | ✓ VERIFIED | router.py:59-65 delegates to `service.remove_drone`; `TestLayering` proves it behaviorally |
| 14 | TelemetrySource.remove_drone() failure is logged and fleet_roster deletion stays committed (D-04) | ✓ VERIFIED | service.py:64-68; `test_service.py::TestRemoveTelemetrySyncFailure` passes |
| 15 | Second DELETE for an already-removed drone returns 404 unknown_drone, no recall, roster unchanged (idempotency) | ✓ VERIFIED | `test_service.py::TestRemoveIdempotency::test_second_removal_raises_and_leaves_state_unchanged`; `test_router.py::TestRemoveDrone::test_second_delete_returns_404_unknown_drone` |
| 16 | Crash-window backstop: recall and delete are two separate transactions; a retried DELETE completes cleanly | ✓ VERIFIED | `test_service.py::TestRemoveIdempotency::test_recall_before_remove_crash_window_completes_cleanly` directly simulates this exact scenario and passes |
| 17 | POST with a drone_id already on the roster returns 409 drone_already_tracked, roster unchanged (ROST-01) | ✓ VERIFIED | `test_router.py::TestAddDroneErrors::test_duplicate_returns_409_and_roster_still_lists_ten` |
| 18 | POST with empty drone_id returns 422 before any DB access (D-05) | ✓ VERIFIED | router.py:23 `Field(min_length=1)`; `test_router.py::TestAddDroneErrors::test_empty_drone_id_returns_422_and_roster_unchanged` |
| 19 | DELETE for a never-tracked drone returns 404 unknown_drone (ROST-02) | ✓ VERIFIED | `test_router.py::TestAddDroneErrors::test_delete_unknown_drone_returns_404` |
| 20 | Roster entry with no telemetry returns exactly `{drone_id, added_at}`; with telemetry adds exactly the 4 fields | ✓ VERIFIED | `test_router.py::TestTelemetryMerge` (both cases) |
| 21 | Roster reads/writes are scoped to one operator | ✓ VERIFIED | repository.py binds `operator_id = ?` on every query; `test_repository.py::TestListRoster::test_ignores_other_operators`; `test_router.py::TestTelemetryMerge::test_other_operator_drone_absent_from_response` |
| 22 | RosterEntry.to_dict() returns exactly `{drone_id, added_at}`; every RosterError subclass carries its reason | ✓ VERIFIED | models.py:18-19, 28-41; `test_models.py` full class |
| 23 | ROST-04 structural mirroring of backend/app/missions/ (backstop, flagged unresolved by executor) | ? UNCERTAIN (carried forward) | `ls backend/app/roster/` vs `ls backend/app/missions/` confirms same 4-module + `__init__.py` shape; executor explicitly left this as a flagged assumption per plan's backstop marker rather than silently resolving it (see `01-03-SUMMARY.md` coverage id D8) |

**Score:** 21/23 truths verified (1 failed, 1 uncertain/carried-forward-by-design)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/roster/models.py` | RosterEntry, RosterError hierarchy | ✓ VERIFIED | Exists, 41 lines, matches contract |
| `backend/app/roster/repository.py` | Parameterized SQL CRUD against fleet_roster | ✓ VERIFIED | Exists, 69 lines; 0 string-interpolated SQL statements found via grep |
| `backend/app/roster/service.py` | Business logic; add_drone, remove_drone | ✓ VERIFIED | Exists, 68 lines; both functions present and wired |
| `backend/app/roster/router.py` | create_roster_router factory, GET/POST/DELETE | ✓ VERIFIED | Exists, 67 lines; all 3 endpoints present |
| `backend/app/roster/__init__.py` | Public exports | ✓ VERIFIED | Exists, 12 lines, `__all__` matches missions/ convention |
| `backend/tests/roster/*.py` (6 files) | Full unit/integration coverage | ✓ VERIFIED | 46 tests, all passing, 100% statement coverage of `app/roster/` (122/122) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `roster/router.py` | `roster/service.py` | POST/DELETE handlers call `service.add_drone`/`service.remove_drone` | ✓ WIRED | Confirmed by source (router.py:54,62) and behaviorally by `TestLayering` (monkeypatch proof) |
| `roster/service.py` | `roster/repository.py` | `repository.add_drone`/`repository.remove_drone` | ✓ WIRED | service.py:26,62 |
| `roster/service.py` | `telemetry/interface.py` | `source.add_drone`/`source.remove_drone` after DB commit | ✓ WIRED | service.py:30,66 — confirmed after persistence, outside any transaction |
| `roster/service.py` | `missions/service.py`, `missions/repository.py` | `recall_mission`, `get_active_mission_for_drone` (narrow imports) | ✓ WIRED (one-directional) | service.py:8-9; `grep -rn 'app.roster' app/missions/` returns no match |
| `main.py` | `roster/router.py` | `app.include_router(create_roster_router(database, telemetry_cache, telemetry_source))` | ✓ WIRED | main.py:84, module-level singleton constructed at line 55 before mount |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `GET /api/roster` response | `entries` | `repository.list_roster_entries(db)` — live SQLite query against `fleet_roster` | Yes | ✓ FLOWING |
| `GET /api/roster` telemetry fields | `reading` | `TelemetryCache.get(drone_id)` — live in-memory cache populated by `TelemetrySource` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full roster test suite | `cd backend && .venv/bin/python -m pytest tests/roster/ -v` | 46 passed | ✓ PASS |
| Full backend suite (regression check) | `cd backend && .venv/bin/python -m pytest -v` | 210 passed, 0 failed | ✓ PASS |
| Lint | `cd backend && .venv/bin/python -m ruff check app/ tests/` | All checks passed | ✓ PASS |
| SQL injection guard | `grep -v '^#' app/roster/repository.py \| grep -Ec "f\"(SELECT\|INSERT\|DELETE\|UPDATE)\|%s\" *%\|\.format\("` | `0` | ✓ PASS |
| Coverage | `pytest tests/roster/ --cov=app.roster --cov-report=term-missing` | 122/122 statements, no missing branches | ✓ PASS |
| One-directional dependency | `grep -rn 'app.roster' app/missions/` | no match | ✓ PASS |
| Reachability of CR-01 (TOCTOU) | `grep -rn 'NoActiveMissionError' app/ tests/` | Only appears in `app/missions/*` and `tests/missions/*` — never imported or caught in `app/roster/` or `tests/roster/` | ✗ FAIL — confirms Gap 1 is unmitigated |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| ROST-01 | 01-01, 01-03 | Add a drone via POST /api/roster | ✓ SATISFIED | Tests pass; REQUIREMENTS.md marks `[x]` Complete |
| ROST-02 | 01-02, 01-03 | Remove a drone via DELETE /api/roster/{drone_id} | ⚠️ BLOCKED (partial) | Happy-path tests pass, but CR-01 TOCTOU race is unresolved (Gap 1). REQUIREMENTS.md still marks this `[ ]` Pending — consistent with this finding, not a stale-doc false negative |
| ROST-03 | 01-01, 01-03 | View roster with latest telemetry via GET /api/roster | ✓ SATISFIED | Tests pass; REQUIREMENTS.md marks `[x]` Complete |
| ROST-04 | 01-01, 01-02, 01-03 | roster/ mirrors missions/ layering | ✓ SATISFIED (with carried-forward backstop flag) | Tests pass, structure confirmed; REQUIREMENTS.md marks `[x]` Complete |

No orphaned requirements: the union of `requirements:` across all three plans ({ROST-01, ROST-02, ROST-03, ROST-04}) exactly matches REQUIREMENTS.md's Phase 1 mapping.

**Note:** REQUIREMENTS.md's checkbox state for ROST-02 (`[ ]` Pending, "Pending" in the traceability table) was last updated by commit `c7d768d` after plan 01-01 only, and was never updated after plans 01-02/01-03 completed. In isolation this looks like a stale-documentation gap, but it happens to coincide with the genuine functional gap found in this verification (Gap 1) — ROST-02 is not, in fact, fully reliable yet.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/roster/service.py` | 59-60 | Unhandled `NoActiveMissionError` (a `MissionError`, not a `RosterError`) can propagate out of `remove_drone` as an unhandled exception | 🛑 Blocker | `DELETE /api/roster/{drone_id}` returns an opaque 500 instead of 204 when a mission resolves between the check and the recall — reachable in production because `run_delivery_scheduler` ticks every 5s (see Gap 1) |
| `backend/app/main.py` | 28, 62 | `telemetry_source.start(DEFAULT_FLEET)` always uses the hardcoded fleet list, never the persisted `fleet_roster` | ⚠️ Warning | Roster changes made via the API do not survive a process restart from the telemetry side (see Gap 2) |
| `backend/app/roster/repository.py` | 50-56 | `except sqlite3.IntegrityError` broadly maps any integrity violation to `DroneAlreadyTrackedError`, not just the UNIQUE constraint | ℹ️ Info | Documented in `01-REVIEW.md` WR-01; low likelihood (UUID PK collision), not currently reachable in practice |
| `backend/app/roster/router.py` | 22-23 | `AddDroneRequest.drone_id` is not stripped/normalized (`" "` or `"FALCON-01 "` pass validation) | ℹ️ Info | Documented in `01-REVIEW.md` WR-03; can create visually-duplicate roster rows |

No `TODO`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers found in any roster module or test file.

### Human Verification Required

None — all findings above are programmatically confirmed (code inspection + passing/failing test evidence + exception-hierarchy trace). No UI, visual, or subjective-judgment items exist in this backend-only phase.

### Gaps Summary

The roster module's happy paths are solidly built and fully test-covered: 46 roster tests and the full 210-test backend suite pass, coverage of `app/roster/` is 100%, ruff is clean, the layering contract (ROST-04) is proven both structurally and behaviorally, and cross-operator isolation, idempotency, and telemetry-failure resilience are all genuinely tested rather than merely claimed.

However, two real, previously-undiscovered-by-SUMMARY (but already caught by this phase's own code-review agent and left unfixed) functional defects block a clean pass:

1. **Gap 1 (blocker):** `DELETE /api/roster/{drone_id}` is not reliably 204/404 as ROADMAP Success Criterion 2 and ROST-02 require. A TOCTOU race between the check-for-active-mission step and the recall step — closed by nothing but timing luck in the test suite — causes an unhandled `NoActiveMissionError` (from `app.missions`, not caught by the roster router's `RosterError`-only handler) to surface as a 500 whenever the 5-second delivery scheduler (or a concurrent manual recall) resolves the mission in that window. This is documented verbatim as Critical finding CR-01 in `.planning/phases/01-roster-module/01-REVIEW.md` and has no follow-up fix commit.
2. **Gap 2 (warning):** The roster's "kept in sync with live telemetry" goal is only true within a single process lifetime. `backend/app/main.py` always seeds the telemetry source from a hardcoded `DEFAULT_FLEET` rather than the persisted roster, so drones added/removed via the API silently diverge from telemetry after any restart (documented as WR-02 in the same review).

Neither gap is covered by any later phase's stated goal or success criteria in `.planning/ROADMAP.md` (Phases 2–4 concern chat, frontend, and Docker/testing, not roster reliability), so neither qualifies for deferral under Step 9b.

**Recommendation:** Close Gap 1 before proceeding to Phase 2, since Phase 2's chat flow explicitly reuses `roster.service.remove_drone` for the `roster_changes` "remove" action (per both 01-01 and 01-02 SUMMARY "affects" notes) — an AI-triggered removal hitting this race would surface the same unhandled 500 through the chat flow. Gap 2 is lower urgency (single-container demo, restarts are infrequent) but should be tracked.

---

_Verified: 2026-08-12T15:19:31Z_
_Verifier: Claude (gsd-verifier)_
