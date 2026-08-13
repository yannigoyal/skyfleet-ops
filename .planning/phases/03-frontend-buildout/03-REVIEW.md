---
phase: 03-frontend-buildout
reviewed: 2026-08-13T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - .gitignore
  - frontend/package.json
  - frontend/src/app/page.test.tsx
  - frontend/src/app/page.tsx
  - frontend/src/components/ConnectionDot.test.tsx
  - frontend/src/components/DetailPanel.test.tsx
  - frontend/src/components/DetailPanel.tsx
  - frontend/src/components/DispatchBar.test.tsx
  - frontend/src/components/DispatchBar.tsx
  - frontend/src/components/DroneSparkline.test.tsx
  - frontend/src/components/DroneSparkline.tsx
  - frontend/src/components/EnergyBudgetChart.test.tsx
  - frontend/src/components/EnergyBudgetChart.tsx
  - frontend/src/components/FleetHeatmap.test.tsx
  - frontend/src/components/FleetHeatmap.tsx
  - frontend/src/components/FleetRosterPanel.tsx
  - frontend/src/components/Header.test.tsx
  - frontend/src/components/Header.tsx
  - frontend/src/components/MissionsTable.test.tsx
  - frontend/src/components/MissionsTable.tsx
  - frontend/src/components/chat/ChatMessage.tsx
  - frontend/src/components/chat/ChatPanel.test.tsx
  - frontend/src/components/chat/ChatPanel.tsx
  - frontend/src/components/chat/ConfirmationCard.test.tsx
  - frontend/src/components/chat/ConfirmationCard.tsx
  - frontend/src/lib/FleetOpsProvider.test.tsx
  - frontend/src/lib/FleetOpsProvider.tsx
  - frontend/src/lib/useChat.test.tsx
  - frontend/src/lib/useChat.ts
  - frontend/src/lib/useTelemetryStream.test.ts
  - frontend/src/lib/useTelemetryStream.ts
  - frontend/src/types/chat.ts
  - frontend/src/types/fleet.ts
  - frontend/vitest.config.ts
  - frontend/vitest.setup.ts
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-08-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Reviewed the frontend buildout for SkyFleet Ops — the fleet console page, roster/detail/dispatch/heatmap/budget/missions panels, the AI flight-director chat sidebar, and the two data hooks (`useTelemetryStream`, `useChat`) plus the shared `FleetOpsProvider` context. Test coverage is broad and the components generally match the documented design decisions (D-01 through D-14) referenced in their docstrings.

The most significant problem is in `FleetOpsProvider.refetch()`, the single source of truth for `GET /api/fleet` and `GET /api/roster` data consumed by the header, dispatch bar, roster panel, detail panel, heatmap, and missions table. Unlike its sibling data-fetchers (`EnergyBudgetChart`, `useChat`), it never checks `res.ok` and has no `try/catch`, so a transient backend error (500, or a non-JSON error body) is not just unhandled — it flows straight into React state as `undefined` values typed as `number | null`, and `Header.formatKwh()` then calls `.toFixed(1)` on `undefined`, throwing and crashing the whole console with no error boundary in place. This is provable from the code as written and is not covered by any existing test (`FleetOpsProvider.test.tsx` only exercises the happy-path race-condition scenario).

Several smaller robustness/consistency gaps follow the same pattern (missing error handling where a sibling component already established the convention), plus two minor code-quality nits.

## Critical Issues

### CR-01: FleetOpsProvider.refetch() has no error handling — a single failed request crashes the console

**File:** `frontend/src/lib/FleetOpsProvider.tsx:82-102`
**Issue:** `refetch()` is the sole reader of `GET /api/fleet` and `GET /api/roster` (per its own docstring, D-01), called on mount and via `setInterval` every 5s, and again after every dispatch/recall/chat action. It never checks `fleetRes.ok` / `rosterRes.ok`, and has no `try/catch` around the `fetch`/`.json()` calls:

```ts
const [fleetRes, rosterRes] = await Promise.all([
  fetch("/api/fleet"),
  fetch("/api/roster"),
]);
const fleetData: FleetStatus = await fleetRes.json();
const rosterData: { drones: RosterDrone[] } = await rosterRes.json();
```

If the backend returns a non-2xx response (e.g. a 500 with `{"detail": "..."}`), `fleetData.energy_budget_kwh` / `fleetData.remaining_kwh` are `undefined`, and that `undefined` is written straight into `budget` state that is typed `number | null`:

```ts
setBudget({
  energyBudgetKwh: fleetData.energy_budget_kwh, // undefined, not null
  remainingKwh: fleetData.remaining_kwh,
  activeMissionCount: fleetData.active_mission_count,
});
```

`Header.formatKwh()` only special-cases `null`:

```ts
function formatKwh(value: number | null): string {
  return value === null ? "—" : value.toFixed(1);
}
```

`undefined.toFixed(1)` throws a `TypeError`, and with no error boundary anywhere in `page.tsx`, this crashes the entire `Console` render on the very next poll tick after any transient backend hiccup. Separately, if the network request itself rejects (backend down, DNS failure) or the response body isn't JSON, the unhandled exception inside the async `refetch()` becomes an unhandled promise rejection on every 5s interval tick — `loaded` never gets set on the very first failed mount call, leaving the header/roster/dispatch bar stuck on `—`/empty state indefinitely even though later polls could otherwise recover.

This is the same class of problem `EnergyBudgetChart.tsx` (`res.ok` check + try/catch + inline error message, with a dedicated Test 5) and `useChat.ts` (try/catch producing a `system` transport-error turn, with dedicated Tests 5 & 6) already solved correctly elsewhere in this same PR — `FleetOpsProvider` is the one outlier, and it happens to be the most heavily depended-on data source in the app.

**Fix:**
```ts
const refetch = useCallback(async () => {
  const requestId = ++latestRequestIdRef.current;
  try {
    const [fleetRes, rosterRes] = await Promise.all([
      fetch("/api/fleet"),
      fetch("/api/roster"),
    ]);
    if (!fleetRes.ok || !rosterRes.ok) {
      throw new Error(`fleet=${fleetRes.status} roster=${rosterRes.status}`);
    }
    const fleetData: FleetStatus = await fleetRes.json();
    const rosterData: { drones: RosterDrone[] } = await rosterRes.json();

    if (requestId !== latestRequestIdRef.current) return;

    setBudget({
      energyBudgetKwh: fleetData.energy_budget_kwh,
      remainingKwh: fleetData.remaining_kwh,
      activeMissionCount: fleetData.active_mission_count,
    });
    missionsRef.current = mergeMissions(missionsRef.current, fleetData.missions);
    setMissions(Array.from(missionsRef.current.values()));
    setRoster(rosterData.drones);
    setLoaded(true);
  } catch {
    // Keep last-known state; the next interval tick retries automatically.
    // Consider surfacing a connection-degraded indicator here.
  }
}, []);
```

## Warnings

### WR-01: DispatchBar.submit() has no catch — network/parse failures silently vanish

**File:** `frontend/src/components/DispatchBar.tsx:31-46`
**Issue:** `submit()` wraps `request()` and `res.json()` in a `try { ... } finally { setSubmitting(false) }` with no `catch`:

```ts
async function submit(request: () => Promise<Response>) {
  setError(null);
  setSubmitting(true);
  try {
    const res = await request();
    const body = await res.json();
    if (!res.ok) {
      setError(body.detail ?? { reason: "dispatch_failed" });
      return;
    }
    upsertMission(body);
    await refetch();
  } finally {
    setSubmitting(false);
  }
}
```

If `fetch()` rejects (offline, DNS failure) or the response body isn't valid JSON, the exception propagates out of `submit()` (called via `await submit(...)` in `handleLaunch`/`handleRecall`, also uncaught) as an unhandled promise rejection. The button re-enables (thanks to `finally`), but the operator gets no error message at all — silently different from every other transport-failure path in this PR (`useChat`, `EnergyBudgetChart`), both of which show an inline error for exactly this case.
**Fix:** Wrap in a catch that sets a generic error, mirroring `useChat`'s transport-failure handling:
```ts
try {
  const res = await request();
  const body = await res.json();
  if (!res.ok) {
    setError(body.detail ?? { reason: "dispatch_failed" });
    return;
  }
  upsertMission(body);
  await refetch();
} catch {
  setError({ reason: "connection_error" });
} finally {
  setSubmitting(false);
}
```

### WR-02: useTelemetryStream's onmessage has no guard around JSON.parse

**File:** `frontend/src/lib/useTelemetryStream.ts:34-36`
**Issue:**
```ts
source.onmessage = (event) => {
  setStatus("connected");
  const data: TelemetrySnapshot = JSON.parse(event.data);
  ...
```
A single malformed or truncated SSE payload (e.g. a proxy splitting a chunk mid-message) throws inside the `EventSource.onmessage` handler. This is an uncaught exception in a DOM event callback — it won't crash React (event handlers outside React's render cycle just log to console), but it silently drops that update with no user-visible degradation and no recovery signal, unlike the `disconnected` status the hook otherwise surfaces via `onerror`.
**Fix:**
```ts
source.onmessage = (event) => {
  setStatus("connected");
  let data: TelemetrySnapshot;
  try {
    data = JSON.parse(event.data);
  } catch {
    return;
  }
  setSnapshot(data);
  ...
```

### WR-03: FleetOpsProvider's mount effect has no unmount guard, unlike the equivalent pattern in EnergyBudgetChart

**File:** `frontend/src/lib/FleetOpsProvider.tsx:104-108`
**Issue:**
```ts
useEffect(() => {
  refetch();
  const id = setInterval(refetch, FLEET_POLL_INTERVAL_MS);
  return () => clearInterval(id);
}, [refetch]);
```
`EnergyBudgetChart.tsx` solves the identical "fetch-in-effect that must not update state after unmount" problem with a `cancelled` flag plus `AbortController`, explicitly called out in its docstring as guarding "a fast unmount ... never produces a state update on an unmounted component." `FleetOpsProvider.refetch()` has no equivalent guard, so a slow in-flight request that resolves after the provider unmounts will still call `setBudget`/`setMissions`/`setRoster`. This is inconsistent with the established convention in this same PR and becomes a real risk once this app grows additional routes/unmount points.
**Fix:** Reuse the same cancelled-flag pattern already proven in `EnergyBudgetChart.tsx` inside the mount effect, or thread an `AbortController` signal into both `fetch()` calls.

### WR-04: FleetHeatmap types Recharts render-prop and click payloads as `any`

**File:** `frontend/src/components/FleetHeatmap.tsx:43, 107`
**Issue:**
```ts
function CellContent(props: any) {
  const { x, y, width, height, name, batteryPct } = props;
  ...
```
```ts
onClick={(node: any) => select(node.name)}
```
Both forfeit type safety on the shape Recharts actually passes in (Recharts' `Treemap` content/callback types are notoriously loose, but `any` here means a future prop rename or destructure typo (`batteryPct` vs `battery_pct`) would only surface as a runtime `undefined`, not a compile error).
**Fix:** Introduce a narrow local interface for the fields actually used and cast once at the boundary, e.g. `function CellContent(props: unknown) { const { x, y, width, height, name, batteryPct } = props as CellContentProps; ... }`, or at minimum a `Record<string, unknown>` cast instead of `any`.

## Info

### IN-01: MissionsTable renders eta_minutes without fixed-precision formatting

**File:** `frontend/src/components/MissionsTable.tsx:76`
**Issue:** Every other numeric field in this table is formatted with `.toFixed(...)` (`distance_km.toFixed(1)`, `energy_cost_kwh.toFixed(2)`), but ETA is interpolated raw:
```ts
{mission.eta_minutes !== undefined ? `${mission.eta_minutes} min` : "—"}
```
A backend value like `6.333333333` would render un-rounded, breaking the table's otherwise consistent fixed-precision presentation.
**Fix:** `` `${mission.eta_minutes.toFixed(1)} min` ``

### IN-02: ChatPanel uses array index as React key

**File:** `frontend/src/components/chat/ChatPanel.tsx:97`
**Issue:** `turns.map((turn, index) => <ChatMessage key={index} turn={turn} />)`. Turns are append-only today so this is low-risk, but it's a latent anti-pattern — the first time turns are ever filtered, reordered, or deleted (e.g. a future "clear chat" or per-turn dismiss), index-based keys will cause React to misattribute component state across re-renders.
**Fix:** Give each `ChatTurn` a stable id (e.g. a client-generated uuid or a monotonically increasing counter) at creation time in `useChat.ts` and key on that instead of the array index.

---

_Reviewed: 2026-08-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
