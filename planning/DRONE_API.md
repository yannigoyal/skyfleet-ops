# Drone API Reference Notes

Research notes on REST/streaming API conventions for drone fleet platforms, applied to SkyFleet Ops's existing `/api/*` contract in `PLAN.md`. This is a reference document, not a spec change — it explains *why* the current API looks the way it does and flags a few conventions worth holding onto as the backend is built out.

## 1. Industry Patterns Observed

- **Traceable actions**: every mission action should be attributable to a specific drone, mission, and timestamp so operators (and support) can reconstruct what happened. SkyFleet Ops already does this via `mission_log` (append-only) alongside the mutable `missions` table.
- **Fleet visibility first**: dashboards lead with "is every drone airworthy and accounted for right now," not historical reporting. This maps to `GET /api/fleet` and `GET /api/roster` being the two calls the frontend needs to render the whole console on load.
- **Streaming telemetry over polling**: platforms with more than a handful of aircraft avoid client polling for position/battery and push updates instead (WebSockets or SSE). SkyFleet Ops uses SSE (`/api/stream/telemetry`), which is the right call here — telemetry is server→client only, so a full duplex channel is unneeded complexity.
- **Idempotent, validated mutations**: launch/recall endpoints should validate state before mutating (enough energy budget, drone actually in flight) rather than trusting the caller — this is standard even in demo-grade systems because a bad LLM-issued action must fail safely, not corrupt state.

## 2. Conventions Worth Adopting As Endpoints Are Implemented

- **Consistent envelope**: return the object the frontend needs directly (no wrapper `{data: ...}` envelope) since this is a single-consumer API, not a public integration surface. Keep error responses to `{"detail": "..."}` (FastAPI's default `HTTPException` shape) so the frontend has one error-parsing code path.
- **Status codes**:
  - `200` for reads and successful mutations that return a resulting resource.
  - `201` only if we ever return a created resource with a Location-style identity; for this project, launching a mission can just return `200` with the mission row since there is no separate "fetch it back" step.
  - `400` for validation failures (insufficient budget, drone already in flight, unknown zone).
  - `404` for `DELETE /api/fleet/missions/{drone_id}` when the drone has no active mission, and for `DELETE /api/roster/{drone_id}` when the drone isn't on the roster.
- **SSE event shape**: one `event: telemetry` per drone update (not one giant batch payload) so the frontend's `EventSource.onmessage` handler stays a simple per-drone reducer. Include `battery_direction` (`"charging" | "draining" | "stable"`) precomputed server-side rather than making the frontend diff readings — the backend already has previous/current in the telemetry cache.
- **No auth headers, no API versioning**: this is explicitly a single-operator, no-login system (see PLAN.md §2). Don't add `Authorization` headers or `/api/v1/` prefixes — they're unused complexity for a system with one operator and no external integrators.
- **Mission auto-execution from chat**: LLM-issued mission/roster actions must go through the exact same validation path as manual dispatch (§9 of PLAN.md already specifies this) — never a separate "trusted" code path for AI-issued commands.

## 3. Endpoint Notes (extending PLAN.md §8)

| Endpoint | Notable behavior |
|---|---|
| `POST /api/fleet/missions` | Reject if `energy_cost_kwh` (derived from `distance_km`) exceeds remaining budget; reject if the drone already has an active mission. |
| `DELETE /api/fleet/missions/{drone_id}` | No-op error (404) if the drone has no `en_route` mission; writes a `mission_log` row with `action="recall"`. |
| `GET /api/fleet/history` | Should support an implicit default range (e.g., last N snapshots) rather than requiring query params — the frontend just wants "enough points for the chart." |
| `POST /api/roster` | Reject duplicate `drone_id` (unique constraint already in schema) with a clear 400, not a raw SQLite constraint error. |

## Sources

- [Drone Fleet Management: Software, Compliance & Scaling Operations](https://www.thedroneu.com/blog/drone-fleet-management/)
- [Drone Fleet Management: Complete Guide + Software Comparison [2026] | Dronedesk](https://dronedesk.io/drone-fleet-management-guide)
- [Drone API | FlytBase](https://flytbase.com/drone-api)
- [REST API — INVOLI](https://www.involi.com/rest-api)
