# Phase 3: Frontend Buildout - Research

**Researched:** 2026-08-13
**Domain:** Next.js/React ops-console frontend (SSE consumption, REST polling, Recharts visualization, client-side global state)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Introduce a `FleetOpsProvider` (React Context) wrapping energy budget, missions list,
  and selected-drone state, rather than prop-drilling from `page.tsx`. — Reversibility: costly —
  once 7+ components consume the context, migrating back to prop-drilling means rewiring every
  consumer's data access.
- **D-02:** `FleetOpsProvider` polls `GET /api/fleet` on an interval AND refetches immediately
  after every dispatch/recall/chat action. The backend's delivery scheduler auto-completes
  missions server-side independent of user action, so refetch-on-action alone would leave the
  missions table showing stale status/ETA.
- **D-03:** `useTelemetryStream`'s per-drone battery history (used by FE-01's sparkline) is capped
  to the last N readings per drone, keeping memory bounded over a long session. Exact N left to
  the planner (~120 readings / ~1 min at 500ms ticks is a reasonable starting point).
- **D-04:** Selected-drone state (FE-02) lives in `FleetOpsProvider` as plain client-side state —
  no URL query-param sync. Single-operator demo, no auth/sharing needs.
- **D-05:** Chat panel is a fixed right sidebar, visible by default, with a collapse toggle
  (satisfies FE-08's "docked/collapsible sidebar") — not a modal, not left-docked.
- **D-06:** FE-09 confirmation cards show: action verb + key params + an outcome badge (e.g.
  "LAUNCH FALCON-03 → Riverside (4.2km)" with a green "Dispatched" badge, or a red "Failed:
  insufficient budget" badge on error) — compact, not an expandable raw-JSON view.
- **D-07:** When the chat panel executes a mission/roster action, it triggers the same shared
  refetch function from `FleetOpsProvider` that the dispatch bar uses (per D-02) — no separate
  optimistic-merge code path.
- **D-08:** The chat message input is disabled while waiting for a response (no message queueing).
  Matches the non-streaming `POST /api/chat` contract (one complete JSON response per request).
- **D-09:** FE-03's treemap uses Recharts' `Treemap` component (recharts 2.13.0 range, already
  pinned), not a hand-rolled grid — reuses the same charting library as the FE-04 budget line
  chart, with a custom `content` render prop for per-cell coloring.
- **D-10:** Idle drones (no active mission / no `energy_cost_kwh`) are included in the heatmap
  with a fixed minimum weight (e.g. equivalent to 0.1 kWh) so the full fleet is always visible —
  otherwise the heatmap looks broken/empty on fresh start (500kWh budget, 0 active missions).
- **D-11:** Battery-health coloring uses 3-band thresholds: green ≥50%, amber 20–50%, red <20% —
  matches the existing roster-row flash convention. **UI-SPEC correction (verified against code):**
  the actual color precedent in `FleetRosterPanel.tsx`'s `batteryColor()` uses `emerald-400` for
  the healthy band, not `ops.teal` — follow `emerald-400`/`ops.amber`/`red-400`, not the `ops.*`
  tri-color set literally (see UI-SPEC Color section for the corrected mapping).
- **D-12:** Clicking a heatmap cell selects that drone (same `FleetOpsProvider` selected-drone
  state as a roster-row click) and opens the FE-02 detail panel.
- **D-13:** FE-05's ETA column is computed client-side from `distance_km` and a fixed cruise speed
  (reusing the simulator's `DEFAULT_CRUISE_SPEED_KMH` constant) — `eta = updated_at +
  distance_km / cruise_speed_kmh`. No backend schema/API change.
  **⚠️ Research correction — see "Critical Finding: eta_minutes already exists" below.** The
  backend's `_mission_response()` (`backend/app/missions/router.py:40-46`) already computes and
  returns an `eta_minutes` field on every mission object from `GET /api/fleet`, `POST
  /api/fleet/missions`, and `DELETE /api/fleet/missions/{drone_id}` — using live telemetry speed
  with a `DEFAULT_CRUISE_SPEED_KMH` fallback, which is strictly more accurate than a naive
  client-side recomputation from a fixed constant. This is new information the CONTEXT.md session
  did not have (or the field was added after). Flagged in Open Questions for planner/user
  decision — this doc does not unilaterally override the locked decision.
- **D-14:** The dispatch bar does not duplicate backend validation client-side. It submits and
  surfaces whatever error the backend returns (`InsufficientBudgetError`, `DroneAlreadyEnRouteError`
  etc., already reason-coded) as an inline message — no separate eligibility-checking logic.
- **D-15:** Dispatch bar's drone field is a dropdown populated from the current roster. The zone
  field is free text — no enumerated list.
- **D-16:** FE-02's detail panel shows a plain "No active mission" empty-state message (not the
  drone's most recent completed/recalled mission from `mission_log`) when the selected drone has
  no active mission — telemetry charts still render normally regardless.

### Claude's Discretion

- Exact retention count for the telemetry history cap (D-03) — reasonable range, not a hard
  number. **Note:** `useTelemetryStream.ts` already implements this cap today with a default of
  120 (`maxHistoryPoints = 120`, see Verified Baseline below) — D-03 may already be satisfied with
  no code change required, only confirmation.
- Exact px/rem sizing for the chat sidebar width, collapse-toggle placement, and minimum heatmap
  cell weight (D-10) — resolved with more precision in 03-UI-SPEC.md (see below).
- Component/file naming for new components — PascalCase convention (`FleetRosterPanel.tsx`-style).

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. No scope-creep suggestions came up during this
session.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FE-01 | Per-drone sparkline mini-chart renders next to each roster row, built from `useTelemetryStream`'s battery history | `useTelemetryStream` already exposes `history: Record<string, number[]>` (battery_pct series, capped at `maxHistoryPoints`, default 120) — see Verified Baseline. Render with Recharts `LineChart`/`Line` (no axes/grid, sparkline style) sized to fit the roster row. |
| FE-02 | Clicking a drone opens a detail panel: battery, altitude, speed, current mission over time | Detail panel is a new component reading `snapshot[selectedDroneId]` plus `history` for battery, and a new `altitudeHistory`/`speedHistory` extension to `useTelemetryStream` (see Architecture Patterns) for the other two series. Mission comes from `FleetOpsProvider`'s missions list filtered by `drone_id`. D-16 empty-state copy is in UI-SPEC. |
| FE-03 | Fleet heatmap (treemap) sized by energy cost, colored by battery health | Recharts `Treemap` with custom `content` render prop — verified against installed `node_modules/recharts` type defs (`TreemapNode`: `x,y,width,height,depth,index,name,value` + passthrough custom fields). `onClick` prop wires D-12 selection directly. |
| FE-04 | Energy-budget line chart from `GET /api/fleet/history` | `budget_snapshots` rows are `{remaining_kwh, recorded_at}` (verified against `repository.list_budget_snapshots`) — feed directly into Recharts `LineChart` with `XAxis dataKey="recorded_at"`, `Line dataKey="remaining_kwh"`. |
| FE-05 | Missions table: drone, zone, distance, energy cost, status, ETA — for every mission | **Gap found:** `GET /api/fleet` only returns *active* (`en_route`) missions (verified: `repository.list_active_missions` filters `WHERE status = 'en_route'`). No endpoint returns delivered/recalled history. See Critical Finding below for the client-side accumulation pattern needed to satisfy "every mission" without a backend change. |
| FE-06 | Dispatch bar launches/recalls instantly, no confirmation | `POST /api/fleet/missions` / `DELETE /api/fleet/missions/{drone_id}`, error shape verified against `missions/router.py` `_ERROR_STATUS` and `MissionError` subclasses in `missions/models.py`. |
| FE-07 | Header: live remaining budget, connection status, active mission count | `Header.tsx` already has the right shape (`energyBudgetKwh`, `activeMissionCount`, `connectionStatus` props) but `page.tsx` currently hardcodes `energyBudgetKwh={500.0}` and `activeMissionCount={0}` — wire both to `FleetOpsProvider`'s live `remaining_kwh` / `active_mission_count` from `GET /api/fleet`. |
| FE-08 | AI chat panel: input, scrolling history, loading indicator | `POST /api/chat` contract verified against `chat/router.py` — returns `{message, missions, roster_changes, errors}` in one shot, no streaming. D-08 disables input during the request. |
| FE-09 | AI-executed actions shown as inline structured confirmation cards | `reply.missions` / `reply.roster_changes` arrays from the chat response map directly to D-06's card format; `errors` array supplies the failure badges. |
</phase_requirements>

## Summary

Phase 3 extends a small, already-working frontend baseline (`Header`, `FleetRosterPanel`,
`ConnectionDot`, `useTelemetryStream`) into the full ops-console: sparklines, a drone detail
panel, a Recharts `Treemap` heatmap, an energy-budget line chart, a missions table, a dispatch
bar, and a chat sidebar — all coordinated through one new `FleetOpsProvider` React Context (D-01)
that polls `GET /api/fleet` and refetches after every mutating action (D-02). All nine backend
endpoints this phase consumes are complete, tested, and were read directly from source in this
research pass; their exact response shapes and error-reason codes are documented below so the
planner can wire components without guessing field names.

Two findings materially affect planning and are called out because they are not obvious from
CONTEXT.md or UI-SPEC.md alone. First, `GET /api/fleet` returns **only currently-active
(`en_route`) missions** — there is no endpoint for delivered/recalled mission history, yet FE-05
requires a table of "every mission" and the UI-SPEC's status-label contract explicitly documents
a "Recalled" label, implying recalled missions must remain visible. Since backend changes are out
of scope for this phase, the missions table must be built from a **client-side accumulated
mission map** in `FleetOpsProvider` that merges each poll's active list with what dispatch/recall
responses already told the client directly, and infers "delivered" for any mission that silently
drops out of the active list without an explicit recall response. Second, the backend's mission
response already includes a live-computed `eta_minutes` field — which conflicts with D-13's
premise that no such field exists; this is flagged for the planner/user to confirm rather than
silently overridden.

**Primary recommendation:** Build one `FleetOpsProvider` (poll + accumulate missions client-side,
per the pattern above) as the single source of truth for budget/missions/selection, wire the
existing `useTelemetryStream` (already correctly bounded) for live telemetry, and use Recharts'
`Treemap`/`LineChart` (already installed at 2.15.4, within the pinned `^2.13.0` range) for both
visualizations — no new npm dependencies are required for this phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live telemetry display (battery/altitude/speed, sparklines) | Browser / Client | API (SSE source) | `useTelemetryStream` already owns SSE consumption and history accumulation entirely client-side; no server aggregation needed |
| Fleet/budget/mission state (`FleetOpsProvider`) | Browser / Client | API / Backend | Client polls and accumulates a view model over REST responses; backend remains the source of truth for validation and persistence |
| Mission dispatch/recall validation | API / Backend | — | `missions/service.py` owns all eligibility/budget rules; frontend must not duplicate them (D-14) — client only submits and displays the returned error |
| Mission history/status inference (delivered vs. recalled) | Browser / Client | API / Backend | Backend has the data (`mission_log`, `missions.status`) but exposes no "all missions" endpoint; client must infer from polling deltas + direct action responses (see Critical Finding) — a backend `GET /api/fleet/missions` (all statuses) endpoint would be the correct long-term home for this, but is out of scope this phase |
| AI action execution (launch/recall/roster changes) | API / Backend | Browser / Client | `POST /api/chat` executes server-side through the same service functions as manual dispatch; frontend only renders the returned `missions`/`roster_changes`/`errors` arrays (D-07) |
| Chat conversation state | Browser / Client | API / Backend | Transcript display and loading state are client-only; persistence of `chat_messages` and history-in-prompt is already handled server-side (Phase 2) |
| Heatmap/chart rendering | Browser / Client | — | Pure presentation over data already fetched by `FleetOpsProvider`/`useTelemetryStream`; Recharts renders client-side only (no SSR data fetching, static export has no server runtime) |

## Verified Baseline (existing code this phase extends)

> Read directly from the working tree this session — not assumed.

- **`frontend/src/lib/useTelemetryStream.ts`** [VERIFIED: frontend/src/lib/useTelemetryStream.ts:1-42] — already implements exactly what D-03 asks for:
  ```
  export function useTelemetryStream(maxHistoryPoints = 120) {
    ...
    const history = useRef<Record<string, number[]>>({});
    ...
    source.onmessage = (event) => {
      ...
      for (const [droneId, reading] of Object.entries(data)) {
        const points = history.current[droneId] ?? [];
        points.push(reading.battery_pct);
        if (points.length > maxHistoryPoints) points.shift();
        history.current[droneId] = points;
      }
    };
    return { snapshot, status, history: history.current };
  }
  ```
  It only accumulates `battery_pct` into `history`. FE-02 additionally needs altitude and speed
  history for the detail panel's "over time" requirement — this hook needs a **small extension**
  (add `altitudeHistory`/`speedHistory` parallel maps, same cap pattern), not a rewrite.
- **`frontend/src/types/telemetry.ts`** [VERIFIED: frontend/src/types/telemetry.ts:1-16] — `TelemetryReading` fields, quoted verbatim:
  ```
  export type DroneStatus = "idle" | "in_flight" | "charging" | "low_battery" | "offline";
  export interface TelemetryReading {
    drone_id: string; battery_pct: number; previous_battery_pct: number;
    altitude_m: number; speed_kmh: number; status: DroneStatus; timestamp: number;
    battery_delta: number; battery_direction: "draining" | "charging" | "flat";
  }
  export type TelemetrySnapshot = Record<string, TelemetryReading>;
  ```
- **`frontend/src/components/Header.tsx`** [VERIFIED: frontend/src/components/Header.tsx:1-28] — props already `{connectionStatus, energyBudgetKwh, activeMissionCount}`; body already renders both values and `<ConnectionDot status={connectionStatus} />`. FE-07 work is: replace `page.tsx`'s hardcoded `energyBudgetKwh={500.0}` / `activeMissionCount={0}` with live values from `FleetOpsProvider`. No new Header markup is required unless UI-SPEC wants additional elements (it doesn't — Header extension is data-wiring only).
- **`frontend/src/components/FleetRosterPanel.tsx`** [VERIFIED: frontend/src/components/FleetRosterPanel.tsx:1-79] — `batteryColor()` (quoted): `if (pct <= 20) return "text-red-400"; if (pct <= 50) return "text-ops-amber"; return "text-emerald-400";` — this is the authoritative 3-band color precedent D-11/UI-SPEC point to. `onSelect` prop already exists and is called from a row `onClick` — FE-01's sparkline is an additional `<td>` in this same row map; no restructuring needed.
- **`frontend/src/components/ConnectionDot.tsx`** [VERIFIED: frontend/src/components/ConnectionDot.tsx:1-23] — `COLORS`: `connected: "bg-emerald-500"`, `connecting: "bg-ops-amber"`, `disconnected: "bg-red-500"`. Reusable as-is for FE-07.
- **`frontend/src/app/page.tsx`** [VERIFIED: frontend/src/app/page.tsx:1-33] — currently renders `Header`, `FleetRosterPanel`, and a static placeholder `<aside>` for chat. This phase's `FleetOpsProvider` wraps this tree; new components (`DetailPanel`, `FleetHeatmap`, `EnergyBudgetChart`, `MissionsTable`, `DispatchBar`, `ChatPanel`) mount alongside/inside it.
- **`frontend/tailwind.config.ts`** [VERIFIED: frontend/tailwind.config.ts:1-30] — `ops.bg #0a0e14`, `ops.panel #12161f`, `ops.border #232a38`, `ops.amber #f2a900`, `ops.teal #17a2b8`, `ops.signal #e8622c`; `animate-flash-charge` / `animate-flash-drain` keyframes (500ms, background-color transition) already defined — reuse verbatim, do not redefine.

## Critical Finding: Missions Table Needs Client-Side History Accumulation

**The problem** [VERIFIED: backend/app/missions/repository.py:82-87, backend/app/missions/router.py:53-63]:

```python
# repository.py
async def list_active_missions(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> list[Mission]:
    rows = await db.fetchall(
        "SELECT * FROM missions WHERE operator_id = ? AND status = 'en_route' ORDER BY updated_at",
        (operator_id,),
    )
    return [_row_to_mission(row) for row in rows]
```
```python
# router.py — GET /api/fleet
@router.get("")
async def get_fleet_status():
    ...
    active = await repository.list_active_missions(db)
    return {..., "missions": [_mission_response(mission, cache) for mission in active]}
```

`GET /api/fleet` — the only fleet-status read endpoint — filters to `status = 'en_route'` only.
There is no `GET /api/fleet/missions` (all statuses) endpoint, and `mission_log` (the append-only
history table) is never exposed via any router. Once a mission is recalled or delivered, it
disappears from every subsequent `GET /api/fleet` response.

This conflicts with FE-05 ("Missions table lists ... for every mission") and with UI-SPEC's
Status labels row, which documents `recalled` → "Recalled" as a displayable status — implying
recalled missions are expected to remain visible, not vanish.

**No backend change is in scope this phase** (CONTEXT.md phase boundary: "This phase is
frontend-only; no backend API changes are in scope"). The recommended pattern:

1. `FleetOpsProvider` keeps a `missionsById: Map<string, MissionRecord>` that persists across
   polls (not replaced wholesale each fetch).
2. On every `GET /api/fleet` poll, **upsert** each returned active mission into the map by `id`
   (status will be `"en_route"`).
3. `POST /api/fleet/missions` and `DELETE /api/fleet/missions/{drone_id}` both return the mutated
   mission directly with its new status [VERIFIED: backend/app/missions/router.py:76-107] — upsert
   that response into the map immediately (this is how a `"recalled"` status ever enters the map;
   the poll alone will never show it, since a recalled mission is no longer `en_route`).
4. On each poll, for any mission in the map still marked `"en_route"` that is **absent** from the
   new active list, and that was not just updated by a direct recall response this tick, mark it
   `"delivered"` client-side — this is the observable signature of the server's background
   `deliver_overdue_missions` scheduler completing it [VERIFIED: backend/app/missions/scheduler.py:53-62, 65-70] (runs every 5s, no client notification other than disappearing from the active list).
5. Session-scoped only: a page reload loses history for missions completed before that reload
   (acceptable for a single-operator demo; document as a known limitation, not a bug).

```typescript
// Source: derived from verified repository.py/router.py/scheduler.py behavior above
type MissionStatus = "en_route" | "delivered" | "recalled";
interface MissionRecord { id: string; drone_id: string; zone: string; distance_km: number;
  energy_cost_kwh: number; status: MissionStatus; updated_at: string; eta_minutes?: number; }

function mergeMissions(
  prev: Map<string, MissionRecord>,
  activeFromPoll: MissionRecord[],
): Map<string, MissionRecord> {
  const next = new Map(prev);
  const activeIds = new Set(activeFromPoll.map((m) => m.id));
  for (const mission of activeFromPoll) next.set(mission.id, mission);
  for (const [id, mission] of next) {
    if (mission.status === "en_route" && !activeIds.has(id)) {
      next.set(id, { ...mission, status: "delivered" });
    }
  }
  return next;
}
```

## Open Questions

1. **D-13 (client-side ETA) vs. the backend's existing `eta_minutes` field**
   - What we know: `_mission_response()` [VERIFIED: backend/app/missions/router.py:40-46] already
     computes `eta_minutes` for every `en_route` mission returned by `GET /api/fleet`,
     `POST /api/fleet/missions`, and `DELETE /api/fleet/missions/{drone_id}`:
     ```python
     def _mission_response(mission: Mission, cache: TelemetryCache) -> dict:
         payload = mission.to_dict()
         if mission.status == "en_route":
             reading = cache.get(mission.drone_id)
             speed = reading.speed_kmh if reading and reading.speed_kmh > 0 else DEFAULT_CRUISE_SPEED_KMH
             payload["eta_minutes"] = round((mission.distance_km / speed) * 60, 1)
         return payload
     ```
   - What's unclear: whether D-13 ("no backend eta field exists, compute client-side") was written
     before this field existed, or whether the discuss-phase session simply didn't check
     `router.py`. The two approaches produce different numbers (backend uses **live** telemetry
     speed with a `DEFAULT_CRUISE_SPEED_KMH` fallback; D-13's client formula uses the fixed
     constant only, and would need `updated_at` to compute a live countdown that the backend
     value doesn't need).
   - Recommendation: surface this to the user/planner before locking the ETA implementation.
     Reusing `mission.eta_minutes` verbatim is simpler and more accurate; it also already exists
     on the launch/recall response, avoiding a second round-trip. If D-13 is kept as-is
     (client computes independently, ignoring the field), document that as a deliberate choice,
     not an oversight.

2. **Detail panel altitude/speed history — extend `useTelemetryStream` or add a second hook?**
   - What we know: `useTelemetryStream` currently only accumulates `battery_pct` into `history`.
     FE-02 needs altitude and speed "over time" too.
   - What's unclear: whether to extend the single hook's `history` shape to
     `Record<string, { battery: number[]; altitude: number[]; speed: number[] }>` (breaking
     change to the existing `history` consumer, `FleetRosterPanel`'s future sparkline) or add
     parallel maps (`batteryHistory`, `altitudeHistory`, `speedHistory`) to avoid touching the
     existing shape.
   - Recommendation: parallel maps, all built inside the same `onmessage` handler and the same
     cap logic — avoids a breaking change to the one function three-plus components will depend
     on by the end of this phase.

3. **Missions table sourcing before any mission has ever been launched this session**
   - What we know: On fresh start, `missionsById` is empty and `GET /api/fleet` returns
     `missions: []` (0 active). UI-SPEC's empty-state copy ("No active missions") already covers
     this.
   - What's unclear: nothing blocking — noted only because it interacts with the Critical Finding
     above (empty state is correct both for "truly zero missions ever" and "zero currently active
     missions", which is a subtle but acceptable copy ambiguity per the locked UI-SPEC wording).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| recharts | `^2.13.0` (installed: **2.15.4**, verified via `node_modules/recharts/package.json`) | Treemap heatmap (FE-03), energy-budget line chart (FE-04), roster sparklines (FE-01), detail-panel telemetry charts (FE-02) | Already a pinned project dependency (`.claude/CLAUDE.md`, `frontend/package.json`); avoids adding a second charting library; SVG-based, works fine in a static export (no server runtime needed) |
| React Context (`createContext`/`useContext`, built into React 18.3, no package) | 18.3.0 (already installed) | `FleetOpsProvider` (D-01) | No state-management library is installed or needed; `.planning/codebase/STRUCTURE.md` explicitly flags Context as the suitable-but-unused option for this exact need |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| native `fetch` | browser built-in | `FleetOpsProvider` polling `GET /api/fleet`, dispatch bar POST/DELETE, chat POST | Already same-origin (`/api/*`), no CORS config, no HTTP client library needed — matches the existing `EventSource`-only pattern in `useTelemetryStream` |
| native `EventSource` | browser built-in | Already used by `useTelemetryStream` — no change needed for this phase beyond the history-cap extension | — |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| React Context (D-01) | Zustand / Jotai | Adds a new dependency for a single-page, single-operator demo with ~7 consumers — Context is sufficient at this scale and matches `.claude/CLAUDE.md`'s "avoid unnecessary dependencies" preference |
| Recharts Treemap (D-09) | Hand-rolled CSS grid treemap | Explicitly rejected by D-09; Recharts already computes squarified-treemap layout math, hand-rolling it is a classic "don't hand-roll" case |
| Polling `GET /api/fleet` (D-02) | A second SSE stream for fleet/mission state | Rejected implicitly by PLAN.md's SSE-is-telemetry-only design and D-02's explicit polling choice; adding a second live channel is unrequested scope for a frontend-only phase |

**Installation:** No new packages required — `recharts`, `react`, `react-dom`, `next` are all
already declared in `frontend/package.json` and present in `node_modules`.

**Version verification:** `recharts` resolved version confirmed by reading
`frontend/node_modules/recharts/package.json` directly this session: `"version": "2.15.4"`, which
satisfies the project's pinned `^2.13.0` range in `frontend/package.json`. [VERIFIED: frontend/node_modules/recharts/package.json — read via `node -e "console.log(require('./node_modules/recharts/package.json').version)"` → `2.15.4`]

## Package Legitimacy Audit

No new external packages are introduced by this phase — `recharts` is already installed and
pinned; all other work uses framework built-ins (`fetch`, `EventSource`, React Context, Tailwind
utility classes). UI-SPEC (`03-UI-SPEC.md` Design System section) explicitly confirms: no shadcn
init, no icon library (hand-authored inline SVG instead), no new npm dependency for the small
icon set this phase needs (chat send, sidebar collapse chevron).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| recharts | npm | already installed, 2.15.4 resolved from pinned `^2.13.0` | high (existing project dependency) | github.com/recharts/recharts | OK | Approved — no change, already in use |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  ├─ EventSource ──────────────► GET /api/stream/telemetry (SSE, ~500ms cadence)
  │     │                              │
  │     ▼                              ▼
  │  useTelemetryStream            TelemetryCache (backend, unchanged)
  │  (snapshot, status,
  │   battery/altitude/speed
  │   history, capped)
  │     │
  │     ├──────────────► FleetRosterPanel (sparklines, row select)
  │     ├──────────────► FleetHeatmap (per-cell battery color)
  │     └──────────────► DetailPanel (battery/altitude/speed-over-time charts)
  │
  ├─ fetch (poll every N sec + on-action refetch) ──► GET /api/fleet
  │     │                                                   │
  │     ▼                                                   ▼
  │  FleetOpsProvider                              missions/router.py (unchanged)
  │  (remaining_kwh, energy_budget_kwh,
  │   active_mission_count,
  │   missionsById: accumulated map,
  │   selectedDroneId)
  │     │
  │     ├──────────────► Header (live budget, mission count, connection dot)
  │     ├──────────────► MissionsTable (all accumulated missions incl. delivered/recalled)
  │     ├──────────────► FleetHeatmap (energy_cost_kwh sizing)
  │     └──────────────► DetailPanel (current mission for selected drone)
  │
  ├─ fetch (mutating) ──► POST /api/fleet/missions ──┐
  │                     ► DELETE /api/fleet/missions/{drone_id} ─┤─► triggers FleetOpsProvider.refetch()
  │  DispatchBar ────────────────────────────────────┘             (D-02, D-07)
  │
  ├─ fetch ──► GET /api/fleet/history ──► EnergyBudgetChart (Recharts LineChart)
  │
  └─ fetch ──► POST /api/chat ──► chat/router.py
        │                              │
        ▼                              ▼
     ChatPanel                  generate_reply() + auto-executed
     (transcript, input,        missions/roster_changes via the
      loading state,            SAME service functions DispatchBar uses
      confirmation cards)             │
        │                             └─► on success, triggers
        └────────────────────────────────  FleetOpsProvider.refetch() (D-07)
```

### Recommended Project Structure

```
frontend/src/
├── app/
│   └── page.tsx                  # wraps tree in <FleetOpsProvider>, mounts all panels
├── components/
│   ├── Header.tsx                 # existing — wire to live FleetOpsProvider values
│   ├── FleetRosterPanel.tsx       # existing — add sparkline <td>, keep onSelect
│   ├── ConnectionDot.tsx          # existing — reused as-is
│   ├── DroneSparkline.tsx         # new — small Recharts LineChart, no axes
│   ├── DetailPanel.tsx            # new — FE-02
│   ├── FleetHeatmap.tsx           # new — FE-03, Recharts Treemap + custom content
│   ├── EnergyBudgetChart.tsx      # new — FE-04, Recharts LineChart
│   ├── MissionsTable.tsx          # new — FE-05
│   ├── DispatchBar.tsx            # new — FE-06
│   └── chat/
│       ├── ChatPanel.tsx          # new — FE-08 container (sidebar, collapse toggle)
│       ├── ChatMessage.tsx        # new — one transcript bubble
│       └── ConfirmationCard.tsx   # new — FE-09, D-06 format
├── lib/
│   ├── useTelemetryStream.ts      # existing — extend with altitude/speed history
│   ├── FleetOpsProvider.tsx       # new — D-01/D-02/D-07, missions accumulation (Critical Finding)
│   └── useChat.ts                 # new — POST /api/chat wrapper, loading/disabled state (D-08)
└── types/
    ├── telemetry.ts                # existing — unchanged
    ├── fleet.ts                    # new — Mission, FleetStatus, BudgetSnapshot types
    └── chat.ts                     # new — ChatResponse, MissionAction, RosterChange types
```

### Pattern 1: FleetOpsProvider (Context + poll + accumulate + refetch-on-action)

**What:** A single React Context provider wrapping the app, owning `remaining_kwh`,
`energy_budget_kwh`, `active_mission_count`, an accumulated `missionsById` map (see Critical
Finding), and `selectedDroneId`. Exposes a `refetch()` function that both the interval poll and
every mutating action (dispatch, recall, chat) call.

**When to use:** Any component needing fleet-wide state (Header, MissionsTable, FleetHeatmap,
DetailPanel, DispatchBar, ChatPanel) — all seven consumers, per D-01's rationale.

**Example:**
```typescript
// Source: derived from verified GET /api/fleet response shape
// (backend/app/missions/router.py:53-63) + D-01/D-02/D-07
"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

interface FleetOpsState {
  energyBudgetKwh: number;
  remainingKwh: number;
  activeMissionCount: number;
  missions: MissionRecord[];
  selectedDroneId: string | null;
  select: (droneId: string | null) => void;
  refetch: () => Promise<void>;
}

const FleetOpsContext = createContext<FleetOpsState | null>(null);

export function FleetOpsProvider({ children, pollIntervalMs = 5000 }: { children: React.ReactNode; pollIntervalMs?: number }) {
  const [budget, setBudget] = useState({ energyBudgetKwh: 0, remainingKwh: 0, activeMissionCount: 0 });
  const missionsRef = useRef<Map<string, MissionRecord>>(new Map());
  const [missions, setMissions] = useState<MissionRecord[]>([]);
  const [selectedDroneId, setSelectedDroneId] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    const res = await fetch("/api/fleet");
    const data = await res.json();
    setBudget({
      energyBudgetKwh: data.energy_budget_kwh,
      remainingKwh: data.remaining_kwh,
      activeMissionCount: data.active_mission_count,
    });
    missionsRef.current = mergeMissions(missionsRef.current, data.missions);
    setMissions(Array.from(missionsRef.current.values()));
  }, []);

  useEffect(() => {
    refetch();
    const id = setInterval(refetch, pollIntervalMs);
    return () => clearInterval(id);
  }, [refetch, pollIntervalMs]);

  return (
    <FleetOpsContext.Provider
      value={{ ...budget, missions, selectedDroneId, select: setSelectedDroneId, refetch }}
    >
      {children}
    </FleetOpsContext.Provider>
  );
}

export function useFleetOps() {
  const ctx = useContext(FleetOpsContext);
  if (!ctx) throw new Error("useFleetOps must be used within FleetOpsProvider");
  return ctx;
}
```

### Pattern 2: Recharts Treemap with custom content and click-to-select

**What:** FE-03's heatmap, sized by `energy_cost_kwh` (with D-10's 0.1 kWh floor for idle
drones), colored per D-11's 3-band thresholds, wired to `FleetOpsProvider.select()` on click.

**When to use:** `FleetHeatmap.tsx`.

**Example:**
```typescript
// Source: verified against installed frontend/node_modules/recharts/types/chart/Treemap.d.ts
// (Props: content?, onClick?: (node: TreemapNode) => void;
//  TreemapNode: { x, y, width, height, depth, index, name, value, [k: string]: any })
import { Treemap } from "recharts";

interface HeatmapDatum {
  name: string;       // drone_id
  value: number;       // energy_cost_kwh, floored at 0.1 for idle drones (D-10)
  batteryPct: number;  // extra field — flows through TreemapNode via [k: string]: any
}

function CellContent(props: any) {
  const { x, y, width, height, name, batteryPct } = props;
  const color = batteryPct >= 50 ? "#34d399" /* emerald-400 */
    : batteryPct >= 20 ? "#f2a900" /* ops.amber */
    : "#f87171" /* red-400 */;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color} stroke="#232a38" />
      {width > 40 && height > 20 && (
        <text x={x + 4} y={y + 14} fontSize={11} fill="#0a0e14" className="font-mono">
          {name}
        </text>
      )}
    </g>
  );
}

export function FleetHeatmap({ data, onSelect }: { data: HeatmapDatum[]; onSelect: (droneId: string) => void }) {
  return (
    <Treemap
      data={data}
      dataKey="value"
      content={<CellContent />}
      onClick={(node) => onSelect(node.name)}
    />
  );
}
```

### Pattern 3: Roster sparkline (compact Recharts LineChart)

**What:** A tiny per-row chart with no axes/grid, driven by `useTelemetryStream`'s per-drone
`history` array.

**When to use:** `DroneSparkline.tsx`, embedded as a `<td>` in `FleetRosterPanel.tsx`'s existing
row map.

**Example:**
```typescript
// Source: standard Recharts minimal-chart pattern (ResponsiveContainer + LineChart,
// axes/grid/tooltip omitted for a sparkline), applied to the verified history shape
// (frontend/src/lib/useTelemetryStream.ts:17, history.current: Record<string, number[]>)
import { LineChart, Line, ResponsiveContainer } from "recharts";

export function DroneSparkline({ points }: { points: number[] }) {
  const data = points.map((battery_pct, i) => ({ i, battery_pct }));
  return (
    <ResponsiveContainer width={80} height={24}>
      <LineChart data={data}>
        <Line type="monotone" dataKey="battery_pct" stroke="#17a2b8" dot={false} strokeWidth={1.5} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### Anti-Patterns to Avoid

- **Duplicating mission validation client-side (violates D-14):** Do not write a
  "can this drone launch?" check in `DispatchBar` before submitting. The backend is the single
  source of truth (`missions/service.py`); duplicating the logic risks drift (e.g. if
  `UNSAFE_TELEMETRY_STATUSES` changes server-side) and directly contradicts the locked decision.
- **Replacing `missionsById` wholesale on each poll:** Doing `setMissions(data.missions)` instead
  of merging (per the Critical Finding) silently drops every recalled/delivered mission from the
  table the instant its status changes — this is the exact bug the accumulation pattern exists to
  prevent.
- **Re-deriving ETA from `updated_at` + a fixed constant while ignoring live telemetry speed:**
  see Open Question 1 — a hand-rolled client ETA that ignores the backend's already-more-accurate
  `eta_minutes` is strictly worse without being simpler (both need the same distance/speed
  division; the client version just uses a staler speed value).
- **Fetching `GET /api/fleet` from multiple components independently:** Bypasses D-01/D-02
  entirely and produces N independent polling loops with N different staleness windows — all
  fleet/mission reads must go through `useFleetOps()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Treemap squarified layout math | A CSS-grid-based sized-rectangle layout | Recharts `Treemap` (D-09) | Treemap layout algorithms (squarify, slice-and-dice) are non-trivial to get right (aspect-ratio balancing); Recharts already ships a tested implementation the project already depends on |
| SSE reconnection/backoff | Custom retry/backoff logic around `EventSource` | Native `EventSource` (already in use) | Browsers implement automatic reconnection for `EventSource` natively; PLAN.md §6 explicitly calls this out as a reason SSE was chosen over WebSockets |
| Client-side global state coordination across 7 components | Manual prop-drilling or a home-grown pub/sub | React Context (`FleetOpsProvider`, D-01) | Context is purpose-built for this exact "many distant consumers, one source of truth" shape; a hand-rolled event bus would just reinvent it with worse React DevTools integration |

**Key insight:** Every hand-roll temptation in this phase (treemap math, SSE retry, global state
plumbing) already has a solution either already installed (Recharts) or already built-in (React
Context, `EventSource`) — the phase's actual novel work is the *data-shaping* layer
(`FleetOpsProvider`'s mission accumulation), not infrastructure.

## Common Pitfalls

### Pitfall 1: Assuming `GET /api/fleet` is the full mission history

**What goes wrong:** A missions table built by directly rendering `data.missions` from each poll
will silently lose any mission the moment it's recalled or delivered — the row just disappears,
which looks like a bug ("where did my mission go?") rather than working as designed.

**Why it happens:** The endpoint name (`/api/fleet`, not `/api/fleet/missions/history`) and its
general "fleet status" framing don't obviously signal "active only" — you have to read
`repository.list_active_missions`'s SQL to see the `WHERE status = 'en_route'` filter.

**How to avoid:** Use the client-side accumulation pattern in the Critical Finding section above;
never treat a `GET /api/fleet` response as the complete missions list.

**Warning signs:** A `recalled`-status row appears in the missions table for one poll interval
then vanishes on the next.

### Pitfall 2: Polling interval race with D-02's action-triggered refetch

**What goes wrong:** If the interval poll and an action-triggered refetch both fire close
together, `FleetOpsProvider`'s `refetch()` can run twice concurrently; if not idempotent (e.g. if
it naively replaced `missionsRef.current` mid-merge from two overlapping calls), a partially
merged state could flash.

**Why it happens:** `setInterval` and `refetch()` calls triggered by dispatch/recall/chat actions
are two independent triggers into the same async function with no in-flight guard.

**How to avoid:** Keep `refetch()` idempotent (each call independently merges the full active list
it received against the current accumulated map — order of completion doesn't matter since merges
are commutative for the "upsert active, mark-missing-as-delivered" logic). Optionally add a simple
in-flight guard (skip a poll tick if a refetch triggered by an action is already in progress) as a
minor optimization, not a correctness requirement.

**Warning signs:** Flickering status values in the UI immediately after a dispatch/recall action.

### Pitfall 3: SVG-only content inside Recharts `Treemap`

**What goes wrong:** Rendering HTML elements (`<div>`, `<span>`) inside the Treemap's `content`
render prop produces invalid SVG and React DOM warnings, since `Treemap` renders its children
inside an `<svg>` tree.

**Why it happens:** It's easy to reach for a `<div className="...">` out of habit when styling
with Tailwind, since every other component in this codebase uses HTML+Tailwind.

**How to avoid:** Use SVG primitives (`<rect>`, `<text>`, `<g>`) inside the custom `content`
component, as shown in Pattern 2 above; apply colors via `fill`/`stroke` attributes, not Tailwind
classes (Tailwind's `bg-*`/`text-*` utilities don't affect SVG `fill`).

**Warning signs:** React console warnings about unrecognized DOM properties, or cells rendering
with no visible color at all.

### Pitfall 4: Static export + no server-side data fetching

**What goes wrong:** Any attempt to fetch fleet data in a Server Component or `getServerSideProps`
-style pattern will fail silently or break the build, since `next.config.js` sets
`output: "export"` [VERIFIED: frontend/next.config.js — `output: "export"`, `images: { unoptimized: true }`] — there is no Node server at request time, only static files served by FastAPI.

**Why it happens:** Next.js's App Router defaults to Server Components; it's easy to accidentally
write a component without `"use client"` that tries to `fetch()` at render time.

**How to avoid:** Every new component that touches `FleetOpsProvider`, `useTelemetryStream`, or
does its own `fetch`/`EventSource` work must be a Client Component (`"use client"` at the top,
matching the existing `page.tsx` and `useTelemetryStream.ts` pattern).

**Warning signs:** Build-time errors referencing `fetch` or `window`/`document` not being
available; already-established as the pattern in every existing frontend file (`"use client"` is
line 1 of both `page.tsx` and `useTelemetryStream.ts`).

## Code Examples

### GET /api/fleet response shape (verified)

```json
// Source: backend/app/missions/router.py:53-63 (get_fleet_status), _mission_response (line 40-46)
{
  "energy_budget_kwh": 500.0,
  "remaining_kwh": 487.36,
  "active_mission_count": 2,
  "missions": [
    {
      "id": "…uuid…",
      "drone_id": "FALCON-03",
      "zone": "Riverside",
      "distance_km": 4.2,
      "energy_cost_kwh": 3.36,
      "status": "en_route",
      "updated_at": "2026-08-13T…Z",
      "eta_minutes": 6.3
    }
  ]
}
```

### GET /api/fleet/history response shape (verified)

```json
// Source: backend/app/missions/repository.py:238-243 (list_budget_snapshots)
{
  "snapshots": [
    { "remaining_kwh": 500.0, "recorded_at": "2026-08-13T…Z" },
    { "remaining_kwh": 487.36, "recorded_at": "2026-08-13T…Z" }
  ]
}
```

### Mission dispatch error response shape (verified)

```json
// Source: backend/app/missions/router.py:15-22 (_ERROR_STATUS),
// backend/app/missions/models.py:44-98 (MissionError hierarchy — reason attrs quoted verbatim)
// InsufficientBudgetError (422): {"reason": "insufficient_budget", "requested_kwh": 3.36, "remaining_kwh": 1.2}
// DroneAlreadyEnRouteError (409): {"reason": "drone_already_en_route"}
// UnknownDroneError (404): {"reason": "unknown_drone"}
// NoActiveMissionError (404, on recall of an idle drone): {"reason": "no_active_mission"}
```
The full reason set, quoted verbatim from `backend/app/missions/models.py:44-98`:
`"unknown_drone"`, `"drone_already_en_route"`, `"drone_unavailable"`, `"no_active_mission"`,
`"no_eligible_drone"`, `"insufficient_budget"`. D-14's inline error text should render the
`detail.reason` (and for `insufficient_budget`, optionally `requested_kwh`/`remaining_kwh`) — see
UI-SPEC Copywriting Contract for exact rendering ("{backend reason-coded message, verbatim}").

### POST /api/chat response shape (verified)

```json
// Source: backend/app/chat/router.py:188-193
{
  "message": "Launched FALCON-03 to Riverside. 2 drones now en route.",
  "missions": [
    { "drone_id": "FALCON-03", "action": "launch", "zone": "Riverside", "distance_km": 4.2 }
  ],
  "roster_changes": [],
  "errors": []
}
```
`missions[].action` is `"launch"` or `"recall"` (recall entries omit `zone`/`distance_km`)
[VERIFIED: backend/app/chat/router.py:50-83, `_execute_mission` return shapes]. `roster_changes[].action`
is `"add"` or `"remove"` [VERIFIED: backend/app/chat/router.py:86-96, `_execute_roster_change`].
`errors` is a flat array of human-readable strings (mission errors then roster errors,
concatenated) — not structured per-action, so D-06's failure badges for AI-issued actions must be
matched by position/heuristic parsing, or — simpler — treat every entry in `missions`/
`roster_changes` as a success card and render each `errors` string as a separate generic failure
card (no drone_id association available from the response shape alone; this is a known response
API limitation, not a frontend bug).

### GET /api/roster response shape (verified)

```json
// Source: backend/app/roster/router.py:31-49 (_entry_response, _TELEMETRY_FIELDS)
{
  "drones": [
    { "drone_id": "FALCON-01", "added_at": "2026-08-12T…Z",
      "battery_pct": 94.2, "altitude_m": 118.0, "speed_kmh": 38.5, "status": "in_flight" }
  ]
}
```
Used by `DispatchBar`'s drone dropdown (D-15) — note this endpoint's telemetry fields are a
point-in-time snapshot from whatever the cache held when the roster was queried, not live; prefer
sourcing the dropdown's drone list (IDs only) from here but battery/status coloring, if any, from
the live `useTelemetryStream` snapshot instead, for consistency with the rest of the UI.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — no prior frontend state-management pattern exists in this codebase | React Context via `FleetOpsProvider` | This phase (first introduction) | Establishes the first cross-component state pattern; all subsequent phases/features needing fleet-wide state should extend this provider, not create a second one |

**Deprecated/outdated:** Nothing in this phase's scope deprecates prior code — `Header`,
`FleetRosterPanel`, `ConnectionDot`, and `useTelemetryStream` are all extended, not replaced.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Exact Recharts `Treemap` custom-content example markup/patterns beyond the verified `.d.ts` prop shapes (e.g. official demo styling conventions) reflect common practice, not a source read this session — the official example page requires client-side JS rendering that WebFetch could not execute, and GitHub raw source paths attempted (`recharts.org` examples repo) returned 404 | Code Examples / Pattern 2 | Low — the `.d.ts` prop names (`x, y, width, height, name, value`, `onClick`, `content`) were verified directly against the installed package, which is the load-bearing contract; only the illustrative "how a typical custom-content component is structured" framing is unverified, and it follows directly from the typed props |
| A2 | `MissionRecord`/`fleet.ts` TypeScript types proposed in Recommended Project Structure are new file suggestions, not read from any existing repo file (no `types/fleet.ts` exists yet) | Architecture Patterns / Recommended Project Structure | Low — field names are all drawn from the verified JSON response shapes above; only the TS interface's existence and exact shape/name is a planning suggestion |
| A3 | 5-second poll interval (`pollIntervalMs = 5000`) in the `FleetOpsProvider` example is an illustrative default, not specified by CONTEXT.md or UI-SPEC (both leave the interval to the planner's discretion) | Architecture Patterns / Pattern 1 | Low — purely a tuning knob; too-short intervals waste requests, too-long intervals make the missions table feel stale after dispatch/recall (though D-02's refetch-on-action covers the common case regardless of polling cadence) |

**If this table is empty:** N/A — see entries above; all are low-risk illustrative/tuning details,
not load-bearing factual claims about the existing codebase or API contracts (all of which were
verified by reading source this session).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | `npm run dev` / `npm run build` for local iteration on this phase | ✓ (assumed dev environment per `.claude/CLAUDE.md` platform requirements) | 20+ required | — |
| recharts (npm package) | FE-01, FE-02, FE-03, FE-04 | ✓ | 2.15.4 installed (verified in `node_modules`) | — |
| Backend endpoints (`GET /api/fleet`, `/api/fleet/history`, `/api/roster`, `/api/stream/telemetry`, `POST/DELETE /api/fleet/missions`, `POST /api/chat`) | All FE-0x requirements | ✓ (Phase 1 & 2 complete and verified per STATE.md) | — | — |

**Missing dependencies with no fallback:** none identified.

**Missing dependencies with fallback:** none identified — this phase has no new external
dependencies; all backend contracts it consumes are already built and verified (STATE.md: "Phase
2 verified... 300/300 backend tests, ruff clean").

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 2.1.0 (declared in `frontend/package.json`) + `@testing-library/react` 16.0.0 |
| Config file | **none — Wave 0 gap.** No `vitest.config.ts`/`vite.config.ts` exists in `frontend/`. |
| Quick run command | `npm test` (currently runs `vitest run` with zero config — will use Vitest defaults, which default to `node` test environment, not `jsdom`) |
| Full suite command | `npm test` (same script; no separate "full" script defined yet) |

**Gap detail** [VERIFIED: frontend/package.json — `"test": "vitest run"`, devDependencies list
does not include `jsdom`, `@testing-library/jest-dom`, or `@vitejs/plugin-react`]: `jsdom` is
present in `node_modules` only as an *optional peer dependency of Vitest itself*
(`"jsdom": "*"` under Vitest's `peerDependenciesMeta`, confirmed via `package-lock.json`), not as
a project-declared dependency — meaning a clean `npm ci` is not guaranteed to install it
consistently, and no `vitest.config.ts` currently sets `test.environment: "jsdom"` to use it even
if present. Any component test needing `document`/`window` (all of them, since these are React
DOM components) will fail under Vitest's default `node` environment without this fixed.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FE-01 | Sparkline renders from history array | unit (render) | `npx vitest run DroneSparkline` | ❌ Wave 0 |
| FE-02 | Detail panel shows battery/altitude/speed + mission or empty state | unit (render) | `npx vitest run DetailPanel` | ❌ Wave 0 |
| FE-03 | Heatmap renders cells sized/colored correctly, idle-drone floor applied | unit (render) | `npx vitest run FleetHeatmap` | ❌ Wave 0 |
| FE-04 | Budget chart renders from snapshots array | unit (render) | `npx vitest run EnergyBudgetChart` | ❌ Wave 0 |
| FE-05 | Missions table shows accumulated missions incl. recalled/delivered | unit (`mergeMissions` logic) | `npx vitest run FleetOpsProvider` | ❌ Wave 0 |
| FE-06 | Dispatch/recall calls correct endpoint, surfaces backend error verbatim | unit (mocked fetch) | `npx vitest run DispatchBar` | ❌ Wave 0 |
| FE-07 | Header reflects live values, not hardcoded | unit (render) | `npx vitest run Header` | ❌ Wave 0 |
| FE-08 | Chat input disabled while loading, transcript scrolls | unit (render + interaction) | `npx vitest run ChatPanel` | ❌ Wave 0 |
| FE-09 | Confirmation cards render for missions/roster_changes/errors | unit (render) | `npx vitest run ConfirmationCard` | ❌ Wave 0 |

Note: TEST-03 (the comprehensive frontend RTL suite) is formally scoped to **Phase 4** per
`.planning/REQUIREMENTS.md`'s traceability table, not this phase. The Wave 0 setup below is
recommended regardless, because (a) Phase 4 will need it anyway and standing it up now avoids
redoing the decision later, and (b) `nyquist_validation` is enabled for this project — some level
of automated per-task verification during Phase 3 execution is expected even if the *exhaustive*
TEST-03 suite is deferred. Recommend lightweight smoke/render tests per new component during
Phase 3 (sampling, not exhaustive coverage), with full coverage completed in Phase 4.

### Sampling Rate

- **Per task commit:** `npm run build` (Next.js static export must succeed) + `npm run lint` +
  `npx vitest run <ComponentName>` for the component just touched, once Wave 0 config exists
- **Per wave merge:** `npm test` (full current suite) + `npm run build`
- **Phase gate:** Full suite green before `/gsd-verify-work`; manual UAT against UI-SPEC's 6
  dimensions (Copywriting, Visuals, Color, Typography, Spacing, Registry Safety) per its
  Checker Sign-Off section

### Wave 0 Gaps

- [ ] `frontend/vitest.config.ts` — set `test.environment: "jsdom"`, `test.setupFiles`, and the
  `@/*` path alias (mirroring `tsconfig.json`'s `paths`) so imports resolve identically to Next.js
- [ ] `frontend/vitest.setup.ts` — import `@testing-library/jest-dom`-style matchers (needs adding
  `@testing-library/jest-dom` to devDependencies) and mock `window.EventSource`/`window.fetch` as
  needed per-test
- [ ] `frontend/package.json` devDependencies — add `jsdom`, `@testing-library/jest-dom` (both
  currently absent as declared dependencies); confirm whether `@testing-library/user-event` is
  needed for D-08's disabled-input interaction test
- [ ] Framework install: `npm install --save-dev jsdom @testing-library/jest-dom` (run inside
  `frontend/`)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Explicitly out of scope project-wide (single-operator demo, no auth — `.planning/REQUIREMENTS.md` Out of Scope table) |
| V3 Session Management | No | No sessions/cookies introduced by this phase |
| V4 Access Control | No | No access-control surface added — all endpoints are already open, unauthenticated, same-origin |
| V5 Input Validation | Yes | Dispatch bar's `zone`/`distance_km` fields are validated server-side by Pydantic (`LaunchMissionRequest`, `distance_km: float = Field(gt=0)` [VERIFIED: backend/app/missions/router.py:25-28]) — frontend must not skip client-side basic sanity (e.g. HTML5 `required`/`min` attributes as UX affordances) but must never treat client validation as authoritative (D-14 already establishes this) |
| V6 Cryptography | No | No cryptographic operations in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected XSS via chat transcript rendering LLM-generated `message` text or user-typed `message` as raw HTML | Tampering / Information Disclosure | React's default JSX text-node rendering already escapes strings — **never** use `dangerouslySetInnerHTML` to render `reply.message`, user chat input, or any `zone`/`drone_id` free-text field anywhere in this phase's new components |
| Free-text `zone` field (D-15) used unsanitized in a URL, log line, or (future) HTML context | Tampering | Same as above — render as plain text via JSX interpolation; the backend already stores it as a plain SQL parameter (verified: `_txn` uses parameterized `?` placeholders throughout `missions/repository.py`, no string concatenation) |
| Overly large/malformed `distance_km` values reaching the display layer (e.g. `NaN`, `Infinity` from a future compromised or buggy chat action) | Tampering | Backend already guards this — `chat/router.py`'s `_execute_mission` explicitly checks `math.isfinite(action.distance_km)` before calling `launch_mission` [VERIFIED: backend/app/chat/router.py:60-65] (this was a real bug fixed in Phase 2's code review per STATE.md); frontend display code should still defensively format with `.toFixed()` guards (existing precedent: `FleetRosterPanel.tsx`'s `reading.battery_pct.toFixed(1)`) rather than assume all values are always well-formed forever |

## Sources

### Primary (HIGH confidence — read directly from the working tree this session)

- `frontend/src/lib/useTelemetryStream.ts`, `frontend/src/types/telemetry.ts`,
  `frontend/src/components/{Header,FleetRosterPanel,ConnectionDot}.tsx`, `frontend/src/app/page.tsx`,
  `frontend/src/app/layout.tsx`, `frontend/tailwind.config.ts`, `frontend/next.config.js`,
  `frontend/package.json`, `frontend/tsconfig.json`
- `backend/app/missions/{router,service,repository,models,scheduler}.py`
- `backend/app/roster/{router,models}.py`
- `backend/app/chat/{router,models}.py`
- `backend/app/db/schema.py`
- `frontend/node_modules/recharts/types/{index,chart/Treemap,util/types}.d.ts` (installed package
  source, version 2.15.4 confirmed via `node_modules/recharts/package.json`)
- `.planning/phases/03-frontend-buildout/{03-CONTEXT.md, 03-UI-SPEC.md}`
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/codebase/{STRUCTURE.md,CONVENTIONS.md}`

### Secondary (MEDIUM confidence)

- npm registry (`npm view recharts version`, `npm view recharts@2.13.0 version
  dependencies.recharts-scale`) — confirmed 2.13.0 exists on the registry and the installed
  2.15.4 satisfies the pinned range

### Tertiary (LOW confidence)

- WebSearch results on general Recharts Treemap/LineChart usage patterns (result summaries only,
  not fetched source) — used only as background context; all load-bearing prop names/types for
  code examples were separately verified against the installed package's `.d.ts` files (Primary)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; recharts version and API surface verified directly
  against the installed package
- Architecture: HIGH — `FleetOpsProvider` pattern and mission-accumulation logic derived directly
  from reading the actual backend endpoint behavior (repository/router/scheduler source), not
  assumed
- Pitfalls: HIGH — all four pitfalls trace to a specific verified code behavior (active-only
  missions filter, static export config, Treemap SVG requirement per installed types, existing
  `"use client"` convention)

**Research date:** 2026-08-13
**Valid until:** 30 days (stable, already-pinned dependency stack; re-verify if `recharts` is
bumped past `2.x` or if Phase 4's Docker/static-export work changes `next.config.js`)
