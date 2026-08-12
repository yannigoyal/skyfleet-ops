---
phase: 01-roster-module
plan: 03
subsystem: api
tags: [fastapi, sqlite, roster, testing]

# Dependency graph
requires:
  - phase: 01-roster-module plan 01
    provides: roster/ package (models, repository, service, router) and shared FakeSource test doubles
  - phase: 01-roster-module plan 02
    provides: DELETE /api/roster/{drone_id} route and roster.service.remove_drone with D-03 auto-recall
provides:
  - "Full unit/integration test coverage for backend/app/roster/: models, repository, router error matrix"
  - "Executable ROST-04 layering assertion (TestLayering) that fails if a future edit routes a roster write around roster.service"
  - "100% statement/branch coverage of app/roster/ (122/122 statements)"
affects: [chat phase (roster_changes action can rely on this test suite as a regression backstop)]

# Actuals (#2632)
actuals:
  tokens: 2107
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Behavioural layering proof via monkeypatch on the service module object, not source-text inspection: router.py's `from . import service` binds the module, so monkeypatch.setattr(roster_service, 'add_drone', fake) is observed by the router's late-bound service.add_drone(...) call"
    - "asyncio.gather(..., return_exceptions=True) against two overlapping repository.add_drone() calls proves the UNIQUE(operator_id, drone_id) constraint enforces single-row semantics, not application-level duplicate checking"

key-files:
  created:
    - backend/tests/roster/test_models.py
    - backend/tests/roster/test_repository.py
  modified:
    - backend/tests/roster/test_router.py

key-decisions:
  - "test_repository.py ported TestListRoster/TestAddDrone/TestRemoveDrone verbatim from branch 2ba52a8 per D-01/RESEARCH finding of no schema drift, then added TestConcurrentDuplicateAdd as the one new class the branch lacked"
  - "test_router.py's new TestAddDroneErrors/TestTelemetryMerge/TestLayering classes were added alongside the existing TestAddDrone/TestRemoveDrone classes from plans 01/02 rather than replacing them - some assertions overlap (e.g. duplicate-409, empty-422) but each class targets a distinct behavioural contract (basic CRUD vs. the full error-and-isolation matrix vs. layering), and the plan's own acceptance criteria list all three as required test classes"
  - "No changes to backend/app/roster/router.py were needed - the existing _ERROR_STATUS table, _TELEMETRY_FIELDS tuple, and service-delegation in both write handlers already satisfied every new test's assertions on first run"

patterns-established:
  - "TestLayering pattern (monkeypatch the service module + assert via a shared mutable dict) is reusable for any future cross-module delegation proof (e.g. chat.service delegating to roster.service/missions.service)"

requirements-completed: [ROST-01, ROST-02, ROST-03, ROST-04]

coverage:
  - id: D1
    description: "POST /api/roster with a drone_id already on the roster returns 409 with {\"reason\": \"drone_already_tracked\"} and does not grow the roster"
    requirement: "ROST-01"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDroneErrors::test_duplicate_returns_409_and_roster_still_lists_ten"
        status: pass
      - kind: unit
        ref: "backend/tests/roster/test_repository.py::TestAddDrone::test_duplicate_does_not_grow_roster"
        status: pass
    human_judgment: false
  - id: D2
    description: "POST /api/roster with an empty or missing drone_id returns 422 before any database access, and the roster is untouched"
    requirement: "ROST-01"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDroneErrors::test_empty_drone_id_returns_422_and_roster_unchanged"
        status: pass
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDroneErrors::test_missing_drone_id_returns_422_and_roster_unchanged"
        status: pass
    human_judgment: false
  - id: D3
    description: "DELETE /api/roster/{drone_id} for a never-tracked drone returns 404 with {\"reason\": \"unknown_drone\"}"
    requirement: "ROST-02"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestAddDroneErrors::test_delete_unknown_drone_returns_404"
        status: pass
      - kind: unit
        ref: "backend/tests/roster/test_repository.py::TestRemoveDrone::test_rejects_unknown_drone"
        status: pass
    human_judgment: false
  - id: D4
    description: "A roster entry with no telemetry reading is returned as exactly {drone_id, added_at}; one with a cached reading adds exactly the four telemetry fields"
    requirement: "ROST-03"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestTelemetryMerge::test_no_telemetry_key_set_is_exactly_drone_id_and_added_at"
        status: pass
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestTelemetryMerge::test_with_telemetry_key_set_adds_exactly_four_fields"
        status: pass
      - kind: unit
        ref: "backend/tests/roster/test_models.py::TestRosterEntry::test_to_dict_shape"
        status: pass
    human_judgment: false
  - id: D5
    description: "Roster reads and writes are scoped to one operator: a drone added under a different operator_id is invisible to both the repository listing and the GET /api/roster response"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_repository.py::TestListRoster::test_ignores_other_operators"
        status: pass
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestTelemetryMerge::test_other_operator_drone_absent_from_response"
        status: pass
    human_judgment: false
  - id: D6
    description: "backend/app/roster/ mirrors backend/app/missions/'s five-module layering, and both HTTP write handlers route through roster.service rather than roster.repository"
    requirement: "ROST-04"
    verification:
      - kind: integration
        ref: "backend/tests/roster/test_router.py::TestLayering::test_post_and_delete_delegate_to_service"
        status: pass
      - kind: unit
        ref: "backend/tests/roster/test_router.py::TestLayering::test_roster_submodules_import_cleanly"
        status: pass
      - kind: other
        ref: "ls backend/app/roster/ backend/tests/roster/ - five source modules, six test modules present"
        status: pass
    human_judgment: false
  - id: D7
    description: "Two overlapping add_drone calls for the same new drone_id leave exactly one row; the loser raises DroneAlreadyTrackedError"
    requirement: "ROST-01"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_repository.py::TestConcurrentDuplicateAdd::test_only_one_row_survives_overlapping_add"
        status: pass
    human_judgment: false
  - id: D8
    description: "[UNRESOLVED probe row - ROST-04, category unclassified] ROST-04 is a structural layering requirement with no runtime edge behaviour the edge probe could classify"
    requirement: "ROST-04"
    verification:
      - kind: other
        ref: "human inspection of backend/app/roster/ vs backend/app/missions/ module layout"
        status: needs_verification
    human_judgment: true
    human_judgment_note: "Carried forward from the plan's must_haves.truths backstop marker, unresolved by design. TestLayering (D6) covers the runtime-observable half of ROST-04 (delegation + importability); the plan explicitly flags that no automated probe can fully confirm structural mirroring intent, so a reviewer should visually confirm backend/app/roster/ has the same five-file shape as backend/app/missions/ (it does - confirmed via ls in this plan's own verification step, but the plan asks that this remain a flagged assumption rather than silently marked resolved)."

duration: 18min
completed: 2026-08-12
status: complete
---

# Phase 1 Plan 3: Roster Module Validation and Error States Summary

**Full backend test coverage for the roster module's failure modes (duplicate-add 409, empty/missing-field 422, unknown-drone 404, cross-operator isolation) plus an executable ROST-04 layering assertion that fails if a future edit routes a roster write around `roster.service` — no production code changes needed, since the module built in plans 01/02 already satisfied every new test on first run.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-08-12 (session start)
- **Completed:** 2026-08-12
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- `backend/tests/roster/test_models.py` (new): pins `RosterEntry.to_dict()`'s exact two-key shape and every `RosterError` subclass's `reason`/`drone_id`/subclass-of-`RosterError` contract
- `backend/tests/roster/test_repository.py` (new): ports the branch-`2ba52a8` list/add/remove suite verbatim, plus a new `TestConcurrentDuplicateAdd` proving the `UNIQUE(operator_id, drone_id)` DB constraint — not application code — is what makes two overlapping `add_drone` calls for the same new drone leave exactly one row
- `backend/tests/roster/test_router.py` (extended): adds `TestAddDroneErrors` (409/422/422/404, each asserting the roster is left unchanged), `TestTelemetryMerge` (exact response key-set with and without cached telemetry, plus cross-operator isolation at the HTTP boundary), and `TestLayering` (monkeypatches `roster.service.add_drone`/`remove_drone` to behaviourally prove both HTTP write handlers delegate to the service layer, plus a structural import check across all four `app.roster` submodules)
- Full backend suite: 210 tests passing (up from 186 after plan 02); `app/roster/` at 100% statement coverage (122/122), no uncovered branch in `service.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Model and repository coverage, including single-operator isolation** - `0616dfd` (test)
2. **Task 2: HTTP error matrix and the ROST-04 layering assertion** - `46760c7` (test)

_Note: no separate plan-metadata commit — this is a parallel worktree plan; the orchestrator commits shared docs after the wave merges._

## Files Created/Modified
- `backend/tests/roster/test_models.py` - `TestRosterEntry` (to_dict key-set), `TestRosterErrors` (reason codes, subclass check, drone_id attribute, base-class default)
- `backend/tests/roster/test_repository.py` - `TestListRoster` (incl. `test_ignores_other_operators`), `TestAddDrone`, `TestRemoveDrone`, `TestConcurrentDuplicateAdd`
- `backend/tests/roster/test_router.py` - added `TestAddDroneErrors`, `TestTelemetryMerge`, `TestLayering` alongside the existing plan 01/02 classes

## Decisions Made
- Kept the existing `TestAddDrone`/`TestRemoveDrone` classes from plans 01/02 in `test_router.py` rather than folding them into the new `TestAddDroneErrors` class — some assertions overlap (duplicate-409, empty-422), but the plan's acceptance criteria explicitly names all three new classes (`TestAddDroneErrors`, `TestTelemetryMerge`, `TestLayering`) as required, and splitting basic-CRUD from full-error-matrix from layering-proof keeps each class's intent legible
- `TestLayering`'s delegation proof monkeypatches the `app.roster.service` module object (imported as `roster_service` to avoid a name collision with the router's local `service` import) rather than text-matching `router.py`'s source — this means the test fails if a future edit reaches into `roster.repository` directly for a write, exactly as ROST-04 requires, without being fragile to refactors that keep the same behavioural contract
- No changes to `backend/app/roster/router.py`: `_ERROR_STATUS`, `_TELEMETRY_FIELDS`, and both write handlers' service delegation already matched every acceptance criterion on the first test run — the module built in plans 01/02 needed no fixes

## Deviations from Plan

None - plan executed exactly as written. All test classes named in the plan's `<action>` sections were added; no `<files>` beyond the three test files were touched, since `backend/app/roster/router.py` (listed as modifiable "only so a layering or status-code gap ... can be fixed in place") required no changes.

## Issues Encountered
- The sandboxed environment's default `uv` cache directory (`~/.cache/uv`) is read-only (same issue documented in plans 01 and 02's summaries), and this worktree has no pre-built `.venv` to fall back to (unlike plan 01's session). Worked around by setting `UV_CACHE_DIR` to a writable scratch directory (`/tmp/claude-1000/uv-cache-a5bdeb`) for all `uv run` invocations, which triggered a fresh `uv sync` (Python 3.13, ~36 packages) on first use. No source files were affected; this is a local test-invocation detail only.

## Next Phase Readiness
- The roster module (`backend/app/roster/`) is now fully tested end-to-end: models, repository, service (from plans 01/02), and router, at 100% statement coverage with no uncovered branches
- ROST-01, ROST-02, ROST-03, and ROST-04 all have passing automated verification; ROST-04's structural-mirroring half is carried forward as an explicit backstop-tier flag per the plan's `must_haves.truths` (see coverage id D8) rather than silently marked fully resolved
- The chat phase's `roster_changes` action can call `roster.service.add_drone`/`remove_drone` directly, backed by this test suite as a regression backstop
- No blockers

---
*Phase: 01-roster-module*
*Completed: 2026-08-12*

## Self-Check: PASSED

Verified `backend/tests/roster/test_models.py` and `backend/tests/roster/test_repository.py` present on disk (new files); verified `backend/tests/roster/test_router.py` modification present via `git diff`; verified both commit hashes (`0616dfd`, `46760c7`) present in `git log --oneline`. Full backend suite (210 tests) and `ruff check app/ tests/` both green as of the final commit; `app/roster/` coverage confirmed at 100% (122/122 statements, no missing branches).
