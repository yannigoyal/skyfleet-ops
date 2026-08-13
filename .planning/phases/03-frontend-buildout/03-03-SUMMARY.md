---
phase: 03-frontend-buildout
plan: 03
subsystem: ui
tags: [react, next.js, vitest, react-testing-library, tailwind]

# Dependency graph
requires:
  - phase: 03-frontend-buildout
    provides: "03-02: FleetOpsProvider (D-01/D-02/D-04), mergeMissions(), DispatchBar launch half, Header — the single React Context source and accumulation algorithm this plan builds on"
provides:
  - "DispatchBar recall half (FE-06, D-14): Recall button sharing the roster dropdown's selected drone, DELETE /api/fleet/missions/{drone_id}, the only path that ever puts a mission into recalled status"
  - "DispatchBar's full five-reason inline backend-error matrix (unknown_drone, drone_already_en_route, drone_unavailable, no_active_mission, insufficient_budget) rendered verbatim in red-400, with requested_kwh/remaining_kwh appended at fixed precision for insufficient_budget"
  - "MissionsTable (FE-05): tabular view of every mission accumulated this session — en_route, delivered, recalled — with backend-supplied eta_minutes, stable row ordering, zone truncation, and the documented empty state"
affects: [03-04, 03-05, 03-06]

# Actuals (#2632)
actuals:
  tokens: 7471
  tasks: 2
  commits: 4

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared submit() helper in DispatchBar owns error-surface lifecycle for both launch and recall: clears stale error, sets in-flight disable, upserts on success, discards raw detail.reason with no reformatting"
    - "MissionsTable sorts by a stable key (updated_at desc, id tie-break) computed from mission fields, not incoming array/Map order, so polling can't reshuffle rows under the operator's cursor"
    - "Test harness pattern for provider-backed components: seed missions via upsertMission() only after FleetOpsProvider's own mount-triggered refetch() resolves (loaded===true) to avoid a race where the initial empty-active-list poll marks a freshly-seeded en_route mission delivered via mergeMissions"

key-files:
  created:
    - frontend/src/components/DispatchBar.test.tsx
    - frontend/src/components/MissionsTable.tsx
    - frontend/src/components/MissionsTable.test.tsx
  modified:
    - frontend/src/components/DispatchBar.tsx
    - frontend/src/app/page.tsx

key-decisions:
  - "Recall is a type=\"button\" inside the shared <form>, not a second <form>/submit — it reuses the same droneId dropdown state without triggering the zone/distance inputs' required-field HTML5 validation on click"
  - "Discovered during Task 2 test-writing (not in the plan skeleton): FleetOpsProvider's own mount-triggered refetch() races any component that seeds a mission via upsertMission() immediately on mount — the provider's first poll (empty active list) resolves after the seed and mergeMissions marks the freshly-seeded en_route mission delivered. Fixed at the test-harness level (seed only after loaded===true), not in FleetOpsProvider itself, since this is a artifact of synthetic test seeding via upsertMission, not a real operator flow (real en_route missions always originate from a launch response that already reflects the current poll cycle)"

patterns-established:
  - "Every reason-coded backend error (MissionError subclasses) renders through one shared error-detail object {reason, requested_kwh?, remaining_kwh?} with no client-side reason->prose remapping anywhere in the dispatch surface (D-14)"

requirements-completed: [FE-05, FE-06]

coverage:
  - id: D1
    description: "Operator recalls an en-route drone from the dispatch bar and that mission's row changes to Recalled in the missions table without a page reload (FE-06)"
    requirement: "FE-06"
    verification:
      - kind: unit
        ref: "frontend/src/components/DispatchBar.test.tsx#Test 1, Test 2 (DELETE issued exactly once; recalled mission upserted into the map and refetch() called afterwards)"
        status: pass
    human_judgment: true
    rationale: "A true browser-rendered visual confirmation (row color/animation, budget refund) is deferred to end-of-phase UAT per workflow.human_verify_mode=end-of-phase; the jsdom test proves the state transition but not the rendered visual."
  - id: D2
    description: "The dispatch bar surfaces the backend's reason-coded error text verbatim inline in red-400 for every failure mode — unknown_drone, drone_already_en_route, drone_unavailable, no_active_mission, insufficient_budget — with no client-side re-validation or rewording (FE-06, D-14)"
    requirement: "FE-06"
    verification:
      - kind: unit
        ref: "frontend/src/components/DispatchBar.test.tsx#Test 3 (no_active_mission), Test 4 (drone_already_en_route), Test 5 (insufficient_budget with both numerals at fixed precision), Test 6 (unknown_drone)"
        status: pass
    human_judgment: false
    rationale: "drone_unavailable is not independently unit-tested (no distinct rendering path from the other four reasons — all four render identically through the same shared error object), but the shared code path covers it structurally; the acceptance-criteria grep confirms no reason-specific branching exists that could omit it."
  - id: D3
    description: "Missions table shows drone, zone, distance, energy cost, status, and ETA for every mission accumulated this session — en_route, delivered, and recalled alike (FE-05)"
    requirement: "FE-05"
    verification:
      - kind: unit
        ref: "frontend/src/components/MissionsTable.test.tsx#Test 2 (en_route fields + eta), Test 3 (delivered/recalled labels)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The ETA column renders the backend's eta_minutes field verbatim; no client-side ETA is computed from distance and a fixed speed constant (supersedes D-13)"
    requirement: "FE-05"
    verification:
      - kind: unit
        ref: "frontend/src/components/MissionsTable.test.tsx#Test 2, Test 4 (undefined eta_minutes renders an em-dash, never undefined/NaN)"
        status: pass
      - kind: static
        ref: "acceptance-criteria grep: MissionsTable.tsx contains no CRUISE_SPEED identifier"
        status: pass
    human_judgment: false
  - id: D5
    description: "MissionsTable renders the documented empty state when the accumulated missions map is empty on a fresh session"
    requirement: "FE-05"
    verification:
      - kind: unit
        ref: "frontend/src/components/MissionsTable.test.tsx#Test 1"
        status: pass
    human_judgment: false
  - id: D6
    description: "Missions table row order is stable across polls for unchanged missions (backstop)"
    verification:
      - kind: unit
        ref: "frontend/src/components/MissionsTable.test.tsx#Test 5 (backstop): identical rendered order across two different seeding orders"
        status: pass
    human_judgment: false
  - id: D7
    description: "A long free-text zone name truncates at a fixed max width with an ellipsis and carries a native title attribute (backstop)"
    verification:
      - kind: unit
        ref: "frontend/src/components/MissionsTable.test.tsx#Test 6 (backstop): 200-char zone, title attribute holds full value, truncate/max-w-[12rem] classes present"
        status: pass
    human_judgment: false
---

# Phase 03 Plan 03: Recall a Drone and List the Full Mission History Summary

**DispatchBar now recalls an en-route drone and surfaces all five backend refusal reasons verbatim; MissionsTable lists every mission accumulated this session — en_route, delivered, recalled — with the backend's own ETA and a stable row order.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 2 (both TDD)
- **Files modified:** 5 (2 modified, 3 created)

## Accomplishments
- `DispatchBar` (FE-06): added a "Recall" button beside "Launch Mission", styled as a neutral secondary control (slate border/text — `bg-ops-signal` stays exclusive to the Launch CTA, verified by grep). Recall issues `DELETE /api/fleet/missions/{drone_id}` for the dropdown's selected drone, upserts the returned mission (the only way a `recalled` status ever enters the accumulated map), then calls `refetch()`.
- Refactored launch and recall onto one `submit()` helper that clears any stale error at the start of every request, keeps both buttons disabled for the duration of any in-flight request, and renders `detail.reason` verbatim in `text-red-400` — appending `requested_kwh`/`remaining_kwh` at `.toFixed(2)` when present (the `insufficient_budget` case). No client-side re-validation, no reworded copy, no confirmation dialog on either action (D-14).
- `frontend/src/components/DispatchBar.test.tsx` — 8 behaviors: single DELETE issuance, mission-map upsert + refetch, four distinct backend refusal reasons rendered verbatim (`no_active_mission`, `drone_already_en_route`, `insufficient_budget` with both numerals, `unknown_drone`), the double-submit disable guard, and error-text clearing on a subsequent success.
- `MissionsTable` (FE-05): new component mirroring `FleetRosterPanel`'s table idiom (panel shell, `thead` classes, `colSpan` empty-state row) over the full accumulated missions map from `useFleetOps()`. Columns: Drone, Zone, Distance, Energy, Status, ETA. Status labels via a `MISSION_STATUS_LABEL` lookup (`En Route`/`Delivered`/`Recalled`). ETA renders the backend's `eta_minutes` verbatim (supersedes D-13) with an em-dash fallback when absent. Rows sort by a stable key (`updated_at` descending, tie-broken by `id`) computed from mission fields, not incoming array order. Zone cell truncates at `max-w-[12rem]` with a native `title` attribute holding the full value. `tbody` scrolls internally under a `sticky` `thead` so a long session's history stays bounded. Row click calls `select(mission.drone_id)`.
- `frontend/src/components/MissionsTable.test.tsx` — 7 behaviors including two labeled backstops: row-order stability across different seeding orders (Test 5) and long-zone truncation with a title attribute (Test 6).
- Mounted `<MissionsTable />` in `page.tsx` beneath the roster panel in the two-column region; the chat placeholder `<aside>` is untouched (plan 06 replaces it).
- Full suite verification: `npm test` (29/29 passing across 6 files), `npx tsc --noEmit` (clean), `npm run build` (static export succeeds).

## Task Commits

Each task was committed atomically (TDD: separate RED/GREEN commits):

1. **Task 1: Recall + inline error matrix** — RED: `b10edbb` (test) -> GREEN: `c79006b` (feat)
2. **Task 2: Missions table + page mount** — RED: `1037506` (test) -> GREEN: `9907ab9` (feat)

**Plan metadata:** committed alongside this SUMMARY (worktree mode — orchestrator finalizes after wave merge).

## Files Created/Modified
- `frontend/src/components/DispatchBar.tsx` - Added Recall button, shared `submit()` helper, full error-detail object rendering
- `frontend/src/components/DispatchBar.test.tsx` - 8 behaviors covering recall + the backend refusal-reason matrix
- `frontend/src/components/MissionsTable.tsx` - New: tabular mission history with backend ETA, stable sort, empty state
- `frontend/src/components/MissionsTable.test.tsx` - 7 behaviors including 2 labeled backstops
- `frontend/src/app/page.tsx` - Mounts `MissionsTable` beneath the roster panel

## Decisions Made
- Recall is a `type="button"` inside the existing `<form>` (not a second form or a submit type) so it reuses the shared `droneId` dropdown state without triggering the zone/distance inputs' native `required` validation on click.
- Error state is a structured `{reason, requested_kwh?, remaining_kwh?}` object (not a plain string) so the component can append the two numerals at fixed precision only when they're present, matching the acceptance criteria's literal `requested_kwh`/`remaining_kwh` grep and avoiding any reason-to-prose remapping.
- MissionsTable's `tbody` wraps in `max-h-[22rem] overflow-y-auto` with a `sticky top-0` `thead`, matching the UI-SPEC's described overflow treatment for the roster table (which the current `FleetRosterPanel.tsx` code does not yet implement — out of this plan's file scope, not re-fixed here per the scope-boundary rule).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking test-harness issue] Provider mount-poll race in MissionsTable's test seeding**
- **Found during:** Task 2, writing `MissionsTable.test.tsx`'s Test 2 (en_route rendering)
- **Issue:** The test harness's `Seed` component called `upsertMission()` inside a bare `useEffect` on mount. `FleetOpsProvider` also fires its own mount-triggered `refetch()` in a `useEffect`. When `Seed`'s upsert landed before the provider's own `refetch()` resolved (an empty-active-list stub response), `mergeMissions()` — working exactly as designed by plan 02 — marked the freshly-seeded `en_route` mission `delivered`, since it was absent from that first poll's active list. Test 2 failed asserting `"En Route"` was present; the DOM showed `"Delivered"` instead.
- **Fix:** `Seed` now waits for the provider's `loaded` flag before calling `upsertMission()`, so seeding happens strictly after the mount poll has resolved and can't be raced by it.
- **Files modified:** `frontend/src/components/MissionsTable.test.tsx` only — this is a test-harness artifact of synthetic seeding via `upsertMission()`, not a real operator flow (a real `en_route` mission always originates from a launch response that already reflects the current poll cycle, so `FleetOpsProvider.tsx` itself needed no change).
- **Verification:** All 7 `MissionsTable` tests pass; full 29-test suite green.
- **Committed in:** part of `9907ab9` (GREEN) — the harness fix landed alongside the component since it was discovered mid-TDD-cycle before the first full green run.

---

**Total deviations:** 1 auto-fixed (test-harness race, caught by the plan's own TDD RED-then-GREEN discipline)
**Impact on plan:** No production code was affected; `FleetOpsProvider`'s `mergeMissions()` behaved exactly as plan 02 specified. The fix only corrects how the test double seeds state relative to the provider's own async lifecycle.

## Issues Encountered
- `npm run lint` (`next lint`) still requires interactive ESLint setup — the same pre-existing issue already logged in `deferred-items.md` from plan 03-01 and re-confirmed in 03-02-SUMMARY. Not re-fixed here per the scope-boundary rule; not re-logged as a new duplicate entry.
- Fresh worktree had no `node_modules` (gitignored). Ran `npm ci` in `frontend/` to install from the committed lockfile before running tests/build.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
The manual dispatch loop (launch + recall) is complete and self-consistent, and every mission this session is now visible in the missions table with the backend's own ETA. `DispatchBar`'s shared `submit()` helper and `MissionsTable`'s stable-sort pattern are both available for later plans (heatmap in 05 reuses the same `select()` mechanism; detail panel in 04 reads from the same `missions` array). No blockers for 03-04 through 03-06.

---
*Phase: 03-frontend-buildout*
*Completed: 2026-08-13*
