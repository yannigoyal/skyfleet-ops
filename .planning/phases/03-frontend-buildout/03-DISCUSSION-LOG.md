# Phase 3: Frontend Buildout - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-13
**Phase:** 3-Frontend Buildout
**Areas discussed:** State & data architecture, AI chat panel UX, Heatmap implementation, Missions table & dispatch bar

---

## State & data architecture

| Option | Description | Selected |
|--------|-------------|----------|
| React Context for fleet-ops state | New FleetOpsProvider wraps budget/missions/selected-drone; STRUCTURE.md flags Context as suitable given many consumers | ✓ |
| Lift to page.tsx + prop drilling | Matches existing pattern, simplest, but props get deep for chat panel/dispatch bar | |
| You decide | Let the planner pick | |

**User's choice:** React Context for fleet-ops state (D-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Poll on an interval + refetch after actions | Catches server-side mission completions from the delivery scheduler | ✓ |
| Refetch only after explicit actions | Simpler, but misses background scheduler completions | |
| You decide | Let the planner pick a polling interval | |

**User's choice:** Poll on an interval + refetch after actions (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Cap to last N readings per drone | Fixed, predictable memory footprint | ✓ |
| Cap to a time window instead | More relevant for detail-panel history, variable memory | |
| You decide | Let the planner pick a specific cap value | |

**User's choice:** Cap to last N readings per drone (D-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Plain client-side state, no URL sync | Single-operator demo, no sharing needs | ✓ |
| Sync to a URL query param | Enables bookmarking/sharing, adds routing complexity | |

**User's choice:** Plain client-side state, no URL sync (D-04)

---

## AI chat panel UX

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed right sidebar, always visible | Simplest layout math | ✓ (later refined) |
| Collapsible right sidebar (toggle open/closed) | More flexible, adds layout/state complexity | |
| You decide | Let the planner pick | |

**User's choice:** Fixed right sidebar, always visible — then refined below.

**Follow-up:** FE-08 explicitly requires "docked/collapsible sidebar." Asked whether to keep it
fixed with no toggle, or always-visible-by-default with a collapse toggle added.

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed, no collapse toggle | Treats "collapsible" as non-essential to FE-08's testable behaviors | |
| Always-visible by default, but add a collapse toggle | Satisfies FE-08's literal wording with minimal extra work | ✓ |

**User's choice:** Always-visible by default, but add a collapse toggle (D-05)
**Notes:** Raised because the original answer conflicted with FE-08's literal requirement text —
resolved to avoid ambiguity at the requirements-coverage gate later in planning.

| Option | Description | Selected |
|--------|-------------|----------|
| Action verb + key params + outcome badge | Compact, scannable, matches ops-console aesthetic | ✓ |
| Expandable card with full raw action JSON | More debuggable, more visual weight | |
| You decide | Let the planner design exact fields | |

**User's choice:** Action verb + key params + outcome badge (D-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Trigger the same refetch as manual dispatch | One code path for staying in sync | ✓ |
| Chat panel optimistically merges the action result into state directly | Snappier but risks drift | |

**User's choice:** Trigger the same refetch as manual dispatch (D-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Disable input until response returns | Matches non-streaming POST /api/chat contract | ✓ |
| Allow queuing additional messages while waiting | More flexible, needs a client-side queue | |

**User's choice:** Disable input until response returns (D-08)

---

## Heatmap implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Recharts Treemap component | Reuses already-pinned charting library | ✓ |
| Hand-rolled CSS grid/flexbox layout | More control, duplicates layout math | |
| You decide | Let the planner pick | |

**User's choice:** Recharts Treemap component (D-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Include with a fixed minimum size | Full fleet always visible, even with 0 active missions | ✓ |
| Exclude idle drones from the heatmap entirely | Heatmap looks broken/empty on fresh start | |
| You decide | Let the planner pick a weighting scheme | |

**User's choice:** Include with a fixed minimum size (D-10)

| Option | Description | Selected |
|--------|-------------|----------|
| 3-band thresholds: green >=50%, amber 20-50%, red <20% | Matches existing roster flash convention and Tailwind tokens | ✓ |
| Continuous gradient interpolated from 0-100% battery | Smoother but needs interpolation, less consistent | |
| You decide | Let the planner pick thresholds | |

**User's choice:** 3-band thresholds: green ≥50%, amber 20–50%, red <20% (D-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — same selection behavior as roster row click | One selection mechanism, multiple entry points | ✓ |
| No — heatmap is view-only | Simpler but inconsistent affordances | |

**User's choice:** Yes — same selection behavior as roster row click (D-12)

---

## Missions table & dispatch bar

| Option | Description | Selected |
|--------|-------------|----------|
| Compute client-side from distance_km and a fixed cruise speed | Reuses DEFAULT_CRUISE_SPEED_KMH, no backend change | ✓ |
| Add an eta field to the backend response | More accurate but touches a stable API contract, out of scope | |
| You decide | Let the planner decide | |

**User's choice:** Compute client-side from distance_km and a fixed cruise speed (D-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Submit and surface backend errors inline | No duplicate validation logic, reuses reason-coded errors | ✓ |
| Client-side pre-validation before submit | Faster feedback but risks drift from backend rules | |
| You decide | Let the planner decide | |

**User's choice:** Submit and surface backend errors inline (D-14)

| Option | Description | Selected |
|--------|-------------|----------|
| Drone: dropdown of roster; Zone: free text | Dropdown prevents typos; no enumerated zone list exists anywhere | ✓ |
| Both dropdowns (drone from roster, zone from a fixed preset list) | Requires inventing an arbitrary zone list | |
| You decide | Let the planner decide | |

**User's choice:** Drone: dropdown of roster; Zone: free text (D-15)

| Option | Description | Selected |
|--------|-------------|----------|
| "No active mission" empty state, telemetry still shown | Simple, no extra query needed | ✓ |
| Show the drone's most recent completed/recalled mission instead | More informative but needs a mission_log lookup | |
| You decide | Let the planner decide | |

**User's choice:** "No active mission" empty state, telemetry still shown (D-16)

---

## Claude's Discretion

- Exact retention count for the telemetry history cap (D-03)
- Exact px/rem sizing for chat sidebar width, collapse-toggle placement, minimum heatmap cell weight
- Component/file naming for new components (follow existing PascalCase convention)

## Deferred Ideas

None — discussion stayed within phase scope.
