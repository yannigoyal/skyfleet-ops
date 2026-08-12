---
phase: 01-roster-module
verified: 2026-08-12T18:40:00Z
status: passed
score: 24/24 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 21/23
  gaps_closed:
    - "Operator can DELETE /api/roster/{drone_id} and receive 204, with automatic recall of any in-flight mission, reliably (ROST-02, ROADMAP SC2) — the check→recall TOCTOU race (CR-01 / T-01-09) is now guarded"
  gaps_remaining: []
  regressions: []
---

# Phase 1: Roster Module Verification Report (Re-Verification After Gap Closure)

**Phase Goal:** Operator can manage the fleet roster through the API, kept in sync with live telemetry, using the same layered pattern as the existing missions module.
**Verified:** 2026-08-12T18:40:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plan 01-04, gap_ids: [ROST-02-TOCTOU])

## Goal Achievement

### Gap 1 Closure — Independent Verification

The prior verification's sole blocker: `DELETE /api/roster/{drone_id}` raised an unhandled
`NoActiveMissionError` (HTTP 500) instead of returning 204 when a drone's `en_route` mission
resolved (via the 5s delivery scheduler, or a concurrent manual recall) in the window between
`roster.service.remove_drone`'s active-mission check and its `recall_mission` call.

I did not trust the SUMMARY's self-report. Independent verification performed:

1. **Diffed the fix commit** (`20e11a6`) against the pre-fix version of `backend/app/roster/service.py` — confirmed the change is exactly a narrow `try/except NoActiveMissionError` wrapped around the `recall_mission` call, with an `logger.info` trace naming the `drone_id`, plus a docstring update. No other production files were touched (router.py is byte-identical to before, as the plan required).
2. **Reproduced the fail-first claim myself.** Temporarily replaced the current `backend/app/roster/service.py` with the pre-fix version (`git show 20e11a6^:backend/app/roster/service.py`) and re-ran the new regression test `tests/roster/test_router.py::TestRemoveDroneMidWindowRace`. It failed with `app.missions.models.NoActiveMissionError: no active mission for drone: FALCON-01` escaping through `app/roster/router.py:62` — the exact unhandled-exception condition the gap described. Restored the fixed file (`git diff` confirmed byte-identical afterward) and re-ran the same test: **204, passes.** This independently confirms the regression test is a real fail-first proof, not a post-hoc rationalization.
3. **Ran every race-related test individually** (not just trusted the SUMMARY's pass count):
   - `tests/roster/test_router.py::TestRemoveDroneMidWindowRace` (HTTP-level, real mission launched over `TestClient`, two routers mounted) — PASS
   - `tests/roster/test_service.py::TestRemoveDroneMidWindowRace` (3 tests: scheduler-delivery variant, concurrent-manual-recall variant, idempotency-after-race) — PASS, and I read each assertion body: they check real SQLite state (`missions.status`, `mission_log` recall-row counts, `get_remaining_kwh` equality), not shallow mocks
   - `tests/roster/test_service.py::TestRemoveDroneCatchNarrowness` (2 tests: a different `MissionError` subclass still propagates and the roster row survives; the skipped recall is logged) — PASS
4. **Ran the full backend suite myself**: 216 passed, 0 failed (matches SUMMARY's claim).
5. **Ran coverage myself**: `app/roster/` 126/126 statements, 100%, no missing lines (matches SUMMARY's claim).
6. **Ran ruff myself**: `app/ tests/` clean (matches SUMMARY's claim).
7. **Read `01-REVIEW.md`** (freshly dated after the fix, superseding the prior review) — confirms CR-01 resolved with a correct root-cause trace of why the fix closes the race (the *authoritative* re-check lives inside `recall()`'s own locked transaction; the guard just stops that expected outcome from surfacing as a 500). No new critical findings.
8. **Confirmed the audit-trail claim structurally**: `repository.recall()` raises `NoActiveMissionError` before its first SQL statement (read `app/missions/repository.py`), so the guarded path performs zero writes to `missions`/`mission_log`/`budget_snapshots` — this is not just asserted by the tests, it is structurally guaranteed by where the exception is raised.

**Verdict: Gap 1 is genuinely closed**, not a superficial patch. The catch is narrow (`NoActiveMissionError` only, not `MissionError` or bare `Exception`), the fix sits at the correct layer (service, not router — matching the project's error-translation convention), and regression coverage exists at both HTTP and service layers for both winning writers of the race.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/roster with `{"drone_id": "FALCON-11"}` returns 201 with the created entry (ROST-01) | ✓ VERIFIED | Unchanged since initial verification; re-confirmed by full-suite pass (216/216) |
| 2 | Added drone is registered with the live TelemetrySource so it starts streaming | ✓ VERIFIED | Unchanged; `test_registers_with_telemetry_source` passes |
| 3 | GET /api/roster returns every tracked drone merged with latest TelemetryCache reading (ROST-03) | ✓ VERIFIED | Unchanged; `test_merges_latest_telemetry` passes |
| 4 | The real app.main:app serves /api/roster; telemetry_source is a module-level singleton | ✓ VERIFIED | Unchanged; `TestAppWiring` passes |
| 5 | backend/app/roster/ organized models/service/repository/router/__init__; router → service → repository (ROST-04) | ✓ VERIFIED | Unchanged structurally; `TestLayering` passes |
| 6 | TelemetrySource.add_drone() failure is logged and the fleet_roster row stays committed (D-04) | ✓ VERIFIED | Unchanged; `TestTelemetrySyncFailure` passes |
| 7 | Two concurrent POST /api/roster for same drone_id leave exactly one row; loser gets 409 | ✓ VERIFIED | Unchanged; `TestConcurrentDuplicateAdd` passes |
| 8 | GET /api/roster never returns a partially-written telemetry reading | ✓ VERIFIED | Unchanged; single `cache.get()` call, frozen dataclass |
| 9 | **Operator can DELETE /api/roster/{drone_id} and receives 204; drone stops appearing, reliably (ROST-02, ROADMAP SC2)** | ✓ **VERIFIED (was FAILED)** | Fail-first reproduction confirms the race existed; fix confirmed narrow and correct; both racing writers (scheduler-delivery, concurrent-manual-recall) pinned by passing tests at HTTP and service layers |
| 10 | Removing a drone with an en_route mission auto-recalls it first: mission status → recalled, mission_log row, budget_snapshots row (D-03) | ✓ VERIFIED | Non-race path unchanged and passing; race path now also verified clean (audit trail preserved, no phantom rows) |
| 11 | Removal is check-first — `get_active_mission_for_drone()` before `recall_mission()`, no exception-driven control flow | ✓ VERIFIED | Structure preserved; the new guard wraps only the recall call, confirmed via `inspect.getsource` acceptance check in the plan and by direct code read |
| 12 | Cross-module dependency is narrow named-function imports, not package-level `app.missions` import | ✓ VERIFIED | `grep -rn 'from app.roster' app/missions/` — no match; dependency stays one-directional; new `NoActiveMissionError` import follows the same narrow-import convention |
| 13 | DELETE write path runs router → roster.service → repository | ✓ VERIFIED | Unchanged; `router.py` byte-identical to pre-fix version |
| 14 | TelemetrySource.remove_drone() failure is logged and fleet_roster deletion stays committed (D-04) | ✓ VERIFIED | Unchanged |
| 15 | Second DELETE for an already-removed drone returns 404 unknown_drone, no recall, roster unchanged | ✓ VERIFIED | Unchanged, plus a new race-specific variant: `test_idempotent_after_race_second_removal_raises_unknown_drone` proves the same for a drone removed via the raced path |
| 16 | Crash-window backstop: recall and delete are two separate transactions; a retried DELETE completes cleanly | ✓ VERIFIED | Unchanged |
| 17 | POST with a drone_id already on the roster returns 409 drone_already_tracked, roster unchanged | ✓ VERIFIED | Unchanged |
| 18 | POST with empty drone_id returns 422 before any DB access | ✓ VERIFIED | Unchanged |
| 19 | DELETE for a never-tracked drone returns 404 unknown_drone | ✓ VERIFIED | Unchanged |
| 20 | Roster entry with no telemetry returns exactly `{drone_id, added_at}`; with telemetry adds exactly 4 fields | ✓ VERIFIED | Unchanged |
| 21 | Roster reads/writes are scoped to one operator | ✓ VERIFIED | Unchanged |
| 22 | RosterEntry.to_dict() returns exactly `{drone_id, added_at}`; every RosterError subclass carries its reason | ✓ VERIFIED | Unchanged |
| 23 | ROST-04 structural mirroring of backend/app/missions/ (backstop, flagged unresolved by executor) | ? UNCERTAIN (carried forward, unchanged) | Structural, not a functional defect; this plan did not touch module structure so the flagged assumption is unchanged — same status as initial verification |
| 24 | The guard is narrow: a different `MissionError` subclass from `recall_mission` still propagates and the roster row survives (T-01-16) | ✓ VERIFIED | `TestRemoveDroneCatchNarrowness::test_different_mission_error_propagates_and_leaves_roster_row` — independently run, passes; asserts `DroneUnavailableError` propagates and `"FALCON-01" in list_roster(db)` afterward |

**Score:** 24/24 truths verified or carried-forward-by-design (1 uncertain/backstop, unaffected by this run's scope)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/roster/service.py` | `remove_drone` with narrow `except NoActiveMissionError` guard around the recall step | ✓ VERIFIED | Confirmed via diff of fix commit; guard sits on the recall call only, not the whole function; import is narrow (`from app.missions.models import NoActiveMissionError`) |
| `backend/tests/roster/test_router.py` | HTTP-level proof of the 204 contract under the race | ✓ VERIFIED | `class TestRemoveDroneMidWindowRace` present, launches a real mission via a two-router-mounted `TestClient`, independently re-run and passes |
| `backend/tests/roster/test_service.py` | Service-level coverage of both race variants, audit-trail preservation, catch narrowness, log trace | ✓ VERIFIED | `class TestRemoveDroneMidWindowRace` (3 tests) + `class TestRemoveDroneCatchNarrowness` (2 tests), all independently re-run and pass; assertions read real DB state, not mocks |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `roster/service.py` | `missions/models.py` | `from app.missions.models import NoActiveMissionError`, caught around `recall_mission` | ✓ WIRED | Confirmed by source read; `grep -c` in plan acceptance criteria independently re-run, returns 1 |
| `roster/router.py` | `roster/service.py` | DELETE handler still only catches `RosterError`, unchanged | ✓ WIRED (unchanged) | `router.py` confirmed byte-identical to pre-fix version — the fix correctly stayed at the service layer per the plan's explicit "NOT changed" constraint |
| `roster/service.py` | `missions/repository.py`, `missions/service.py` | `get_active_mission_for_drone`, `recall_mission` (narrow imports, one-directional) | ✓ WIRED | `grep -rn 'from app.roster' app/missions/` — no match, independently re-run |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Fail-first reproduction of the pre-fix bug | Reverted `service.py` to pre-fix, ran `pytest tests/roster/test_router.py::TestRemoveDroneMidWindowRace` | `NoActiveMissionError` escapes unhandled (1 failed) | ✓ PASS — proves the regression test is real, not decorative |
| Post-fix HTTP-level race test | `pytest tests/roster/test_router.py::TestRemoveDroneMidWindowRace -v` (restored fix) | 1 passed | ✓ PASS |
| Post-fix service-level race + narrowness tests | `pytest tests/roster/test_service.py::TestRemoveDroneMidWindowRace tests/roster/test_service.py::TestRemoveDroneCatchNarrowness -v` | 5 passed | ✓ PASS |
| Full backend suite (regression check) | `pytest -q` | 216 passed, 0 failed | ✓ PASS |
| `app/roster/` coverage | `pytest tests/roster/ --cov=app.roster --cov-report=term-missing` | 126/126 statements, 100%, no missing lines | ✓ PASS |
| Lint | `ruff check app/ tests/` | All checks passed | ✓ PASS |
| Missions suite (cross-module regression check) | `pytest tests/missions/ -q` | 83 passed, 0 failed | ✓ PASS |
| Debt-marker scan on changed files | `grep -nE "TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER" app/roster/service.py tests/roster/test_router.py tests/roster/test_service.py` | no matches | ✓ PASS |
| Reachability grep (same probe the prior verification used to prove the gap) | `grep -rn 'NoActiveMissionError' app/roster/` | matches `app/roster/service.py` | ✓ PASS — the exact grep that previously proved the gap now proves the fix |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| ROST-01 | 01-01, 01-03 | Add a drone via POST /api/roster | ✓ SATISFIED | Unaffected by this plan; full-suite pass confirms no regression |
| ROST-02 | 01-02, 01-03, 01-04 | Remove a drone via DELETE /api/roster/{drone_id} | ✓ SATISFIED (was BLOCKED) | Gap 1 closed and independently re-verified above |
| ROST-03 | 01-01, 01-03 | View roster with latest telemetry via GET /api/roster | ✓ SATISFIED | Unaffected by this plan |
| ROST-04 | 01-01, 01-02, 01-03 | roster/ mirrors missions/ layering | ✓ SATISFIED (with carried-forward backstop flag) | Unaffected by this plan; structural flag unchanged by design |

No orphaned requirements: the union of `requirements:` across all four plans ({ROST-01, ROST-02, ROST-03, ROST-04}) exactly matches REQUIREMENTS.md's Phase 1 mapping.

**Documentation note (not a functional gap):** REQUIREMENTS.md's Phase 1 traceability table currently shows ROST-01/03/04 as "Gaps Found" (commit `87e8ee1` reverted all four to Pending/Gaps-Found as a blanket phase-level flag when the initial verification found the ROST-02 blocker, rather than flipping only ROST-02). Commit `2cf2e80` then re-marked only ROST-02 as Complete after this fix. ROST-01/03/04 were never functionally broken — the initial verification independently confirmed their truths as VERIFIED — so this is stale bookkeeping left over from the blanket revert, not a regression. Recommend flipping ROST-01/03/04 back to `[x]` Complete / "Complete" in REQUIREMENTS.md now that the phase's only blocking defect is closed.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/roster/service.py` | 9-10 | `from app.missions.repository import get_active_mission_for_drone` reaches into another domain's repository layer directly rather than through `missions`' public API (`__all__` doesn't export it) | ℹ️ Info (pre-existing, documented as WR-01 in `01-REVIEW.md`, not touched by this plan) | Tight coupling to missions' internal persistence shape; low likelihood of breakage but no test would catch a silent contract change |
| `backend/app/roster/router.py` | 59-65 | DELETE handler only catches `RosterError`; if a future change to `recall_mission` ever raised a `MissionError` subclass other than `NoActiveMissionError`, it would still surface as an unhandled 500 (the new guard only catches the one class that's reachable today) | ℹ️ Info (pre-existing, documented as WR-02 in the fresh `01-REVIEW.md`, explicitly low-urgency since no current code path can trigger it) | Latent gap for a hypothetical future mission-layer change; not reachable today, `TestRemoveDroneCatchNarrowness` proves the current single reachable case is handled correctly |
| `backend/app/main.py` | 28, 62 | `telemetry_source.start(DEFAULT_FLEET)` always uses the hardcoded fleet list, never the persisted `fleet_roster` — roster changes made via the API do not survive a process restart from the telemetry side (prior verification's Gap 2 / REVIEW WR-02) | ⚠️ Warning (pre-existing, explicitly out of scope for this gap-closure plan by orchestrator direction — see `01-04-PLAN.md` `flagged_assumptions` #2) | Independently confirmed still present: `grep -n "DEFAULT_FLEET\|telemetry_source.start" app/main.py` shows the hardcoded seed is unchanged. Does not block any of ROADMAP Phase 1's four numbered Success Criteria (none require restart-survival); recommended as a tracked follow-up before Phase 4's Docker work, where container restarts become routine |
| `.planning/phases/01-roster-module/01-SECURITY.md` | — | The security threat register was never updated after the fix landed — `git log` shows it was written once (`e506596`), before plan 01-04. It still reads T-01-09 as "open — below high threshold (non-blocking)" with a forward-looking "Fix: catch NoActiveMissionError..." instruction, even though that fix is now implemented and independently verified | ℹ️ Info (documentation staleness, not a functional gap) | The actual code fix is verified correct by this report; the security register's prose just hasn't been refreshed to record closure. Recommend a follow-up doc pass to flip T-01-09's status to `closed` and record the disposition |

No `TODO`/`FIXME`/`XXX`/`HACK`/`PLACEHOLDER` markers found in any file touched by this gap-closure plan.

### Human Verification Required

None — all findings above are programmatically confirmed (fail-first reproduction I ran myself, passing/failing test evidence, source diffs, exception-hierarchy trace, structural DB-write analysis). No UI, visual, or subjective-judgment items exist in this backend-only phase.

### Gaps Summary

**Gap 1 (the phase's sole blocker) is genuinely closed.** I did not rely on the SUMMARY's self-report: I independently reverted the fix, watched the new regression test fail with the exact unhandled `NoActiveMissionError` the gap described, restored the fix, watched it pass, and separately re-ran every race-related test, the full 216-test suite, coverage, and ruff myself. The fix is narrow (catches exactly `NoActiveMissionError`, proven not to swallow other `MissionError` subclasses), sits at the correct architectural layer (service, not router), preserves the mission audit trail (structurally guaranteed — `recall()` raises before writing anything — and behaviorally proven by the tests), and is diagnosable (INFO log naming the drone_id). `01-REVIEW.md`'s fresh pass independently confirms the same conclusion with a correct root-cause trace.

Two pre-existing, non-blocking items remain open, unchanged from the prior verification and explicitly out of this gap-closure plan's scope:

1. **Gap 2 (warning, carried forward):** `backend/app/main.py` still seeds the telemetry source from a hardcoded `DEFAULT_FLEET` rather than the persisted roster, so roster changes diverge from telemetry after a process restart. Confirmed still present. Does not block any ROADMAP Phase 1 Success Criterion (none require restart-survival); recommended before Phase 4's Docker work.
2. **REQUIREMENTS.md documentation lag:** ROST-01/03/04 show "Gaps Found" from a blanket revert during the initial gaps_found run, even though their underlying functionality was never broken. Recommend flipping them back to Complete now that ROST-02 is closed.

Neither item is a functional defect in the roster module's delivered behavior, and neither is part of this plan's scope (`gap_ids: [ROST-02-TOCTOU]`). The phase goal — "Operator can manage the fleet roster through the API, kept in sync with live telemetry, using the same layered pattern as the existing missions module" — is now met for all four ROADMAP-numbered Success Criteria, with the one previously-blocking reliability defect closed and independently re-verified.

---

_Verified: 2026-08-12T18:40:00Z_
_Verifier: Claude (gsd-verifier)_
