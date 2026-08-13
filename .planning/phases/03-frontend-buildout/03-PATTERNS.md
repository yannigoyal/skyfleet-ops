# Phase 3: Frontend Buildout - Pattern Map

**Mapped:** 2026-08-13
**Files analyzed:** 16 (7 new components, 3 new lib/hook files, 2 new type files, 1 extended hook, 3 extended existing components)
**Analogs found:** 16 / 16 (RESEARCH.md already contains verified code examples for several; this map adds concrete excerpts from the actual current codebase files)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `frontend/src/lib/FleetOpsProvider.tsx` | provider | request-response (polling) | `frontend/src/lib/useTelemetryStream.ts` | role-match (hook→provider, same client-fetch-and-accumulate shape) |
| `frontend/src/lib/useChat.ts` | hook | request-response | `frontend/src/lib/useTelemetryStream.ts` | role-match (client hook wrapping an async I/O source) |
| `frontend/src/types/fleet.ts` | type/config | n/a | `frontend/src/types/telemetry.ts` | exact (same file role: plain TS interfaces mirroring a backend `to_dict()`) |
| `frontend/src/types/chat.ts` | type/config | n/a | `frontend/src/types/telemetry.ts` | exact |
| `frontend/src/components/DroneSparkline.tsx` | component | transform (render) | `frontend/src/components/ConnectionDot.tsx` | role-match (small presentational component, no local state) |
| `frontend/src/components/DetailPanel.tsx` | component | request-response | `frontend/src/components/FleetRosterPanel.tsx` | exact (reads snapshot/history, renders per-drone data) |
| `frontend/src/components/FleetHeatmap.tsx` | component | transform (render) | `frontend/src/components/FleetRosterPanel.tsx` | role-match (renders a collection from context, click-to-select) |
| `frontend/src/components/EnergyBudgetChart.tsx` | component | request-response | `frontend/src/components/FleetRosterPanel.tsx` | role-match (fetches/derives a series, renders it) |
| `frontend/src/components/MissionsTable.tsx` | component | CRUD (read) | `frontend/src/components/FleetRosterPanel.tsx` | exact (tabular render of a live-updating collection) |
| `frontend/src/components/DispatchBar.tsx` | component | CRUD (write) | `frontend/src/components/FleetRosterPanel.tsx` (for markup/styling only) | partial (no existing form/mutation component in repo) |
| `frontend/src/components/chat/ChatPanel.tsx` | component | request-response | `frontend/src/components/Header.tsx` (props/layout convention only) | partial (no existing chat/sidebar component in repo) |
| `frontend/src/components/chat/ChatMessage.tsx` | component | transform (render) | `frontend/src/components/ConnectionDot.tsx` | role-match |
| `frontend/src/components/chat/ConfirmationCard.tsx` | component | transform (render) | `frontend/src/components/ConnectionDot.tsx` | role-match |
| `frontend/src/lib/useTelemetryStream.ts` (extend) | hook | streaming | itself (existing file) | exact — extend in place |
| `frontend/src/components/Header.tsx` (extend) | component | request-response | itself (existing file) | exact — wire live props, no markup change |
| `frontend/src/components/FleetRosterPanel.tsx` (extend) | component | request-response | itself (existing file) | exact — add sparkline `<td>` |
| `frontend/src/app/page.tsx` (extend) | component (page) | request-response | itself (existing file) | exact — wrap in `FleetOpsProvider`, mount new panels |

## Pattern Assignments

### `frontend/src/lib/FleetOpsProvider.tsx` (provider, request-response/polling)

**Analog:** `frontend/src/lib/useTelemetryStream.ts` (full file, 42 lines — read above)

**Imports pattern** (`useTelemetryStream.ts` lines 1-4):
```typescript
"use client";

import { useEffect, useRef, useState } from "react";
import type { TelemetrySnapshot } from "@/types/telemetry";
```
Copy this exact shape for the provider: `"use client"` directive first, then React hooks, then a local `@/types/*` import (new `@/types/fleet.ts`).

**Core client-fetch-and-accumulate pattern** (`useTelemetryStream.ts` lines 14-42, full function):
```typescript
export function useTelemetryStream(maxHistoryPoints = 120) {
  const [snapshot, setSnapshot] = useState<TelemetrySnapshot>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const history = useRef<Record<string, number[]>>({});

  useEffect(() => {
    const source = new EventSource("/api/stream/telemetry");
    source.onopen = () => setStatus("connected");
    source.onerror = () => setStatus("disconnected");
    source.onmessage = (event) => {
      setStatus("connected");
      const data: TelemetrySnapshot = JSON.parse(event.data);
      setSnapshot(data);
      for (const [droneId, reading] of Object.entries(data)) {
        const points = history.current[droneId] ?? [];
        points.push(reading.battery_pct);
        if (points.length > maxHistoryPoints) points.shift();
        history.current[droneId] = points;
      }
    };
    return () => source.close();
  }, [maxHistoryPoints]);

  return { snapshot, status, history: history.current };
}
```
`FleetOpsProvider` follows the same shape (state + ref-accumulator + effect that establishes the data source + cleanup) but swaps `EventSource` for `fetch` on an interval, per RESEARCH.md's fully-worked Pattern 1 example (`03-RESEARCH.md` lines 437-494) — use that verified example verbatim as the starting point; it already matches this repo's `"use client"` + hooks-only, no-external-state-library convention. Export both `FleetOpsProvider` and a `useFleetOps()` accessor hook (mirrors `useTelemetryStream` being the sole way components read telemetry — no component should call `fetch("/api/fleet")` directly, matching the Anti-Pattern warning in RESEARCH.md).

**Docstring convention** (`useTelemetryStream.ts` lines 8-13):
```typescript
/**
 * Subscribes to GET /api/stream/telemetry via EventSource and keeps the
 * latest snapshot plus a per-drone battery history (for sparklines), both
 * accumulated client-side since mount — the backend only ever sends the
 * latest reading, matching the SSE contract in planning/PLAN.md section 6.
 */
```
Use the same one-paragraph docstring convention above `FleetOpsProvider`, citing the CONTEXT.md decision IDs (D-01/D-02/D-07) it implements, per `.claude/CLAUDE.md`'s "design decisions documented in module docstrings" rule.

---

### `frontend/src/lib/useTelemetryStream.ts` (extend in place)

**Current full file** — read above (42 lines). Extension per RESEARCH.md Open Question 2 recommendation: add parallel `altitudeHistory`/`speedHistory` refs using the exact same push/shift/cap block, duplicated per field (not restructuring `history`'s existing shape, since `FleetRosterPanel`'s future sparkline consumer depends on it staying `Record<string, number[]>`):
```typescript
const altitudeHistory = useRef<Record<string, number[]>>({});
const speedHistory = useRef<Record<string, number[]>>({});
// inside onmessage, alongside the existing battery_pct push:
const altPoints = altitudeHistory.current[droneId] ?? [];
altPoints.push(reading.altitude_m);
if (altPoints.length > maxHistoryPoints) altPoints.shift();
altitudeHistory.current[droneId] = altPoints;
// same for speed_kmh -> speedHistory
```
Return `{ snapshot, status, history, altitudeHistory: altitudeHistory.current, speedHistory: speedHistory.current }`.

---

### `frontend/src/components/FleetRosterPanel.tsx` (extend — add sparkline column)

**Full current file** — read above (79 lines). Key excerpts to extend, not replace:

**Row-map pattern** (lines 43-67) — add a new `<td>` inside the existing `<tr>` map, after the Speed column and before Status (or per UI-SPEC ordering), calling the new `DroneSparkline`:
```typescript
<td className="px-4 py-2">
  <DroneSparkline points={history[reading.drone_id] ?? []} />
</td>
```
`history` must be threaded in as a new prop (`Props` interface at lines 17-21) alongside `snapshot`/`selectedDroneId`/`onSelect` — the component is already a pure-props renderer with no local state, so this is additive only.

**Color-threshold precedent** (lines 11-15, `batteryColor()`):
```typescript
function batteryColor(pct: number): string {
  if (pct <= 20) return "text-red-400";
  if (pct <= 50) return "text-ops-amber";
  return "text-emerald-400";
}
```
This is the **authoritative source** for D-11/UI-SPEC's 3-band threshold — copy the exact three color tokens (`red-400`, `ops-amber`, `emerald-400`) into `FleetHeatmap.tsx`'s cell coloring rather than inventing new ones or using `ops.teal` (RESEARCH.md explicitly flags this correction).

**Table shell/empty-state pattern** (lines 28-41, 68-74) — reuse this exact `rounded-lg border border-ops-border bg-ops-panel` panel shell + header bar + empty-state row (`Waiting for telemetry…`) convention for `MissionsTable.tsx`'s panel chrome and its own empty state (e.g. "No missions yet").

---

### `frontend/src/components/Header.tsx` (extend — wire live props only)

**Full current file** — read above (28 lines). No markup changes needed. The only change is at the call site in `page.tsx`.

**Props/render pattern already correct** (lines 4-8, 17-25):
```typescript
interface Props {
  connectionStatus: ConnectionStatus;
  energyBudgetKwh: number;
  activeMissionCount: number;
}
...
<div className="text-slate-300">
  Energy Budget: <span className="font-mono text-ops-teal">{energyBudgetKwh.toFixed(1)} kWh</span>
</div>
<div className="text-slate-300">
  Active Missions: <span className="font-mono text-ops-teal">{activeMissionCount}</span>
</div>
<ConnectionDot status={connectionStatus} />
```
Use this exact `label: <span className="font-mono text-ops-teal">value</span>` inline pattern for any new header stat if FE-07/UI-SPEC calls for one. Also add a "Remaining" figure alongside budget if UI-SPEC requires it, using the identical span/class structure.

---

### `frontend/src/app/page.tsx` (extend — wrap in provider, mount new panels)

**Full current file** — read above (33 lines). Structural pattern to extend:
```typescript
"use client";
import { useState } from "react";
import { Header } from "@/components/Header";
import { FleetRosterPanel } from "@/components/FleetRosterPanel";
import { useTelemetryStream } from "@/lib/useTelemetryStream";

export default function Home() {
  const { snapshot, status } = useTelemetryStream();
  const [selectedDroneId, setSelectedDroneId] = useState<string | null>(null);
  return (
    <div className="flex min-h-screen flex-col">
      <Header connectionStatus={status} energyBudgetKwh={500.0} activeMissionCount={0} />
      <main className="grid flex-1 grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><FleetRosterPanel ... /></div>
        <aside className="rounded-lg border border-ops-border bg-ops-panel p-4 text-sm text-slate-400">
          ...
        </aside>
      </main>
    </div>
  );
}
```
New structure: wrap everything in `<FleetOpsProvider>`, replace the hardcoded `energyBudgetKwh={500.0}` / `activeMissionCount={0}` with values pulled from `useFleetOps()`, replace the placeholder `<aside>` with the real `<ChatPanel />`, and add the new panels (`DetailPanel`, `FleetHeatmap`, `EnergyBudgetChart`, `MissionsTable`, `DispatchBar`) into the `<main>` grid — reuse the existing `grid grid-cols-1 gap-4 p-6 lg:grid-cols-3` container convention and `rounded-lg border border-ops-border bg-ops-panel` panel-shell class throughout for visual consistency (this is the single dark-panel idiom used by every existing component).

---

### `frontend/src/components/ConnectionDot.tsx` (analog for small presentational components)

**Full current file** — read above (23 lines):
```typescript
import type { ConnectionStatus } from "@/lib/useTelemetryStream";

const COLORS: Record<ConnectionStatus, string> = {
  connected: "bg-emerald-500",
  connecting: "bg-ops-amber",
  disconnected: "bg-red-500",
};
const LABELS: Record<ConnectionStatus, string> = { ... };

export function ConnectionDot({ status }: { status: ConnectionStatus }) {
  return ( ... );
}
```
This lookup-table + tiny-pure-component pattern (`Record<UnionType, string>` constants declared module-level, above a stateless function component) is the template for `DroneSparkline.tsx`, `ChatMessage.tsx`, and `ConfirmationCard.tsx` — all are small, prop-driven, no local state, no `"use client"` needed unless they use hooks.

---

### `frontend/src/types/telemetry.ts` (analog for new type files)

**Full current file** — read above (16 lines):
```typescript
// Mirrors backend/app/telemetry/models.py::TelemetryUpdate.to_dict()
export type DroneStatus = "idle" | "in_flight" | "charging" | "low_battery" | "offline";

export interface TelemetryReading {
  drone_id: string;
  battery_pct: number;
  ...
}
export type TelemetrySnapshot = Record<string, TelemetryReading>;
```
Convention: a one-line comment citing the exact backend source file/method the type mirrors, then plain `interface`/`type` declarations, snake_case field names matching the JSON wire format exactly (no camelCase translation layer). Apply identically to:
- `frontend/src/types/fleet.ts` — `// Mirrors backend/app/missions/router.py::_mission_response() and get_fleet_status()`, defining `Mission`/`MissionStatus`/`FleetStatus`/`BudgetSnapshot` using the exact field names verified in RESEARCH.md's Code Examples section (`energy_budget_kwh`, `remaining_kwh`, `active_mission_count`, `eta_minutes`, etc.)
- `frontend/src/types/chat.ts` — `// Mirrors backend/app/chat/router.py chat response shape`, defining `ChatResponse { message: string; missions: ChatMissionAction[]; roster_changes: ChatRosterChange[]; errors: string[] }`.

---

## Shared Patterns

### Dark panel shell
**Source:** `frontend/src/components/FleetRosterPanel.tsx:28` / `frontend/src/app/page.tsx:26`
**Apply to:** every new panel component (`DetailPanel`, `FleetHeatmap`, `EnergyBudgetChart`, `MissionsTable`, `DispatchBar`, `ChatPanel`)
```typescript
<div className="rounded-lg border border-ops-border bg-ops-panel">
  <div className="border-b border-ops-border px-4 py-2 text-sm font-semibold text-slate-300">
    {/* panel title */}
  </div>
  {/* panel body */}
</div>
```

### Battery 3-band color thresholds
**Source:** `frontend/src/components/FleetRosterPanel.tsx:11-15`
**Apply to:** `FleetHeatmap.tsx` cell coloring, `DetailPanel.tsx` battery readout
```typescript
function batteryColor(pct: number): string {
  if (pct <= 20) return "text-red-400";
  if (pct <= 50) return "text-ops-amber";
  return "text-emerald-400";
}
```
For SVG contexts (Treemap cells), use the hex equivalents already verified in RESEARCH.md Pattern 2: `#34d399` (emerald-400), `#f2a900` (ops.amber), `#f87171` (red-400) — Tailwind `text-*`/`bg-*` classes do not apply inside `<svg>` `fill`/`stroke` attributes (see RESEARCH.md Pitfall 3).

### Flash-on-change animation classes
**Source:** `frontend/src/components/FleetRosterPanel.tsx:44-49`, `frontend/tailwind.config.ts:17-30`
**Apply to:** any new row/cell that should flash on telemetry update (already defined, do not redefine)
```typescript
const flashClass =
  reading.battery_direction === "draining" ? "animate-flash-drain"
  : reading.battery_direction === "charging" ? "animate-flash-charge"
  : "";
```

### `"use client"` directive requirement
**Source:** `frontend/src/lib/useTelemetryStream.ts:1`, `frontend/src/app/page.tsx:1`
**Apply to:** every new component/hook touching `FleetOpsProvider`, `useTelemetryStream`, `fetch`, or `EventSource` (static export has no server runtime — see RESEARCH.md Pitfall 4)

### `@/*` import alias, no relative `../../` paths
**Source:** all existing files (e.g. `frontend/src/components/Header.tsx:1`, `import type { ConnectionStatus } from "@/lib/useTelemetryStream";`)
**Apply to:** all new files — `@/components/*`, `@/lib/*`, `@/types/*`

### Numeric display formatting guard
**Source:** `frontend/src/components/FleetRosterPanel.tsx:60,62-63` — `reading.battery_pct.toFixed(1)`, `reading.altitude_m.toFixed(0)`, `reading.speed_kmh.toFixed(0)`
**Apply to:** `DetailPanel.tsx`, `MissionsTable.tsx`, `DispatchBar.tsx` — always `.toFixed(n)` numeric fields before rendering (RESEARCH.md's Security Domain section calls this out explicitly for `distance_km`/chat-sourced values, citing this exact precedent)

### No `dangerouslySetInnerHTML`
**Source:** RESEARCH.md Security Domain (no existing codebase precedent needed — this is a negative pattern)
**Apply to:** `ChatMessage.tsx` (rendering `reply.message`), `ConfirmationCard.tsx`, `DispatchBar.tsx` (rendering `zone` free text) — render all LLM/user-originated strings as plain JSX text nodes only

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/components/DispatchBar.tsx` | component | CRUD (write) | No existing form/mutation component in the frontend yet — this is the first component to issue `POST`/`DELETE` requests. Use RESEARCH.md's verified error-shape (`_ERROR_STATUS`, `MissionError.reason`) for the inline-error rendering; follow the shared dark-panel shell + `"use client"` + `@/*` import conventions above for everything else. |
| `frontend/src/components/chat/ChatPanel.tsx`, `ChatMessage.tsx`, `ConfirmationCard.tsx` | component | request-response | No chat/sidebar UI exists yet (`page.tsx`'s current `<aside>` is a static placeholder, not a real analog). Use RESEARCH.md's verified `POST /api/chat` response shape (Code Examples section) and D-05/D-06/D-08 for behavior; use the shared dark-panel shell and `ConnectionDot`-style small-component pattern for structure. |
| `frontend/src/components/FleetHeatmap.tsx` | component | transform (render) | No existing chart/visualization component (Recharts is installed but unused in any current `.tsx` file). Use RESEARCH.md Pattern 2 (fully verified against installed `recharts` `.d.ts` types) as the primary source; `FleetRosterPanel.tsx`'s color thresholds and click-to-select (`onSelect` prop) supply the remaining conventions. |
| `frontend/src/components/EnergyBudgetChart.tsx` | component | request-response | Same as above — no existing chart component; use standard Recharts `LineChart`/`XAxis`/`Line` per RESEARCH.md's `GET /api/fleet/history` shape and Architecture Patterns section. |

## Metadata

**Analog search scope:** `frontend/src/` (components, lib, types, app) — entire existing frontend tree (7 files total pre-Phase-3)
**Files scanned:** 7 existing frontend source files (all read in full — none exceed 80 lines) + `frontend/tailwind.config.ts`, `frontend/next.config.js` (config) + `03-CONTEXT.md`, `03-RESEARCH.md` (upstream inputs, RESEARCH.md already verified backend response shapes and Recharts type defs directly)
**Pattern extraction date:** 2026-08-13
