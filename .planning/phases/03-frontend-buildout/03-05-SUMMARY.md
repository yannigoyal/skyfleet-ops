---
phase: 03-frontend-buildout
plan: 05
subsystem: ui
tags: [react, next.js, recharts, vitest, react-testing-library]
status: complete

# Dependency graph
requires:
  - phase: 03-frontend-buildout
    provides: "03-04: FleetOpsProvider's missions array and select() mechanism, batteryColor() three-band thresholds, the DroneSparkline/DetailPanel Recharts idiom, and the shared ResizeObserver stub in vitest.setup.ts"
provides:
  - "FleetHeatmap (FE-03, D-09/D-10/D-11/D-12): Recharts Treemap, one SVG-only cell per drone in the live telemetry snapshot, sized by active-mission energy_cost_kwh (floored at IDLE_HEATMAP_WEIGHT_KWH for idle drones), coloured by the same at-or-below three-band battery thresholds as batteryColor(), labelled with drone id + battery percentage as the non-colour criticality cue, click-to-select wired to FleetOpsProvider.select()"
  - "EnergyBudgetChart (FE-04): client-component Recharts LineChart of remaining_kwh over recorded_at from GET /api/fleet/history, polling independently of FleetOpsProvider, with an empty state, an inline error state, and an unmount-guarded fetch"
affects: []

# Actuals (#2632)
actuals:
  tokens: 5800
  tasks: 2
  commits: 5

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recharts' Treemap invokes the custom `content` render prop once for a synthetic root/container node (depth 0, no data fields) in addition to each leaf cell — any custom cell content component must guard on a data-only field (e.g. `typeof batteryPct !== \"number\"`) and return null for that invocation, or it will crash reading undefined properties on first render"
    - "A component whose GET endpoint serves only that one component polls independently with its own local interval constant (documented as matching FleetOpsProvider's cadence) rather than being routed through FleetOpsProvider, keeping the shared context from growing a concern only one consumer needs"
    - "Block comments that describe Tailwind utility-class prefixes (e.g. `bg-*`) must avoid the literal substring `*/` inside prose, since esbuild treats it as the comment terminator regardless of intent — write out \"background/text utilities\" instead of `bg-*/text-*`"

key-files:
  created:
    - frontend/src/components/FleetHeatmap.tsx
    - frontend/src/components/FleetHeatmap.test.tsx
    - frontend/src/components/EnergyBudgetChart.tsx
    - frontend/src/components/EnergyBudgetChart.test.tsx
  modified:
    - frontend/src/app/page.tsx

key-decisions:
  - "CellContent guards on `typeof batteryPct !== \"number\"` and returns null — Recharts' Treemap render pipeline calls the custom content component for the whole-canvas root/container node (depth 0) as well as each leaf, and that synthetic node carries none of HeatmapDatum's fields; without the guard the root invocation crashes with 'Cannot read properties of undefined (reading toFixed)' on every render"
  - "EnergyBudgetChart uses a local HISTORY_POLL_INTERVAL_MS constant (5000, matching FleetOpsProvider's FLEET_POLL_INTERVAL_MS) instead of importing the provider's private constant — the plan's files_modified list excludes FleetOpsProvider.tsx, and exporting a symbol from it to serve one external consumer would be a wider change than the plan scoped"
  - "XAxis uses interval={0} (render every tick) rather than Recharts' default overlap-avoidance interval — deterministic tick count under jsdom's lack of real text measurement, and matches the plan's explicit 'axis reflects three data points' behavior for a small-N series"

patterns-established:
  - "Any future custom Treemap content component in this codebase should reuse the depth-0 guard pattern from FleetHeatmap's CellContent rather than rediscovering the root-node crash"

requirements-completed: [FE-03, FE-04]

coverage:
  - id: D1
    description: "Fleet heatmap renders one rectangle per drone in the live snapshot, sized by that drone's active-mission energy_cost_kwh and coloured by its live battery health (FE-03)"
    requirement: "FE-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 2 (mission-energy weighting vs. idle floor), Test 3 (three-band colour mapping)"
        status: pass
    human_judgment: true
    rationale: "Live-updating visual confirmation of cell growth on mission launch is deferred to end-of-phase UAT per workflow.human_verify_mode=end-of-phase; the jsdom tests prove the weighting and colour logic, not the real-time visual."
  - id: D2
    description: "Idle drones with no active mission appear in the heatmap at a fixed minimum weight, so the fleet is never visually empty on a fresh start with 500 kWh and zero active missions (D-10)"
    requirement: "FE-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 1 (D-10, ten drones/zero missions still render ten cells)"
        status: pass
      - kind: static
        ref: "acceptance-criteria grep: FleetHeatmap.tsx contains IDLE_HEATMAP_WEIGHT_KWH and the value 0.1"
        status: pass
    human_judgment: false
  - id: D3
    description: "Heatmap cell colours use the three-band battery mapping corrected against batteryColor()'s at-or-below thresholds: emerald-400 at 50% and above, ops.amber from 20% up to 50%, red-400 below 20% (D-11)"
    requirement: "FE-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 3 (75/35/8%), Test 4 (boundary: exactly 50% amber, exactly 20% red)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Clicking a heatmap cell selects that drone and opens the same detail panel a roster row click opens (D-12)"
    requirement: "FE-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 7 (D-12): click calls FleetOpsProvider.select with the cell's drone id"
        status: pass
    human_judgment: false
  - id: D5
    description: "The heatmap is built with the Recharts Treemap component, sharing the charting library with the budget chart (D-09)"
    requirement: "FE-03"
    verification:
      - kind: static
        ref: "acceptance-criteria grep: FleetHeatmap.tsx imports Treemap from recharts"
        status: pass
    human_judgment: false
  - id: D6
    description: "Heatmap cell content is composed of SVG primitives only; no HTML element is rendered inside the chart's SVG tree"
    requirement: "FE-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 5 (SVG-only, Pitfall 3): svg subtree has zero div, zero foreignObject"
        status: pass
      - kind: static
        ref: "acceptance-criteria grep: FleetHeatmap.tsx has no className=\"bg- occurrence in the cell renderer region"
        status: pass
    human_judgment: false
  - id: D7
    description: "The heatmap layout renders correctly at zero, one, and many active missions"
    requirement: "FE-03"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 8 (zero-one-many): renders without throwing at 0/1/20 drones"
        status: pass
    human_judgment: false
  - id: D8
    description: "MUST NOT convey battery criticality by colour alone — battery percentage renders as text in or adjacent to every legible cell (prohibition, flagged)"
    verification:
      - kind: unit
        ref: "frontend/src/components/FleetHeatmap.test.tsx#Test 6 (prohibition, non-colour cue): legible cells render both drone id and battery percentage as SVG text"
        status: pass
    human_judgment: true
    rationale: "The plan flags this prohibition's verification as judgment-tier; the automated test proves the text nodes render for legible cells, but confirming the contrast/legibility reads correctly to an actual colour-blind viewer is deferred to end-of-phase UAT."
  - id: D9
    description: "Energy-budget line chart plots remaining_kwh against recorded_at from GET /api/fleet/history (FE-04)"
    requirement: "FE-04"
    verification:
      - kind: unit
        ref: "frontend/src/components/EnergyBudgetChart.test.tsx#Test 1 (three snapshots render a path and three axis ticks), Test 3 (remaining_kwh=0 renders without NaN coordinates)"
        status: pass
    human_judgment: true
    rationale: "Live 30-second-cadence updates against the real backend scheduler are deferred to end-of-phase UAT; the jsdom test proves the fetch/render/format pipeline against a mocked response, not the live streaming behavior."
  - id: D10
    description: "EnergyBudgetChart's fetch to GET /api/fleet/history does not update state or warn after the component unmounts mid-request (backstop)"
    verification:
      - kind: unit
        ref: "frontend/src/components/EnergyBudgetChart.test.tsx#Test 4 (backstop, concurrency): unmount before fetch resolves, no console.error"
        status: pass
    human_judgment: false
  - id: D11
    description: "An empty snapshots array and a non-2xx history response each render a documented state (empty-state message / inline error) instead of a broken or blank chart, and never throw out of render"
    requirement: "FE-04"
    verification:
      - kind: unit
        ref: "frontend/src/components/EnergyBudgetChart.test.tsx#Test 2 (empty state), Test 5 (non-2xx inline error)"
        status: pass
    human_judgment: false
---

# Phase 03 Plan 05: Fleet Heatmap and Energy-Budget Chart Summary

**A Recharts Treemap gives the operator fleet-wide situational awareness at a glance — one cell per drone, sized by active-mission energy cost and coloured by battery health, floored so the fleet is never blank at zero missions — beside a line chart of remaining energy budget over time from the backend's own snapshot history.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 (both TDD)
- **Files modified:** 5 (1 modified, 4 created)

## Accomplishments

- `FleetHeatmap` (FE-03, D-09/D-10/D-11/D-12): a Recharts `Treemap` with a custom SVG-only `content` renderer. One `HeatmapDatum` per drone in the live telemetry snapshot: `value` is the drone's active `en_route` mission's `energy_cost_kwh`, floored at the module constant `IDLE_HEATMAP_WEIGHT_KWH` (0.1) for any drone without one — D-10's guarantee that a fresh start with 500 kWh and zero missions still shows all ten drones as visible cells rather than a blank panel. `batteryFill(pct)` reproduces `batteryColor()`'s exact at-or-below thresholds (`<=20` red-400, `<=50` ops.amber, else emerald-400) as hex fills, so the roster and the heatmap can never disagree about the same drone's colour band. `CellContent` renders `g`/`rect`/`text` primitives only, guarded to omit labels only when a cell is genuinely too small (`width > 40 && height > 28`); the battery percentage renders as its own SVG text node alongside the drone id, satisfying the plan's colour-blind-dispatcher prohibition. Clicking a cell calls `select(node.name)` against the same `FleetOpsProvider` state the roster row and detail panel already share (D-12).
- `frontend/src/components/FleetHeatmap.test.tsx` — 8 behaviors: idle-weight floor at zero missions, mission-energy weighting vs. the idle floor, three-band colour mapping at 75/35/8%, the exact-boundary case at 50%/20%, SVG-only content (zero `div`/`foreignObject` in the `svg` subtree), the non-colour battery-percentage text cue, click-to-select, and render-without-throwing at 0/1/20 drones.
- `EnergyBudgetChart` (FE-04): a `"use client"` component fetching `GET /api/fleet/history` in a `useEffect`, independent of `FleetOpsProvider` (this endpoint serves only this component). Polls on a local `HISTORY_POLL_INTERVAL_MS` (5000ms, matching the provider's cadence by value, not by import — see Decisions). Renders a Recharts `LineChart` with a teal (`#17a2b8`) stroke line, time-of-day-formatted x-axis ticks, `.toFixed(1)` kWh y-axis/tooltip formatting, an empty-state message when `snapshots` is an empty array, and an inline `text-red-400` error when the fetch returns non-2xx or throws — the chart never throws out of render. The fetching effect's cleanup sets a `cancelled` flag and calls `AbortController.abort()`, so a request that settles after unmount never calls `setState`.
- `frontend/src/components/EnergyBudgetChart.test.tsx` — 5 behaviors: three-snapshot render with a matching axis tick count, empty-state message, `remaining_kwh=0` rendering without `NaN` path coordinates, the unmount-during-fetch concurrency backstop (asserted via a `console.error` spy), and a non-2xx response producing an inline error instead of a thrown exception.
- Mounted `<FleetHeatmap snapshot={snapshot} />` and `<EnergyBudgetChart />` in `page.tsx`'s main grid, after the detail panel and before the missions table; the chat placeholder `<aside>` is untouched (plan 06 replaces it).
- Full suite verification: `npm test` (59/59 passing across 11 files, including the existing `page.tsx` integration test), `npx tsc --noEmit` (clean), `npm run build` (static export succeeds).

## Task Commits

Each task was committed atomically (TDD: separate RED/GREEN commits):

1. **Task 1: Fleet heatmap** — RED: `425d1f2` (test) -> fix: `62c26a1` (test race-condition fix, found during Task 2's full-suite run) -> GREEN: `b58851b` (feat)
2. **Task 2: Energy-budget line chart** — RED: `8cdab13` (test) -> GREEN: `a7d3a28` (feat)

**Plan metadata:** committed alongside this SUMMARY (worktree mode — orchestrator finalizes after wave merge).

## Files Created/Modified

- `frontend/src/components/FleetHeatmap.tsx` - New: Recharts Treemap, mission-energy weighted, battery-coloured, SVG-only, click-to-select
- `frontend/src/components/FleetHeatmap.test.tsx` - New: 8 behaviors covering D-10/D-11/D-12 and the colour-only prohibition
- `frontend/src/components/EnergyBudgetChart.tsx` - New: independent-polling remaining-kWh line chart with empty/error states and an unmount guard
- `frontend/src/components/EnergyBudgetChart.test.tsx` - New: 5 behaviors including the unmount backstop
- `frontend/src/app/page.tsx` - Mounts `FleetHeatmap` and `EnergyBudgetChart` in the main grid

## Decisions Made

- `CellContent` guards on `typeof batteryPct !== "number"` and returns `null` for that invocation — Recharts' `Treemap` calls the custom `content` render prop once for a synthetic whole-canvas root/container node (depth 0) in addition to each real leaf cell, and that root node carries none of `HeatmapDatum`'s fields. Without the guard, the very first render throws `Cannot read properties of undefined (reading 'toFixed')` on every mount. Discovered empirically by running the RED->GREEN cycle rather than assumed from the `.d.ts` types (which don't document this root-invocation behavior).
- `EnergyBudgetChart` polls on a local `HISTORY_POLL_INTERVAL_MS` constant (5000, matching `FleetOpsProvider`'s `FLEET_POLL_INTERVAL_MS` by value) rather than importing the provider's private constant — the plan's `files_modified` list for this plan does not include `FleetOpsProvider.tsx`, and exporting a symbol from it solely to serve one external, single-purpose consumer would widen that file beyond what this plan scoped. The cadence match is documented in a code comment instead.
- `EnergyBudgetChart`'s `XAxis` uses `interval={0}` (render every tick) instead of Recharts' default overlap-avoidance interval, which depends on real text measurement unavailable under jsdom — this makes the tick count deterministic and testable, and matches the plan's explicit "axis reflects three data points" behavior for what is, in this single-operator demo, always a small-N series.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Recharts Treemap's synthetic root-node content invocation crashed CellContent**
- **Found during:** Task 1, first `npx vitest run FleetHeatmap` after writing the initial implementation
- **Issue:** `TypeError: Cannot read properties of undefined (reading 'toFixed')` on every render — Recharts' `Treemap.renderNode()` calls the custom `content` component once for the whole-canvas container node (`depth: 0`, no `name`/`batteryPct`) in addition to once per real data leaf; `CellContent` unconditionally called `batteryPct.toFixed(1)`.
- **Fix:** Added a guard at the top of `CellContent`: `if (typeof batteryPct !== "number") return null;` — renders nothing for the synthetic root invocation, proceeds normally for real leaves.
- **Files modified:** `frontend/src/components/FleetHeatmap.tsx` only.
- **Verification:** All 8 `FleetHeatmap` behaviors pass; `npm run build` succeeds.
- **Committed in:** `b58851b` (Task 1 GREEN) — found and fixed before the first full-green run, same TDD-discipline pattern noted in 03-04's summary.

**2. [Rule 1 - Bug] Block comment containing a literal `*/` inside Tailwind-prefix prose terminated early**
- **Found during:** Task 1, immediately after the CellContent guard fix above, when `npx vitest run FleetHeatmap` failed with an esbuild parse error at `bg-*/text-*` inside a doc comment.
- **Issue:** The comment text `Tailwind bg-*/text-* utilities don't affect SVG fill` contains the literal substring `*/`, which esbuild (correctly) treats as the block comment's closing delimiter regardless of authorial intent, corrupting the rest of the file's parse.
- **Fix:** Reworded to "Tailwind background/text utilities don't affect SVG fill/stroke" — same meaning, no embedded comment-closing sequence.
- **Files modified:** `frontend/src/components/FleetHeatmap.tsx` only.
- **Verification:** File transforms and parses cleanly; full suite green.
- **Committed in:** `b58851b` (Task 1 GREEN) — caught before any test run succeeded.

**3. [Rule 1 - Bug] FleetHeatmap.test.tsx Test 2 raced the mission-upsert effect under full-suite timing**
- **Found during:** Task 2, running `npm test` (full suite) after EnergyBudgetChart was green — Test 2 passed reliably in file isolation (`npx vitest run FleetHeatmap`) but failed intermittently under the full 11-file suite with both cells reporting equal area.
- **Issue:** The test's `Setup` component upserts missions only after `FleetOpsProvider`'s mount-triggered `refetch()` resolves and `loaded` flips true — one render tick after the heatmap's first (idle-weighted) paint. The original assertion read cell areas immediately after a `waitFor` that only checked `rect` count, which can already be satisfied by the pre-mission-upsert idle-weighted render.
- **Fix:** Moved the area-ratio assertion inside the same `waitFor` block used for the rect-count check, so the test polls until the mission-weighted layout has actually settled instead of asserting on the first paint.
- **Files modified:** `frontend/src/components/FleetHeatmap.test.tsx` only.
- **Verification:** `npm test` (full suite) passed twice in a row after the fix, including `page.tsx`'s integration test.
- **Committed in:** `62c26a1` — a standalone fix commit between Task 1's GREEN and Task 2's RED, since it was discovered while validating Task 2's cross-component integration, not while working on Task 1 itself.

---

**Total deviations:** 3 auto-fixed (2 found during Task 1's own TDD cycle before its first full-green run; 1 found during Task 2's full-suite integration check). All are test/implementation-local fixes with no architectural impact.
**Impact on plan:** None on scope or files_modified beyond the two component pairs and `page.tsx` the plan specified — all three fixes stayed within `FleetHeatmap.tsx`/`FleetHeatmap.test.tsx`.

## Issues Encountered

- `npm run lint` (`next lint`) still requires interactive ESLint setup — the same pre-existing issue logged in `deferred-items.md` from plan 03-01 and re-confirmed in every subsequent plan's summary (03-02 through 03-04). Not re-fixed here per the scope-boundary rule; not re-logged as a new duplicate entry. `npx tsc --noEmit` (clean) and `npm run build` (succeeds) provide equivalent static-correctness coverage for this plan's changes.
- Fresh worktree had no `node_modules` (gitignored). Ran `npm ci` in `frontend/` to install from the committed lockfile before running tests/build — same one-time step noted in 03-04's summary.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

FE-03 and FE-04 are complete: the fleet heatmap gives at-a-glance situational awareness sharing the same drone-selection state as the roster row and detail panel clicks, and the energy-budget chart plots the backend's own snapshot history independently of the polling provider. Phase 03's remaining plan (06 — AI flight-director chat panel) can proceed without further changes to `FleetOpsProvider`, `page.tsx`'s main grid, or either new component; the chat placeholder `<aside>` in `page.tsx` is untouched and ready for plan 06 to replace. No blockers.

---
*Phase: 03-frontend-buildout*
*Completed: 2026-08-13*

## Self-Check: PASSED

All five key files verified present on disk (`frontend/src/components/FleetHeatmap.tsx`,
`frontend/src/components/FleetHeatmap.test.tsx`, `frontend/src/components/EnergyBudgetChart.tsx`,
`frontend/src/components/EnergyBudgetChart.test.tsx`, `frontend/src/app/page.tsx`) plus this
SUMMARY.md. All five commits (`425d1f2`, `62c26a1`, `b58851b`, `8cdab13`, `a7d3a28`) verified
present in `git log`.
