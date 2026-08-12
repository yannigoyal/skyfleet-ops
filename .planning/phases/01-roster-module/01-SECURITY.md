---
phase: 01
slug: roster-module
status: verified
threats_open: 0
asvs_level: 1
created: 2026-08-12
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| HTTP client → `POST /api/roster` | Untrusted JSON body (`drone_id`) crosses into the application | drone identifier string |
| HTTP client → `DELETE /api/roster/{drone_id}` | Untrusted path parameter crosses into the application | drone identifier string |
| Router/service → SQLite `fleet_roster` | Untrusted `drone_id` reaches the persistence layer | drone identifier string, operator scoping |
| Service → `TelemetrySource` | Untrusted `drone_id` reaches the in-process telemetry fleet registry | drone identifier string |
| `roster.service` → `missions.service` | In-process cross-module call; a roster action triggers a mission-state write and a budget snapshot | mission recall side effects |
| `TelemetryCache` → `GET /api/roster` response | Cached telemetry is projected into an operator-visible payload | battery/altitude/speed readings |

Out of scope project-wide (per `.planning/REQUIREMENTS.md` "Out of Scope"): ASVS V2 Authentication, V3 Session Management, V4 Access Control, V6 Cryptography. Single-operator demo with a hardcoded `operator_id = 'default'`.

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-01-01 | Tampering | `roster/repository.py` SQL against `fleet_roster` | high | mitigate | All statements use `?` placeholders via `Database.execute`/`fetchall`/`transaction`; zero interpolated SQL confirmed by grep | closed |
| T-01-02 | Tampering | `AddDroneRequest` body validation | medium | mitigate | `Field(min_length=1)` rejects empty/missing `drone_id` with 422 before DB access | closed |
| T-01-03 | Information Disclosure | `roster/repository.py` read queries | medium | mitigate | Every SELECT/DELETE scoped `WHERE operator_id = ?`; cross-operator invisibility test-pinned | closed |
| T-01-04 | Denial of Service | `POST /api/roster` unbounded roster growth | low | accept | No `MAX_FLEET_SIZE`; single-operator local demo, below `high` block threshold. (Duplicate registration as T-01-15 in 01-03-PLAN.md — merged here) | closed |
| T-01-05 | Denial of Service | Simulator Cholesky recompute on each roster add | low | accept | Documented in `.planning/codebase/CONCERNS.md`; fleet sizes small, out of phase scope | closed |
| T-01-06 | Tampering | `drone_id` path parameter reaching `remove_drone` | high | mitigate | DELETE binds `operator_id` and `drone_id` as `?` params inside `db.transaction` | closed |
| T-01-07 | Elevation of Privilege | `roster.service` invoking `missions.service.recall_mission` | medium | mitigate | Reuses the identical `recall_mission` entry point manual dispatch uses; no bypass path; precondition enforced inside recall's own transaction | closed |
| T-01-08 | Repudiation | Auto-recall triggered as a side effect of a roster action | medium | mitigate | `recall()` appends `mission_log` (action=recall) and `budget_snapshots` rows in the same transaction | closed |
| T-01-09 | Tampering | Check-then-act exception path: `roster.service.remove_drone` checks for an active mission, then recalls it as a separate transaction; if `run_delivery_scheduler` (5s tick) resolves the mission in that window, `recall_mission()` raises `NoActiveMissionError`, a `MissionError` subclass the roster router's `except RosterError` does not catch | low | mitigate (flipped from accept) | **Open.** Live-reproduced by the security auditor against the real app (probe script, not just source inspection): scheduler resolves mission → DELETE returns HTTP 500 → retry succeeds with 204. Original plan-time `accept` rationale ("residual state safe, retry idempotent") described a crash window, not the exception path that actually exists — the accept was granted against the wrong threat statement. Same defect as code review finding CR-01. No information disclosure (generic 500 body, no stack trace) and no state corruption — retry succeeds — hence severity stays `low`, below the `high` block threshold, non-blocking. Fix: catch `NoActiveMissionError` around the `recall_mission()` call in `remove_drone()` and treat as already-resolved; add a regression test interleaving mission resolution between check and recall. | open — below high threshold (non-blocking) |
| T-01-10 | Information Disclosure | Cross-operator deletion via an unscoped DELETE | medium | mitigate | Scoped DELETE; `rowcount == 0` raises `UnknownDroneError` rather than silently succeeding; 404 test-pinned | closed |
| T-01-11 | Tampering | `AddDroneRequest` input validation (error matrix) | medium | mitigate | `TestAddDroneErrors` pins 422 for empty/missing `drone_id`, asserts roster unchanged | closed |
| T-01-12 | Tampering | String-interpolated SQL creeping into `roster/repository.py` | high | mitigate | Grep for f-string/`%`/`.format(` SQL construction returns zero matches | closed |
| T-01-13 | Information Disclosure | `GET /api/roster` payload shape | medium | mitigate | `TestTelemetryMerge` asserts exact key set; `RosterEntry.to_dict()` returns only `drone_id`/`added_at`, never `id`/`operator_id` | closed |
| T-01-14 | Elevation of Privilege | A write handler bypassing the service layer in a future edit | medium | mitigate | `TestLayering` monkeypatches service functions; fails if a handler writes through the repository directly | closed |
| T-01-SC | Tampering | npm/pip/cargo installs (registered once per plan, x3) | n/a | accept | Zero new packages installed across all three plans — verified against `git log --name-only` diff, not just docs | closed |

*Status: open · closed · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (`high`) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-04 | No fleet-size cap exists; single-operator local demo, growth bound by manual operator action, below `high` block threshold | plan author (01-01-PLAN.md, 01-03-PLAN.md) | 2026-08-12 |
| AR-02 | T-01-05 | Cholesky recompute cost on each roster add documented as a known, out-of-scope performance concern, not a security defect at current fleet sizes | plan author (01-01-PLAN.md) | 2026-08-12 |
| AR-03 | T-01-SC | Zero new dependencies installed across all three plans — verified via git diff, not just supply-chain audit notes | plan author / security auditor | 2026-08-12 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-12 | 15 (14 unique + 1 duplicate merged) | 13 | 1 (non-blocking) | gsd-security-auditor (live-reproduction verification, not source-inspection only) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (T-01-09 open but below `high` block threshold)
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-12 — non-blocking. T-01-09 should still be fixed before Phase 2, since the chat flow is planned to reuse `roster.service.remove_drone` directly for AI-triggered removals (same reachable race).
