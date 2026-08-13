# API Coverage — SkyFleet Ops backend (`/api/*`, same-origin)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

**Scope note.** This phase integrates no *third-party* API, SDK, or vendor service — the
only network surface it consumes is SkyFleet Ops' own FastAPI backend, built and verified
in Phases 1 and 2 and served from the same origin (`planning/PLAN.md` §3: one container,
one port, no CORS). The coverage question is nonetheless real and worth deciding
explicitly: the backend exposes eleven routes, and the frontend built here consumes seven
of them. The four it does not consume are recorded below with reasons rather than left as
invisible holes.

Route list enumerated from source this session: `backend/app/missions/router.py`,
`backend/app/roster/router.py`, `backend/app/chat/router.py`,
`backend/app/telemetry/stream.py`, `backend/app/main.py`.

| capability | decision | reason |
|---|---|---|
| `GET /api/stream/telemetry` | INTEGRATE | |
| `GET /api/fleet` | INTEGRATE | |
| `GET /api/fleet/history` | INTEGRATE | |
| `POST /api/fleet/missions` | INTEGRATE | |
| `DELETE /api/fleet/missions/{drone_id}` | INTEGRATE | |
| `GET /api/roster` | INTEGRATE | |
| `POST /api/chat` | INTEGRATE | |
| `GET /api/fleet/missions/queue` | OPT-OUT | Internal retry buffer for auto-assign dispatch; absent from PLAN.md §8 and from every FE requirement. D-15's dropdown always names a drone, so this UI can never enqueue. |
| `POST /api/roster` | OPT-OUT | No FE requirement covers a manual roster-add control (FE-01..FE-09 are visualisation, dispatch, header, chat only). Reachable via the chat's roster_changes path. See gap below. |
| `DELETE /api/roster/{drone_id}` | OPT-OUT | Same as `POST /api/roster` — no manual-removal FE requirement; reachable via the chat panel's `roster_changes` path, which renders a "Removed" card. See gap below. |
| `GET /api/health` | OPT-OUT | Deployment concern, not a console feature. Consumed by the Docker `HEALTHCHECK` in Phase 4 (DEPLOY-01), not by the browser. |

## Flagged gap for the developer — manual roster CRUD has no requirement

`planning/PLAN.md` §2 ("What the Dispatcher Can Do") states the dispatcher can *"Manage the
fleet roster — add/remove drones **manually** or via the AI chat."* The AI-chat half is
covered by FE-09. The **manual** half has no FE requirement: `.planning/REQUIREMENTS.md`'s
FE-01 through FE-09 contain no roster add/remove control, so the roadmap's phase requirement
set does not carry it and no plan in this phase implements it.

This is recorded as an opt-out rather than silently omitted, and it is **not** a scope
reduction by the planner — the two roster-write endpoints exist and are tested (ROST-01,
ROST-02, Phase 1), so wiring a small roster control would be a genuinely new requirement,
not a deferred part of an existing one. Two defensible resolutions:

1. **Accept as-is.** Roster management stays an AI-delegated capability this milestone,
   which is on-theme for an agentic demo and already demonstrable end to end.
2. **Add FE-10** (manual roster add/remove control) to `REQUIREMENTS.md` and plan it as a
   seventh plan in this phase or as a follow-on. Cost is small — one form component reusing
   the `DispatchBar` shell and the already-built endpoints.

Raised for the developer to decide; the planner did not choose unilaterally.
