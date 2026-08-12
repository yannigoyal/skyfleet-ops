---
phase: 1
slug: roster-module
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.0+ with pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `python_files = ["test_*.py"]`, `asyncio_mode = "auto"` |
| **Quick run command** | `uv run --extra dev pytest tests/roster/ -v` |
| **Full suite command** | `uv run --extra dev pytest -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run --extra dev pytest tests/roster/ -v`
- **After every plan wave:** Run `uv run --extra dev pytest -v` (full backend suite, including `tests/missions/` to catch regressions from the new `roster → missions` cross-module call)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-TBD | 01 | 1 | ROST-01 | V5 | Pydantic `Field(min_length=1)` rejects empty drone_id | unit (router) | `pytest tests/roster/test_router.py::TestAddDrone -x` | ❌ W0 | ⬜ pending |
| 01-01-TBD | 01 | 1 | ROST-01 | — | `repository.add_drone()` inserts row, raises `DroneAlreadyTrackedError` on duplicate | unit (repository) | `pytest tests/roster/test_repository.py::TestAddDrone -x` | ❌ W0 | ⬜ pending |
| 01-02-TBD | 01 | 1 | ROST-02 | — | `DELETE /api/roster/{drone_id}` removes drone; drone with active mission is auto-recalled first (D-03) | unit (service) | `pytest tests/roster/test_service.py::TestRemoveDrone -x` | ❌ W0 | ⬜ pending |
| 01-02-TBD | 01 | 1 | ROST-02 | — | Telemetry sync failure on remove is logged, not fatal (D-04) | unit (service, mocked source) | `pytest tests/roster/test_service.py::TestTelemetrySyncFailure -x` | ❌ W0 | ⬜ pending |
| 01-03-TBD | 01 | 1 | ROST-03 | — | `GET /api/roster` merges roster with latest `TelemetryCache` reading | unit (router) | `pytest tests/roster/test_router.py::TestListDrones -x` | ❌ W0 | ⬜ pending |
| 01-04-TBD | 01 | 1 | ROST-04 | — | `roster/` module layering matches `missions/` (models/service/repository/router) | structural (import check) | `pytest tests/roster/test_service.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are TBD — the planner fills exact task IDs when PLAN.md is generated; the requirement→test mapping above is authoritative going in.*

---

## Wave 0 Requirements

- [ ] `backend/tests/roster/__init__.py` — new test package (mirrors `tests/missions/`)
- [ ] `backend/tests/roster/conftest.py` — `db`/`cache` fixtures, mirroring `backend/tests/missions/conftest.py:11-27` exactly — same `tmp_path`-backed `Database` fixture pattern, same `seed_telemetry()` helper shape
- [ ] `backend/tests/roster/test_models.py` — mirrors `tests/missions/test_models.py`
- [ ] `backend/tests/roster/test_repository.py` — mirrors `tests/missions/test_repository.py`
- [ ] `backend/tests/roster/test_service.py` — new; no missions equivalent to copy verbatim since this is where the D-03 cross-module recall logic and D-04 telemetry-failure-swallowing logic live — needs a fake/mock `TelemetrySource` stub (implementing the 4-method ABC, or `unittest.mock.AsyncMock`) to test the "source raises, service logs and continues" path deterministically
- [ ] `backend/tests/roster/test_router.py` — mirrors `tests/missions/test_router.py:13-16`'s `_client(db, cache, ...)` helper pattern, using `create_roster_router` in place of `create_missions_router`

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
