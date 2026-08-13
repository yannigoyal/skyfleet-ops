---
phase: 02-ai-flight-director-chat
plan: 03
subsystem: api
tags: [fastapi, chat, roster, missions, service-layer, pytest, ast]

# Dependency graph
requires:
  - phase: 02-ai-flight-director-chat
    provides: "plan 02-01's chat router tracer slice (launch-only), FlightDirectorReply/MissionAction/RosterChange schema, mock_reply, chat_messages persistence"
provides:
  - "Chat-issued recall executing through missions.service.recall_mission"
  - "Chat-issued roster add/remove executing through roster.service.add_drone / remove_drone"
  - "A structural import-boundary test proving chat/router.py can never import roster/missions persistence modules"
  - "A two-database differential test proving chat-issued and manual roster removal produce identical final state"
affects: ["02-04", "phase-3 frontend chat integration"]

# Actuals (#2632)
actuals:
  tokens: 5427
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Chat router write path only imports domain service modules, never persistence — enforced by an AST-based structural test, not just convention"
    - "Differential testing: run the same mutation through two independent code paths against two independent Database instances, assert byte-identical final state"

key-files:
  created: []
  modified:
    - backend/app/chat/router.py
    - backend/tests/chat/test_router.py

key-decisions:
  - "Reproduced the exact reference-branch defect (git show 2ba52a8) in a scratch edit before writing the final implementation, confirming the differential test and the import-boundary test both fail against it — not just pass against the correct code"
  - "Used two independently-initialized Database instances (separate tmp_path subdirectories) for the differential test rather than two assertions against one database, so neither side could see the other's rows"

patterns-established:
  - "AST-parse a module's own source to assert its import boundary, rather than relying on code review or docstring convention"

requirements-completed: [CHAT-03, CHAT-04]

coverage:
  - id: D1
    description: "AI-proposed recall executes through missions.service.recall_mission, moving the mission to a terminal state"
    requirement: CHAT-03
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_router.py::TestRecall::test_recall_moves_mission_to_terminal_state"
        status: pass
      - kind: unit
        ref: "backend/tests/chat/test_router.py::TestRecall::test_recall_with_no_active_mission_returns_readable_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "AI-proposed roster add/remove executes through roster.service, matching the manual endpoint's call shape"
    requirement: CHAT-04
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_router.py::TestRosterChanges (4 tests: add-new, add-duplicate, remove-tracked, remove-untracked)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Chat-issued roster removal of a drone with an active mission recalls it first and leaves database state identical to the manual DELETE /api/roster/{drone_id} path"
    requirement: CHAT-04
    verification:
      - kind: integration
        ref: "backend/tests/chat/test_router.py::TestRosterServiceParity::test_chat_and_manual_removal_leave_identical_state"
        status: pass
      - kind: integration
        ref: "backend/tests/chat/test_router.py::TestRosterServiceParity::test_chat_removal_recalls_the_active_mission"
        status: pass
    human_judgment: false
  - id: D4
    description: "chat/router.py's import statements name the missions and roster service modules and name neither module's persistence layer; no file under app/chat/ writes to missions, mission_log, budget_snapshots, or fleet_roster"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_router.py::TestImportBoundary (2 tests)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Two launches in one reply execute sequentially, so the second correctly fails once the first exhausts the budget"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_router.py::TestSequentialExecution::test_second_launch_fails_when_first_exhausts_budget"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-13
status: complete
---

# Phase 2 Plan 3: Chat Recall and Roster Actions Summary

**Chat-issued recall and roster add/remove now execute through the identical `missions.service.recall_mission` / `roster.service.add_drone` / `roster.service.remove_drone` functions the manual REST endpoints call, proven by a two-database differential test and an AST-based import-boundary assertion.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-13 (session start)
- **Completed:** 2026-08-13T06:57:22+05:30
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `_execute_mission`'s non-launch arm is now a real recall branch calling `missions_service.recall_mission`, with the recall check ordered before the launch precondition so a recall never runs the zone/distance validation
- New `_execute_roster_change` helper delegates every add/remove to `roster_service.add_drone` / `roster_service.remove_drone`, matching `roster/router.py`'s exact call shape argument-for-argument
- `POST /api/chat`'s roster-change loop now executes sequentially (one await per action against live state) and reports failures alongside mission errors in a single `errors` array, missions first
- A differential test (`TestRosterServiceParity`) runs the same roster removal — a drone with an active mission — through `POST /api/chat` and through `DELETE /api/roster/{drone_id}` against two independently-seeded databases, and asserts identical `fleet_roster` rows, zero `en_route` missions, identical mission status, and identical `remaining_kwh`
- An AST-based structural test (`TestImportBoundary`) parses `chat/router.py`'s own import statements and fails if either domain's persistence module is named, plus a source scan proving no file under `app/chat/` contains write SQL against `missions`, `mission_log`, `budget_snapshots`, or `fleet_roster`

## Task Commits

Each task was committed atomically (Task 1 is `tdd="true"`, so it has a RED and a GREEN commit):

1. **Task 1 RED: failing tests for recall and roster changes** - `cb826da` (test)
2. **Task 1 GREEN: wire recall and roster changes through the service layer** - `9b79248` (feat)
3. **Task 2: differential and import-boundary tests** - `ecdc274` (test)

**Plan metadata:** (final commit recorded after this SUMMARY is written)

## Files Created/Modified
- `backend/app/chat/router.py` - Recall branch in `_execute_mission`; new `_execute_roster_change` helper; POST handler now executes and reports roster changes
- `backend/tests/chat/test_router.py` - `TestRecall`, `TestRosterChanges`, `TestSequentialExecution`, `TestRosterServiceParity`, `TestImportBoundary`; a `_mock_reply` test helper and a `_client_with_roster` helper mounting the roster+missions routers for the manual side of the differential

## Decisions Made
- Verified the differential and import-boundary tests are not vacuous by temporarily reproducing the exact reference-branch defect (`git show 2ba52a8:backend/app/chat/router.py` imports `app.roster.repository` directly, skipping the auto-recall-before-remove guard) in a scratch edit, confirming both new tests fail against it, then restoring the correct implementation via `git checkout --` (the file was already committed, so this discarded only the throwaway scratch edit, not real work)
- Built the differential test against two independently-initialized `Database` instances under separate `tmp_path` subdirectories rather than reusing the `db` fixture, so neither side's assertions could accidentally read the other side's rows

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria commands pass verbatim, including the plan's embedded `ast`-based verification script.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The chat write path now covers the full action surface (launch, recall, roster add/remove), all routed through the same service functions the manual REST endpoints use
- The import-boundary and differential tests are regression guards for any future plan that touches `backend/app/chat/router.py` — they will fail immediately if a future change reaches into `roster.repository` or `missions.repository` directly
- No blockers for 02-04 or subsequent frontend integration work

---
*Phase: 02-ai-flight-director-chat*
*Completed: 2026-08-13*

## Self-Check: PASSED
- FOUND: backend/app/chat/router.py
- FOUND: backend/tests/chat/test_router.py
- FOUND: .planning/phases/02-ai-flight-director-chat/02-03-SUMMARY.md
- FOUND commit: cb826da (test)
- FOUND commit: 9b79248 (feat)
- FOUND commit: ecdc274 (test)
