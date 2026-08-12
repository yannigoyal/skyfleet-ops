# Phase 1: Roster Module - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-12
**Phase:** 1-Roster Module
**Areas discussed:** Prior code reuse, Active-mission removal, Telemetry sync failure, Drone ID format

---

## Prior code (unmerged `agent_team_work` branch reuse)

| Option | Description | Selected |
|--------|-------------|----------|
| Port and extend it | Bring `agent_team_work`@`2ba52a8` roster files over as a starting point, add the missing service.py layer per ROST-04, and add active-mission handling. | ✓ |
| Build fresh | Ignore the old branch entirely and implement roster/ from scratch following missions/ as the template. | |
| Let the planner decide | Note the prior code's existence and shape in CONTEXT.md; let gsd-planner assess reuse vs rewrite during planning. | |

**User's choice:** Port and extend it (recommended option).
**Notes:** Discovered during codebase scout — `backend/app/roster/` on disk at HEAD has only stale
`__pycache__` files (no source), but an unmerged branch commit has working models/repository/router.
That code lacks a service.py layer and doesn't handle removal of a drone with an active mission.

---

## Active mission on removal

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-recall then remove | Removing the drone also recalls its mission before the roster row is deleted. | ✓ |
| Block removal with an error | Return 409 and require the operator to recall the mission first. | |
| Allow it, leave mission orphaned | Mission stays en_route pointing at an untracked drone. | |

**User's choice:** Auto-recall then remove (recommended option).
**Notes:** Requires `roster.service` to call into `missions.service.recall_mission()` — first
cross-module service dependency in the codebase. Rated `costly` to reverse later (see CONTEXT.md D-03).

---

## Telemetry sync failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Log and continue | DB is the source of truth; telemetry cache miss self-heals on next cycle/retry. | ✓ |
| Roll back the DB write | Treat telemetry sync as part of the same atomic operation. | |

**User's choice:** Log and continue (recommended option).
**Notes:** Matches existing project pattern — telemetry issues are logged, not fatal.

---

## Drone ID format

| Option | Description | Selected |
|--------|-------------|----------|
| Any non-empty string | Matches prior branch code's `Field(min_length=1)` and how missions.drone_id is treated. | ✓ |
| Enforce a naming pattern | Require drone IDs to match a squadron-prefixed format like existing FALCON-01..10. | |

**User's choice:** Any non-empty string (recommended option).
**Notes:** No naming convention enforced by the backend.

---

## Claude's Discretion

- Exact SQL/transaction shape for the auto-recall-then-remove flow.
- Response payload shape for roster entries (which telemetry fields to merge in).

## Deferred Ideas

None — discussion stayed within phase scope.
