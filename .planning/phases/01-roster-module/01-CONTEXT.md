# Phase 1: Roster Module - Context

**Gathered:** 2026-08-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator can manage the fleet roster (add/remove/view tracked drones) through `backend/app/roster/`,
kept in sync with live telemetry via the existing `TelemetrySource` interface, using the same
layered pattern (models/service/repository/router) as `backend/app/missions/`. Requirements:
ROST-01, ROST-02, ROST-03, ROST-04.

</domain>

<decisions>
## Implementation Decisions

### Reuse of prior unmerged work
- **D-01:** Port and extend the roster code found on the unmerged `agent_team_work` branch
  (commit `2ba52a8`, files `backend/app/roster/{models,repository,router,__init__}.py`) as the
  starting point, rather than writing from scratch. — **Reversibility:** reversible — it's a
  starting point for this phase's plan, not a merged dependency; the planner/executor can still
  rewrite pieces that don't fit.
- **D-02:** That branch's code is missing the `service.py` layer required by ROST-04 (router calls
  `repository` directly) and has no handling for removing a drone with an active mission. Both must
  be added — the ported code is not a drop-in, it needs a service layer inserted between router and
  repository, following `missions/service.py`'s shape.

### Active-mission handling on removal
- **D-03:** Removing a drone that has an active (`en_route`) mission auto-recalls that mission
  (same effect as `DELETE /api/fleet/missions/{drone_id}`) before deleting the roster row, so one
  operator action always leaves the system consistent. This requires `roster.service` to call
  `missions.service.recall_mission()` (or equivalent) as part of the remove flow — a new
  cross-module dependency from `roster/` into `missions/` that doesn't exist in the ported branch
  code. — **Reversibility:** costly — **rationale:** changing this later means either adding a
  migration path for orphaned missions already created under the old behavior, or reworking the
  remove endpoint's response contract if callers start relying on the auto-recall side effect.

### Telemetry sync failure handling
- **D-04:** If the roster DB write succeeds but `TelemetrySource.add_drone()` /
  `remove_drone()` raises, log the error and continue — do not roll back the DB write. The
  database (`fleet_roster` table) is the source of truth for the roster; a telemetry cache miss
  self-heals on the next update cycle or a later retry. Matches the project's existing pattern of
  telemetry issues being logged, not fatal.

### Drone ID validation
- **D-05:** Accept any non-empty string as `drone_id` when adding a drone (matches the prior
  branch's `Field(min_length=1)` and how `missions.drone_id` is already treated — a plain string,
  no enforced naming convention).

### Claude's Discretion
- Exact SQL/transaction shape for the auto-recall-then-remove flow (single transaction vs.
  sequential calls) — follow whatever `missions/repository.py` conventions make this safe under
  concurrent access, consistent with the project's single-writer-lock pattern.
- Response payload shape for `_entry_response`-equivalent helper (which telemetry fields to merge
  into each roster entry) — the ported branch's `_TELEMETRY_FIELDS = (battery_pct, altitude_m,
  speed_kmh, status)` is a reasonable default; adjust only if `GET /api/roster` needs more per
  Phase 3's frontend requirements.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specification
- `planning/PLAN.md` §7 (Database schema — `fleet_roster` table) and §8 (API Endpoints — Roster) —
  the authoritative shape for `POST/GET/DELETE /api/roster`.

### Prior unmerged implementation (reuse source, per D-01/D-02)
- Branch `agent_team_work`, commit `2ba52a8` — `backend/app/roster/models.py`,
  `backend/app/roster/repository.py`, `backend/app/roster/router.py`,
  `backend/app/roster/__init__.py`. Not on disk at HEAD (stray `__pycache__/*.pyc` files exist in
  `backend/app/roster/` from a prior checkout — safe to ignore/delete, source `.py` files are
  gone). Retrieve via `git show 2ba52a8:backend/app/roster/<file>`.

### Sibling module to mirror (per ROST-04)
- `backend/app/missions/` (models.py, service.py, repository.py, router.py, `__init__.py`) — the
  layering, error-hierarchy (`MissionError` → reason-tagged subclasses → `_ERROR_STATUS` lookup in
  router), and dependency-injection-via-factory-function pattern (`create_missions_router(db,
  cache, queue)`) that `roster/` must follow.

### Telemetry integration contract
- `backend/app/telemetry/interface.py` — `TelemetrySource.add_drone()` / `remove_drone()` /
  `get_drone_ids()` — the interface roster mutations must call to keep telemetry in sync (per D-04
  for failure handling).

### Database schema
- `backend/app/db/schema.py` — `fleet_roster` table definition (lines ~12-18): `id`, `operator_id`
  default `'default'`, `drone_id`, `added_at`, `UNIQUE(operator_id, drone_id)`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/roster/{models,repository,router}.py` on branch `agent_team_work` @ `2ba52a8` —
  working CRUD logic (add/remove/list against `fleet_roster`), `RosterError` hierarchy
  (`DroneAlreadyTrackedError`, `UnknownDroneError`), and a router that already merges telemetry
  fields into roster entries. Needs a `service.py` inserted and active-mission handling added (see
  D-01–D-03).
- `missions/repository.py::is_drone_on_roster()` already exists and queries `fleet_roster` — the
  mission-launch path already depends on roster state; no new coupling needed there.
- `missions/repository.py::recall()` — existing recall logic the new roster removal flow should
  call into (per D-03) rather than duplicating recall SQL.

### Established Patterns
- Factory-function routers: `create_missions_router(db, cache, queue) -> APIRouter` — no globals,
  dependencies passed explicitly. `roster/` should follow: `create_roster_router(db, cache,
  source) -> APIRouter`.
- Domain exceptions: `reason` class attribute + router-level `_ERROR_STATUS` dict translating to
  HTTP codes (`missions/router.py:15-22`, ported `roster/router.py` already has a smaller
  `_ERROR_STATUS` for `unknown_drone`/`drone_already_tracked` — will need `active_mission`-related
  reasons added if D-03's auto-recall path can itself fail).
- Repository transaction pattern: `db.transaction(_txn)` for multi-statement atomicity (see
  `missions/repository.py::recall()` and the ported `roster/repository.py::remove_drone()`).

### Integration Points
- `app.state` / lifespan wiring in `backend/app/main.py` — roster router must be constructed and
  mounted the same way `missions_router` currently is (module-level `telemetry_cache`,
  `mission_queue`, `database` passed in, not accessed globally).
- `roster.service` will need a dependency on `missions.service` (or `missions.repository`) for the
  auto-recall-on-remove behavior (D-03) — first cross-module service dependency in the codebase;
  keep it a straightforward function call, not a shared abstraction.

</code_context>

<specifics>
## Specific Ideas

No UI references for this phase (backend-only). No specific wording/behavior examples beyond the
decisions above — standard REST CRUD semantics apply.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Roster Module*
*Context gathered: 2026-08-12*
