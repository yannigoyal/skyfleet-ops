# Phase 3: Frontend Buildout - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator gets the complete ops-console UI — visualization, manual dispatch, and the AI chat
panel — built against the now-stable roster/chat/telemetry/missions API contracts (Phase 1 and
Phase 2 are complete). Requirements: FE-01 through FE-09. This phase is frontend-only; no backend
API changes are in scope.

</domain>

<decisions>
## Implementation Decisions

### State & Data Architecture
- **D-01:** Introduce a `FleetOpsProvider` (React Context) wrapping energy budget, missions list,
  and selected-drone state, rather than prop-drilling from `page.tsx`. — **Reversibility:** costly
  — **rationale:** once 7+ components (header, roster, detail panel, heatmap, missions table,
  dispatch bar, chat panel) consume the context, migrating back to prop-drilling means rewiring
  every consumer's data access.
- **D-02:** `FleetOpsProvider` polls `GET /api/fleet` on an interval AND refetches immediately
  after every dispatch/recall/chat action. The backend's delivery scheduler auto-completes
  missions server-side independent of user action, so refetch-on-action alone would leave the
  missions table showing stale status/ETA.
- **D-03:** `useTelemetryStream`'s per-drone battery history (used by FE-01's sparkline) is capped
  to the last N readings per drone (not the current unbounded accumulation), keeping memory bounded
  over a long session. Exact N left to the planner (~120 readings / ~1 min at 500ms ticks is a
  reasonable starting point).
- **D-04:** Selected-drone state (FE-02) lives in `FleetOpsProvider` as plain client-side state —
  no URL query-param sync. This is a single-operator demo with no auth/sharing needs.

### AI Chat Panel UX
- **D-05:** Chat panel is a fixed right sidebar, visible by default, with a collapse toggle added
  to satisfy FE-08's "docked/collapsible sidebar" wording — not a modal, not left-docked.
- **D-06:** FE-09 confirmation cards show: action verb + key params + an outcome badge (e.g.
  "LAUNCH FALCON-03 → Riverside (4.2km)" with a green "Dispatched" badge, or a red "Failed:
  insufficient budget" badge on error) — compact, not an expandable raw-JSON view.
- **D-07:** When the chat panel executes a mission/roster action, it triggers the same shared
  refetch function from `FleetOpsProvider` that the dispatch bar uses (per D-02) — no separate
  optimistic-merge code path, so chat-driven and manual actions stay in sync through one mechanism.
- **D-08:** The chat message input is disabled while waiting for a response (no message queueing).
  Matches the non-streaming `POST /api/chat` contract from Phase 2 (one complete JSON response per
  request, no token streaming) — avoids out-of-order response handling.

### Heatmap Implementation
- **D-09:** FE-03's treemap uses Recharts' `Treemap` component (recharts 2.13.0, already pinned),
  not a hand-rolled grid — reuses the same charting library as the FE-04 budget line chart, with a
  custom `content` render prop for per-cell coloring.
- **D-10:** Idle drones (no active mission / no `energy_cost_kwh`) are included in the heatmap with
  a fixed minimum weight (e.g. equivalent to 0.1 kWh) so the full fleet is always visible —
  otherwise the heatmap looks broken/empty on fresh start (500kWh budget, 0 active missions, per the
  TEST-04 E2E scenario).
- **D-11:** Battery-health coloring uses 3-band thresholds: green ≥50%, amber 20–50%, red <20% —
  matches the existing roster-row flash convention (amber = draining, green = stable) and reuses
  the `ops.amber`/`ops.teal`/`ops.signal` Tailwind tokens already defined in `tailwind.config.ts`.
- **D-12:** Clicking a heatmap cell selects that drone (same `FleetOpsProvider` selected-drone
  state as a roster-row click) and opens the FE-02 detail panel — one selection mechanism, multiple
  entry points.

### Missions Table & Dispatch Bar
- **D-13:** FE-05's ETA column is computed client-side from `distance_km` and a fixed cruise speed
  (reusing the simulator's `DEFAULT_CRUISE_SPEED_KMH` constant as the assumed value) —
  `eta = updated_at + distance_km / cruise_speed_kmh`. No backend schema/API change; the `missions`
  table has no `eta` column and adding one is out of this frontend-only phase's scope.
- **D-14:** The dispatch bar does not duplicate backend validation client-side. It submits and
  surfaces whatever error the backend returns (`InsufficientBudgetError`, `DroneAlreadyEnRouteError`
  etc. from `missions/service.py`, already reason-coded) as an inline message — no separate
  eligibility-checking logic to keep in sync with the backend.
- **D-15:** Dispatch bar's drone field is a dropdown populated from the current roster (a drone
  must be on the roster to be valid — the backend enforces this, so a dropdown prevents typos
  entirely). The zone field is free text — PLAN.md and the schema treat zone as a display label with
  no enumerated list anywhere, so inventing a fixed preset list would be unrequested scope.
- **D-16:** FE-02's detail panel shows a plain "No active mission" empty-state message (not the
  drone's most recent completed/recalled mission from `mission_log`) when the selected drone has no
  active mission — telemetry charts (battery/altitude/speed) still render normally regardless.

### Claude's Discretion
- Exact retention count for the telemetry history cap (D-03) — reasonable range, not a hard number.
- Exact px/rem sizing for the chat sidebar width, collapse-toggle placement, and minimum heatmap
  cell weight (D-10) — visual specifics not pinned here; expect the UI-SPEC gate (this phase has
  "UI hint: yes" in ROADMAP.md) to nail these down with more precision.
- Component/file naming for new components — follow the existing PascalCase convention
  (`FleetRosterPanel.tsx`-style) and `.claude/CLAUDE.md`'s naming table.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specification
- `planning/PLAN.md` §10 (Frontend Design) — the authoritative element list (roster panel, detail
  panel, heatmap, budget chart, missions table, dispatch bar, chat panel, header) and technical
  notes (EventSource, canvas-based charting, flash-effect pattern, Tailwind dark theme).
- `planning/PLAN.md` §8 (API Endpoints) — `GET /api/fleet`, `GET /api/fleet/history`,
  `GET/POST /api/roster`, `DELETE /api/roster/{drone_id}`, `POST/DELETE /api/fleet/missions`,
  `POST /api/chat` — the full contract this phase's frontend consumes.
- `.planning/REQUIREMENTS.md` — FE-01 through FE-09 (this phase's requirement text, including the
  exact FE-08/FE-09 wording referenced in D-05/D-06).

### Codebase maps (already generated)
- `.planning/codebase/STRUCTURE.md` — existing frontend file layout, "Frontend Component State
  Management" section (flags React Context as the suitable-but-unused option — informs D-01).
- `.planning/codebase/STACK.md` — confirms recharts 2.13.0 is the pinned charting library
  (informs D-09) and the Tailwind dark-theme token names (`ops.bg`, `ops.panel`, `ops.amber`,
  `ops.teal`, `ops.signal` — informs D-11).
- `.planning/codebase/CONVENTIONS.md` — TypeScript/React naming conventions for new components,
  hooks, and types.

### Existing implementation this phase builds on
- `backend/app/missions/service.py` — `MissionError` subclasses (`InsufficientBudgetError`,
  `DroneAlreadyEnRouteError`, etc.) with `reason` attributes — the error shape D-14's inline error
  surfacing depends on.
- `backend/app/telemetry/simulator.py` — `DEFAULT_CRUISE_SPEED_KMH` constant — the value D-13's
  client-side ETA calculation should reuse.
- `frontend/src/lib/useTelemetryStream.ts` — existing SSE hook; D-03 modifies its history
  accumulation to add a cap.
- `frontend/src/components/{Header,FleetRosterPanel,ConnectionDot}.tsx`,
  `frontend/src/types/telemetry.ts` — existing components/types this phase extends and integrates
  with the new `FleetOpsProvider`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/useTelemetryStream.ts` — SSE hook already accumulating battery history; needs
  a bound added (D-03) rather than a rewrite.
- `frontend/src/components/Header.tsx` — already shows some header content; FE-07 extends it
  (live budget, connection status, active mission count) rather than replacing it.
- `frontend/src/components/FleetRosterPanel.tsx` — existing roster grid; FE-01 (sparklines) and the
  click-to-select behavior (D-04/D-12) extend this component.
- `frontend/src/components/ConnectionDot.tsx` — existing connection-status indicator, reusable as-is
  for FE-07's header requirement.

### Established Patterns
- Tailwind dark theme with `ops.bg`/`ops.panel`/`ops.amber`/`ops.teal`/`ops.signal` custom color
  tokens already defined in `tailwind.config.ts` — new components should reuse these, not invent
  new colors (informs D-11 directly).
- PascalCase component files, `use*`-prefixed camelCase hook files, `@/*` → `./src/*` path alias.
- No global state management library in use yet; `FleetOpsProvider` (D-01) will be the first.

### Integration Points
- `frontend/src/app/page.tsx` — currently renders `Header`, `FleetRosterPanel`, and a chat-sidebar
  placeholder. New components (detail panel, heatmap, budget chart, missions table, dispatch bar,
  real chat panel) mount here, wrapped by the new `FleetOpsProvider`.
- Backend endpoints this phase's frontend calls are all already built and tested (Phase 1 roster,
  Phase 2 chat, and the pre-existing missions/telemetry endpoints) — no backend work is in scope.

</code_context>

<specifics>
## Specific Ideas

No literal UI mockups or copy examples were provided beyond the decisions above. Visual/layout
specifics (exact spacing, panel proportions, chat sidebar width) are deliberately left for the
UI-SPEC gate this phase triggers (ROADMAP.md marks this phase "UI hint: yes").

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope-creep suggestions came up during this
session.

</deferred>

---

*Phase: 3-Frontend Buildout*
*Context gathered: 2026-08-13*
