---
phase: 04-docker-packaging-test-suites
plan: 02
subsystem: testing
tags: [pytest, vitest, testing-library, requirements-audit]

requires:
  - phase: 02-chat-integration
    provides: chat/LLM structured-output parsing and validation test suite
  - phase: 03-frontend-buildout
    provides: DetailPanel, FleetHeatmap, EnergyBudgetChart, MissionsTable, DispatchBar, ChatPanel components and their Vitest suites
provides:
  - Confirmed requirement-noun-to-test-function mapping for TEST-01, TEST-02, TEST-03
  - Verified backend suite (300 passed / 6 skipped / 3 deselected) and frontend suite (81 passed / 14 files) at baseline, zero regression
affects: [04-03, 04-04, ship-gate]

actuals:
  tokens: 700
  tasks: 2
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/04-docker-packaging-test-suites/deferred-items.md
  modified: []

key-decisions:
  - "Audited rather than rewrote: both suites already satisfied TEST-01/02/03's literal wording with real, read assertions — zero test files were added or changed, per D-02 and the plan's no-op-if-clean design"
  - "npm ci run to populate node_modules (gitignored, absent in fresh worktree) — restores the existing committed package-lock.json exactly, no new package names, so this is Rule 3 auto-fix rather than the package-install exclusion"
  - "Pre-existing npm run lint failure (ESLint never configured for frontend/, exits 1 non-interactively) logged to deferred-items.md rather than fixed — out of scope per SCOPE BOUNDARY, first found in 03-01 and still unresolved"

patterns-established: []

requirements-completed: [TEST-01, TEST-02, TEST-03]

coverage:
  - id: D1
    description: "TEST-01 — roster service, repository, and router logic each backed by named, read, passing pytest functions"
    requirement: "TEST-01"
    verification:
      - kind: unit
        ref: "backend/tests/roster/test_service.py, test_repository.py, test_router.py — pytest tests/roster -q"
        status: pass
    human_judgment: false
  - id: D2
    description: "TEST-02 — chat structured-output parsing, malformed-response handling, and mission/roster validation in the chat flow each backed by named, read, passing pytest functions"
    requirement: "TEST-02"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_llm.py::TestParseReply::test_valid_completion_parses_typed_actions, test_malformed_completions_raise_llm_error; backend/tests/chat/test_router.py::TestSequentialExecution::test_second_launch_fails_when_first_exhausts_budget, TestChatRosterChanges::test_add_duplicate_drone_returns_readable_error, test_remove_untracked_drone_returns_readable_error"
        status: pass
    human_judgment: false
  - id: D3
    description: "TEST-03 — all six named components (DetailPanel, FleetHeatmap, EnergyBudgetChart, MissionsTable, DispatchBar, ChatPanel) render and assert on real output in passing Vitest files"
    requirement: "TEST-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/{DetailPanel,FleetHeatmap,EnergyBudgetChart,MissionsTable,DispatchBar}.test.tsx, frontend/src/components/chat/ChatPanel.test.tsx — npm test"
        status: pass
    human_judgment: false

duration: 22min
completed: 2026-08-14
status: complete
---

# Phase 04 Plan 02: Test Suite Requirement Audit Summary

**Audited TEST-01/02/03 against the existing pytest and Vitest suites — every requirement noun already had a real, read assertion behind it, so zero test files were added or modified.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-08-14T00:42:00Z
- **Completed:** 2026-08-14T01:04:41Z
- **Tasks:** 2
- **Files modified:** 1 (new: `deferred-items.md`)

## Accomplishments

- Re-ran the full backend suite live: **300 passed, 6 skipped, 3 deselected** in 7.73s — exact match to the 04-RESEARCH.md baseline, no regression
- Re-ran the full frontend suite live: **81 passed across 14 files** in 3.83s — exact match to the 04-RESEARCH.md baseline, no regression
- Read every named test function's body (not just its name) for all three requirements and confirmed each asserts the behavior it claims, not merely a status code or "does not throw"
- Produced the requirement-noun-to-test-function-to-file:line mapping below — the plan's real deliverable
- Confirmed the `not live` marker filter held: 3 deselected, `test_live_smoke.py` never reached the network

## Requirement-Noun-to-Test Mapping

### TEST-01 — roster service/repository/router logic

| Noun | Test file | Representative test(s) | Assertion confirmed |
|---|---|---|---|
| roster service | `backend/tests/roster/test_service.py` (17 tests) | `TestRemoveDroneWithActiveMission::test_auto_recalls_active_mission_and_releases_budget`, `TestRemoveDroneMidWindowRace::test_concurrent_manual_recall_variant_preserves_single_recall_log_and_budget` | Add/remove drone, duplicate rejection, telemetry-source-failure survival, active-mission auto-recall with budget/log integrity, and three race-window variants — each asserts real DB state (`mission_log`, `missions.status`, `remaining_kwh`), not just no-exception |
| roster repository | `backend/tests/roster/test_repository.py` (10 tests) | `TestConcurrentDuplicateAdd::test_only_one_row_survives_overlapping_add` | Seeded-fleet listing, add/remove CRUD, duplicate rejection at the DB constraint level, concurrent-add race safety |
| roster router | `backend/tests/roster/test_router.py` (20 tests) | `TestRemoveDroneMidWindowRace::test_scheduler_delivers_mission_inside_check_recall_window_returns_204`, `TestLayering::test_post_and_delete_delegate_to_service` | HTTP status codes, telemetry merge shape, 409/404/422 error paths, layering (router delegates to service, doesn't touch DB directly), operator isolation |

### TEST-02 — chat/LLM structured-output parsing, malformed-response handling, chat-flow validation

| Noun | Test file:line | Test function | Assertion confirmed |
|---|---|---|---|
| structured-output parsing | `backend/tests/chat/test_llm.py:141` | `TestParseReply::test_valid_completion_parses_typed_actions` | Parses a raw JSON completion into typed `MissionAction`/`RosterChange` dataclass instances with correct field values, not just "did not throw" |
| malformed-response handling | `backend/tests/chat/test_llm.py:137` | `TestParseReply::test_malformed_completions_raise_llm_error` | Parametrized over 7 cases (prose, markdown-fenced JSON, JSON array, missing message, invalid action enum, extra top-level field, extra mission-action field) — each raises `LLMError` |
| mission validation in chat flow | `backend/tests/chat/test_router.py:280` | `TestSequentialExecution::test_second_launch_fails_when_first_exhausts_budget` | Chat-initiated launch that exhausts the budget on the first drone causes the second to fail with `insufficient_budget` (same error reason as manual dispatch), confirmed via `/api/fleet` remaining_kwh after the call — the `key_links` pattern this plan named as its verification target |
| roster validation in chat flow | `backend/tests/chat/test_router.py:179, :227` | `TestChatRosterChanges::test_add_duplicate_drone_returns_readable_error`, `test_remove_untracked_drone_returns_readable_error` | Chat-initiated add of an already-tracked drone and removal of an untracked drone both surface `drone_already_tracked`/`unknown_drone` reasons through the same service validation manual dispatch uses |

### TEST-03 — six named frontend components

| Component | Test file | Test count | Assertion style confirmed |
|---|---|---|---|
| detail panel | `frontend/src/components/DetailPanel.test.tsx` | 7 | Renders selected drone's id/battery/altitude/speed readouts, mission zone/distance/cost, three Recharts series, offline fallback, and battery color-band threshold — all via `screen.getByText`/DOM queries on rendered output |
| fleet heatmap | `frontend/src/components/FleetHeatmap.test.tsx` | 8 | Cell count, energy-cost weighting, color-band boundaries (75%/35%/8%, boundary cases at 50%/20%), SVG-only rendering, text-based non-color cue, click-to-select wiring |
| budget chart | `frontend/src/components/EnergyBudgetChart.test.tsx` | 5 | Path rendering from snapshot data, empty-state message, zero-value edge case (no NaN coordinates), unmount-during-fetch safety, non-2xx inline error |
| missions table | `frontend/src/components/MissionsTable.test.tsx` | 7 | Empty state, en_route row fields incl. ETA, delivered/recalled status labels, undefined-ETA em-dash fallback, stable row order, zone-name truncation, row-click selection |
| dispatch bar | `frontend/src/components/DispatchBar.test.tsx` | 8 | Recall DELETE call, optimistic mission upsert + refetch, 404/409/422 error-reason rendering, double-click guard via disabled state, error-clearing on success |
| chat panel | `frontend/src/components/chat/ChatPanel.test.tsx` | 7 | Empty-state welcome copy, send wiring, loading-disabled state, collapse/expand toggle, layout placement, auto-scroll on new turn, inline action-confirmation cards |

**Gap found: none.** Every noun in TEST-01, TEST-02, and TEST-03 already had a real, read assertion behind it. No test file was added, modified, or deleted.

## Task Commits

1. **Task 1: Backend audit — map TEST-01 and TEST-02 nouns to named pytest functions** — no commit (audit-only, zero files changed; verified 300 passed/6 skipped/3 deselected, ruff clean)
2. **Task 2: Frontend audit — map TEST-03's six named components to passing Vitest files** — `82ee9f7` (docs: log pre-existing frontend lint gap found during TEST-03 audit)

_Note: neither task's own `<files>` list (`test_service.py`, `test_router.py`, `DetailPanel.test.tsx`) was touched — the audit confirmed each was already complete. Task 2's commit carries only the deferred-items.md finding, not a source change._

## Files Created/Modified

- `.planning/phases/04-docker-packaging-test-suites/deferred-items.md` - Logs the pre-existing (Phase 3-origin) `npm run lint` / unconfigured-ESLint gap found while verifying Task 2's acceptance criteria; out of scope for this audit plan

## Decisions Made

- No test files added or changed — the audit's own success criterion ("if clean, change nothing and say so") was met, so the mapping table above is the deliverable, not a diff
- Ran `npm ci` in this worktree to install `frontend/node_modules` (absent because it's gitignored in a fresh worktree, not because dependencies are missing from the project) — restores the committed lockfile exactly, so this is a Rule 3 auto-fix, not a new/unverified package install
- Deferred the `npm run lint` failure rather than fixing it: ESLint has never been configured for `frontend/` (no `.eslintrc*`/`eslint.config.*`, no `eslint` devDependency) — this predates this plan (first logged in 03-01's own deferred-items.md) and is unrelated to the six test files this plan audited

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed frontend dependencies via `npm ci` before running the suite**
- **Found during:** Task 2 precondition check
- **Issue:** `frontend/node_modules` did not exist in this fresh git worktree (gitignored, not part of the checkout), so `npm test`/`npm run lint`/`npx tsc` all failed with "vitest not found" / missing-module errors before any auditing could begin
- **Fix:** Ran `npm ci`, which installs exactly what `package-lock.json` (already committed, already trusted) declares — no new package names introduced, so this does not fall under the package-install exclusion in Rule 3
- **Files modified:** none tracked (`node_modules/` is gitignored)
- **Verification:** `npm test` subsequently ran and reported 81 passed / 14 files, matching baseline
- **Committed in:** n/a (gitignored, nothing to commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — dependency install)
**Impact on plan:** Necessary to make the suite runnable at all in this isolated worktree; no scope creep, no source files touched.

## Issues Encountered

- `npm run lint` (`next lint`) prompts interactively for ESLint setup and exits 1 under non-interactive stdin, because ESLint has never been configured for `frontend/`. This is a pre-existing gap (first found and deferred in 03-01), not caused by this plan's audit, and no frontend source files changed in this plan. Logged to `.planning/phases/04-docker-packaging-test-suites/deferred-items.md` per SCOPE BOUNDARY rather than fixed. `npx tsc --noEmit` — the other half of that acceptance line — exits 0 cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TEST-01, TEST-02, TEST-03 are now backed by an explicit, checkable mapping rather than filename resemblance; REQUIREMENTS.md can move all three from Pending to complete
- Both suites remain green at their measured baselines (300 backend / 81 frontend), with zero weakening (no deletions, skips, or marker exclusions added) — `git diff --numstat` over `backend/tests/` and `frontend/src/` is empty
- The unconfigured-ESLint gap remains open and unowned — flagging again for whichever future plan (or a dedicated tooling plan) picks up frontend lint

---
*Phase: 04-docker-packaging-test-suites*
*Completed: 2026-08-14*
