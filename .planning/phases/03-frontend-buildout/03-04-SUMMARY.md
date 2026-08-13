---
phase: 03-frontend-buildout
plan: 04
subsystem: ui
tags: [react, next.js, recharts, vitest, react-testing-library]

# Dependency graph
requires:
  - phase: 03-frontend-buildout
    provides: "03-03: DispatchBar recall half, MissionsTable, FleetOpsProvider's accumulated missions array and select() mechanism — the state surface DetailPanel reads its current-mission filter and selection from"
provides:
  - "useTelemetryStream widened with altitudeHistory/speedHistory parallel maps (D-03), sharing one 120-point cap across all three series; existing history key's Record<string, number[]> battery shape unchanged"
  - "DroneSparkline (FE-01): fixed-size axis-free Recharts LineChart column in every roster row, handling empty (blank placeholder) and flat (padded Y domain) input explicitly"
  - "DetailPanel (FE-02, D-16): selected-drone battery/altitude/speed-over-time charts plus current en_route mission, with the 'No active mission' and 'Drone offline or removed from roster' documented empty/partial states"
  - "batteryColor() exported from FleetRosterPanel so DetailPanel reuses the same three-band thresholds instead of duplicating them"
  - "ResizeObserver stub in vitest.setup.ts — a shared test-infra fix any future Recharts component test needs"
affects: [03-05, 03-06]

# Actuals (#2632)
actuals:
  tokens: 8608
  tasks: 3
  commits: 6

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "All three telemetry series in useTelemetryStream (battery, altitude, speed) share one push-then-shift cap block against the same maxHistoryPoints knob, keeping the bounded-history guarantee (D-03) trivially auditable via a single grep for the comparison"
    - "DroneSparkline/DetailPanel charts pass fixed numeric width/height to Recharts' ResponsiveContainer (not percentage sizing) so jsdom tests don't need a real layout pass — requires a ResizeObserver stub since Recharts still wires one up even with fixed dimensions"
    - "A flat (all-identical-value) series gets an explicit padded Y-axis domain ([value-1, value+1]) rather than trusting Recharts' auto-domain, which would otherwise collapse a zero-range series to an invisible line"
    - "DetailPanel receives snapshot + three history maps as props from page.tsx's single useTelemetryStream() call rather than calling the hook itself, avoiding a second EventSource connection"

key-files:
  created:
    - frontend/src/lib/useTelemetryStream.test.ts
    - frontend/src/components/DroneSparkline.tsx
    - frontend/src/components/DroneSparkline.test.tsx
    - frontend/src/components/DetailPanel.tsx
    - frontend/src/components/DetailPanel.test.tsx
  modified:
    - frontend/src/lib/useTelemetryStream.ts
    - frontend/src/components/FleetRosterPanel.tsx
    - frontend/src/app/page.tsx
    - frontend/vitest.setup.ts

key-decisions:
  - "Exported batteryColor() from FleetRosterPanel.tsx (previously module-private) instead of duplicating the three-band thresholds in DetailPanel — the plan explicitly called for reuse, and duplicating risks the two readouts silently drifting apart if the thresholds ever change"
  - "DetailPanel's three telemetry charts are a new local TelemetryChart helper (not a reuse of DroneSparkline) — DroneSparkline is fixed at a tiny 80x24 roster-cell size with no label, while the detail panel needs larger (280x60) labelled charts; both follow the identical Recharts idiom (ResponsiveContainer + LineChart + Line, isAnimationActive={false}) so the visual language matches without forcing an ill-fitting shared component"
  - "Current-mission fields (zone, distance, energy) render in three separate grid cells, not concatenated into one text block — mirrors MissionsTable's one-field-per-cell pattern so each field is independently findable by testing-library's exact-text matcher without ambiguity"

patterns-established:
  - "Any future Recharts-based component test can rely on the shared ResizeObserver stub in vitest.setup.ts rather than each test file needing its own polyfill"

requirements-completed: [FE-01, FE-02]

coverage:
  - id: D1
    description: "Every roster row shows a battery sparkline built from the per-drone history useTelemetryStream has accumulated since page load (FE-01)"
    requirement: "FE-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/DroneSparkline.test.tsx#Test 5 (FleetRosterPanel renders one ResponsiveContainer per drone row)"
        status: pass
    human_judgment: true
    rationale: "Live-updating visual confirmation across the 500ms SSE cadence is deferred to end-of-phase UAT per workflow.human_verify_mode=end-of-phase; the jsdom test proves one sparkline mounts per row and reads the correct history array, not the live-extending visual."
  - id: D2
    description: "DroneSparkline renders a visible flat line (not a crash or blank gap) when consecutive battery_pct history values are equal"
    requirement: "FE-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/DroneSparkline.test.tsx#Test 4"
        status: pass
    human_judgment: false
  - id: D3
    description: "DroneSparkline renders without throwing when history has 0 or 1 points"
    requirement: "FE-01"
    verification:
      - kind: unit
        ref: "frontend/src/components/DroneSparkline.test.tsx#Test 2 (empty), Test 3 (single point)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Clicking a drone in the roster opens a detail panel showing that drone's battery, altitude, and speed over time plus its current mission (FE-02)"
    requirement: "FE-02"
    verification:
      - kind: unit
        ref: "frontend/src/components/DetailPanel.test.tsx#Test 2 (id, readouts, and 3 chart series for a selected+present drone)"
        status: pass
    human_judgment: true
    rationale: "The click-to-select wiring itself (roster row onClick -> FleetOpsProvider.select -> DetailPanel re-render) was already established by D-04/FleetOpsProvider in plan 02; this plan's test seeds selection directly and asserts the panel's render output, not the click event itself, which is exercised via the roster row's existing onSelect prop unchanged in this plan."
  - id: D5
    description: "The detail panel shows the plain message 'No active mission' when the selected drone has no active mission, and the battery/altitude/speed charts still render normally beneath it (D-16)"
    requirement: "FE-02"
    verification:
      - kind: unit
        ref: "frontend/src/components/DetailPanel.test.tsx#Test 3 (D-16), Test 5 (delivered/recalled excluded from current)"
        status: pass
    human_judgment: false
  - id: D6
    description: "useTelemetryStream caps every per-drone history series — battery, altitude, and speed — at maxHistoryPoints, default 120 (D-03)"
    requirement: "FE-02"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useTelemetryStream.test.ts#Test 2 (all three series capped identically at maxHistoryPoints=2)"
        status: pass
      - kind: static
        ref: "acceptance-criteria grep: exactly 3 occurrences of '> maxHistoryPoints' in useTelemetryStream.ts — one per series"
        status: pass
    human_judgment: false
  - id: D7
    description: "The existing history return key keeps its Record<string, number[]> battery shape; altitude and speed are added as parallel maps"
    requirement: "FE-02"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useTelemetryStream.test.ts#Test 4"
        status: pass
    human_judgment: false
  - id: D8
    description: "The roster table body scrolls internally past 8 visible rows with the header row staying pinned"
    verification:
      - kind: static
        ref: "acceptance-criteria grep: FleetRosterPanel.tsx contains overflow-y-auto and a sticky thead"
        status: pass
    human_judgment: false
  - id: D9
    description: "The per-drone history array preserves chronological SSE-arrival order as points are appended (backstop)"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useTelemetryStream.test.ts#Test 3 (backstop): strictly increasing readings stay in order"
        status: pass
    human_judgment: false
  - id: D10
    description: "When the selected drone drops out of the live SSE snapshot, the detail panel shows 'Drone offline or removed from roster' instead of freezing on stale values (backstop)"
    verification:
      - kind: unit
        ref: "frontend/src/components/DetailPanel.test.tsx#Test 6 (backstop)"
        status: pass
    human_judgment: false
---

# Phase 03 Plan 04: Battery Sparklines and the Drone Detail Panel Summary

**Every roster row now carries a live battery trend line, and clicking a drone opens a detail panel showing its battery/altitude/speed over time plus its current mission — both fed by a `useTelemetryStream` widened with capped, parallel altitude and speed history maps.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3 (all TDD)
- **Files modified:** 9 (4 modified, 5 created)

## Accomplishments

- `useTelemetryStream` (D-03): extended in place with `altitudeHistory` and `speedHistory` `useRef` maps beside the existing battery `history` ref. All three series share one push-then-shift cap against `maxHistoryPoints` (default 120) inside the same `onmessage` handler — exactly three cap comparisons exist in the file, one per series, so a future series can't be added without inheriting the bound. The existing `history` key's `Record<string, number[]>` battery shape is unchanged; the returned object widened to `{snapshot, status, history, altitudeHistory, speedHistory}`.
- `frontend/src/lib/useTelemetryStream.test.ts` — 5 behaviors: 3-series accumulation from one message, shared cap enforcement across all three series, a labeled chronological-order backstop, the unchanged `history` contract, and EventSource cleanup on unmount. Driven by a controllable fake `EventSource` that records handlers and exposes `emit()`/`closed`.
- `DroneSparkline` (FE-01): new pure-props component (`ConnectionDot.tsx` template — no local state) rendering a fixed 80x24 Recharts `LineChart` with no axes/grid/tooltip, `isAnimationActive={false}`. Empty input renders a same-size blank placeholder instead of crashing; an all-identical-value input gets an explicit padded Y-axis domain so a flat battery still draws as a visible horizontal line rather than collapsing.
- `FleetRosterPanel.tsx`: gained a `history` prop, a "Battery Trend" column feeding `DroneSparkline`, and the empty-state `colSpan` bumped 5->6. The `tbody` now scrolls internally past ~8 rows under a `sticky` `thead` (matching `MissionsTable`'s existing overflow treatment) so a chat-grown fleet can't push the roster off screen. `batteryColor()` is now exported for `DetailPanel` to reuse.
- `frontend/src/components/DroneSparkline.test.tsx` — 5 behaviors: varying-value path render, empty-array blank cell (no path, no throw), single-point no-throw, flat-series visible line, and a `FleetRosterPanel` integration assertion (one sparkline per row, `colSpan={6}` empty state).
- `DetailPanel` (FE-02, D-16): new component reading `selectedDroneId`/`missions` from `useFleetOps()` and receiving the telemetry snapshot plus three history maps as props from `page.tsx` (avoiding a second `EventSource`). Renders, in priority order: a neutral "Select a drone…" prompt when nothing is selected; the exact "Drone offline or removed from roster" message when the selection has dropped out of the live snapshot; otherwise the drone id, three-band-colored battery readout plus altitude/speed readouts (`.toFixed(n)` matching `FleetRosterPanel`'s precedent), three labelled 280x60 telemetry charts (battery/altitude/speed), and a current-mission block that filters the accumulated missions array to `drone_id` match AND `status === "en_route"` — a delivered or recalled mission never counts as current, and telemetry charts render regardless of mission presence.
- `frontend/src/components/DetailPanel.test.tsx` — 7 behaviors including one labeled backstop (Test 6: selected drone absent from snapshot shows the offline message, not stale values).
- Mounted `<DetailPanel />` in `page.tsx`'s main grid, between the roster and missions table; the chat placeholder `<aside>` is untouched (plan 06 replaces it).
- Full suite verification: `npm test` (46/46 passing across 9 files), `npx tsc --noEmit` (clean), `npm run build` (static export succeeds).

## Task Commits

Each task was committed atomically (TDD: separate RED/GREEN commits):

1. **Task 1: Widen useTelemetryStream** — RED: `36e0477` (test) -> GREEN: `b7955cb` (feat)
2. **Task 2: Battery sparkline + roster row** — RED: `5d9264f` (test) -> GREEN: `dccae17` (feat)
3. **Task 3: Drone detail panel** — RED: `83e2bb6` (test) -> GREEN: `2dc1713` (feat)

**Plan metadata:** committed alongside this SUMMARY (worktree mode — orchestrator finalizes after wave merge).

## Files Created/Modified

- `frontend/src/lib/useTelemetryStream.ts` - Widened with capped `altitudeHistory`/`speedHistory` parallel maps
- `frontend/src/lib/useTelemetryStream.test.ts` - New: 5 behaviors covering the widened hook
- `frontend/src/components/DroneSparkline.tsx` - New: fixed-size axis-free per-drone battery trend line
- `frontend/src/components/DroneSparkline.test.tsx` - New: 5 behaviors incl. FleetRosterPanel integration
- `frontend/src/components/FleetRosterPanel.tsx` - Added Battery Trend column, internal scroll, exported `batteryColor()`
- `frontend/src/components/DetailPanel.tsx` - New: selected-drone telemetry-over-time + current mission
- `frontend/src/components/DetailPanel.test.tsx` - New: 7 behaviors incl. offline-drone backstop
- `frontend/src/app/page.tsx` - Mounts `DetailPanel`, threads all three history maps
- `frontend/vitest.setup.ts` - Added shared `ResizeObserver` stub for Recharts component tests

## Decisions Made

- `batteryColor()` exported from `FleetRosterPanel.tsx` rather than duplicated in `DetailPanel.tsx` — the plan explicitly called for reuse of the same three-band thresholds; duplicating risks silent drift if the bands ever change.
- `DetailPanel`'s three telemetry charts are a new local `TelemetryChart` helper, not a reuse of `DroneSparkline` — the two have different fixed sizes (80x24 roster cell vs. 280x60 labelled detail chart) but share the identical Recharts idiom (`ResponsiveContainer` + `LineChart` + `Line`, `isAnimationActive={false}`).
- Current-mission fields (zone, distance, energy) render in three separate grid cells rather than one concatenated text block, mirroring `MissionsTable`'s one-field-per-cell pattern so each field is unambiguously findable by an exact-text test query.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking test infra] jsdom has no ResizeObserver, which Recharts' ResponsiveContainer requires**
- **Found during:** Task 2, first render of `DroneSparkline` under vitest
- **Issue:** `ReferenceError: ResizeObserver is not defined` — Recharts' `ResponsiveContainer` wires up a `ResizeObserver` even when given fixed numeric `width`/`height` props (to react to future container resizes), and jsdom ships no implementation.
- **Fix:** Added a minimal `ResizeObserverStub` (no-op `observe`/`unobserve`/`disconnect`) to `frontend/vitest.setup.ts`, guarded so it only installs if `ResizeObserver` isn't already defined.
- **Files modified:** `frontend/vitest.setup.ts` only.
- **Verification:** All `DroneSparkline` and `DetailPanel` tests pass; full 46-test suite green.
- **Committed in:** part of `dccae17` (Task 2 GREEN) — discovered mid-TDD-cycle before the first full green run, same pattern as 03-03's test-harness fix.

---

**Total deviations:** 1 auto-fixed (shared test-infra gap, caught by the plan's own TDD RED-then-GREEN discipline)
**Impact on plan:** No production code was affected; this is a one-time test-environment fix that also benefits any future Recharts component test in this codebase (the upcoming `FleetHeatmap`/`EnergyBudgetChart` in plan 05).

## Issues Encountered

- `npm run lint` (`next lint`) still requires interactive ESLint setup — the same pre-existing issue logged in `deferred-items.md` from plan 03-01 and re-confirmed in 03-02/03-03 summaries. Not re-fixed here per the scope-boundary rule; not re-logged as a new duplicate entry.
- Fresh worktree had no `node_modules` (gitignored). Ran `npm ci` in `frontend/` to install from the committed lockfile before running tests/build.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

FE-01 and FE-02 are complete: every roster row shows a live battery trend, and the detail panel gives per-drone depth on battery/altitude/speed plus current mission, sharing the same `selectedDroneId` state (`FleetOpsProvider`) that plan 05's heatmap will also drive via cell clicks. The widened `useTelemetryStream` return shape (`altitudeHistory`/`speedHistory`) is available for any future consumer without further hook changes. No blockers for 03-05 or 03-06.

---
*Phase: 03-frontend-buildout*
*Completed: 2026-08-13*

## Self-Check: PASSED

All nine key files verified present on disk (`frontend/src/lib/useTelemetryStream.ts`,
`frontend/src/lib/useTelemetryStream.test.ts`, `frontend/src/components/DroneSparkline.tsx`,
`frontend/src/components/DroneSparkline.test.tsx`, `frontend/src/components/FleetRosterPanel.tsx`,
`frontend/src/components/DetailPanel.tsx`, `frontend/src/components/DetailPanel.test.tsx`,
`frontend/src/app/page.tsx`, `frontend/vitest.setup.ts`) plus this SUMMARY.md. All six commits
(`36e0477`, `b7955cb`, `5d9264f`, `dccae17`, `83e2bb6`, `2dc1713`) verified present in `git log`.
