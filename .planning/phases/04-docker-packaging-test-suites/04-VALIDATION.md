---
phase: 04
slug: docker-packaging-test-suites
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-14
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

This phase spans three independent frameworks — no single "quick run" covers the whole phase.

| Property | Backend | Frontend | E2E |
|----------|---------|----------|-----|
| **Framework** | pytest 8.3+, `asyncio_mode = "auto"` | Vitest 2.1+, jsdom | Playwright 1.48 |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` | `frontend/vitest.config.ts` | `tests/playwright.config.ts` |
| **Quick run command** | `cd backend && uv run --extra dev pytest -v` | `cd frontend && npm test` | N/A — E2E has no "quick" subset; full suite only |
| **Full suite command** | (same as quick — 300 tests) | (same as quick — 81 tests) | `cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit` |
| **Estimated runtime** | ~6s (verified live this session) | ~4s (verified live this session) | ~2-5 min (image build + browser boot dominate) |

---

## Sampling Rate

- **After every task commit:** Run backend quick run + frontend quick run (both complete in under 6s combined, verified live)
- **After every plan wave:** Run full E2E suite (`docker compose -f tests/docker-compose.test.yml up --build --abort-on-container-exit`) — slower (image build + browser boot), run once per wave not per task
- **Before `/gsd-verify-work`:** Full E2E suite green, plus backend (300 tests) and frontend (81 tests) suites green
- **Max feedback latency:** ~6s for unit-level tasks (Docker/script edits, unit test gap-fill); ~5 min for E2E-spec tasks (bounded by container build+boot, not test logic)

---

## Per-Task Verification Map

Pre-planning approximation keyed by requirement ID (research-derived); the planner cross-references
each row to its actual `{phase}-{plan}-{task}` ID when PLAN.md files are created.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| DEPLOY-01 | Image builds, serves both frontend+API on 8000 | smoke (scripted) | `docker build -f docker/Dockerfile -t skyfleet-ops . && docker run ...` + curl checks | N/A — verified via TEST-04 fresh-start E2E scenario | ⬜ pending |
| DEPLOY-02 | `start_mac.sh`/`stop_mac.sh` idempotent, bind-mount volume | manual/code-review | Run twice, assert same end state | N/A — shell scripts, guard clauses verified by reading | ⬜ pending |
| DEPLOY-03 | `start_windows.ps1`/`stop_windows.ps1` idempotent equivalents | code-review only | No Windows runner available — code review against bash logic | N/A | ⬜ pending |
| DEPLOY-04 | SQLite persists across container restart via bind mount | E2E | `fresh-start.spec.ts` (restart scenario) | ❌ Wave 0 | ⬜ pending |
| TEST-01 | Backend unit tests cover roster service/repository/router | unit | `pytest backend/tests/roster/ -v` | ✅ existing, verified passing | ✅ green |
| TEST-02 | Backend unit tests cover chat/LLM parsing, malformed-response, validation | unit | `pytest backend/tests/chat/ -v` | ✅ existing, verified passing | ✅ green |
| TEST-03 | Frontend unit tests cover 6 named components | unit | `npm test -- src/components/{DetailPanel,FleetHeatmap,EnergyBudgetChart,MissionsTable,DispatchBar}.test.tsx src/components/chat/ChatPanel.test.tsx` | ✅ existing, verified passing | ✅ green |
| TEST-04.1 | Fresh start: default roster, 500kWh, telemetry streaming | E2E | `tests/specs/fresh-start.spec.ts` | ❌ Wave 0 | ⬜ pending |
| TEST-04.2 | Roster add/remove (API-driven, UI reflects) | E2E | `tests/specs/roster.spec.ts` | ❌ Wave 0 | ⬜ pending |
| TEST-04.3 | Mission launch/recall + budget updates | E2E | `tests/specs/missions.spec.ts` | ❌ Wave 0 | ⬜ pending |
| TEST-04.4 | Visualization rendering (structural assertions, per D-03) | E2E | `tests/specs/visualization.spec.ts` | ❌ Wave 0 | ⬜ pending |
| TEST-04.5 | Mocked AI chat flow | E2E | `tests/specs/chat.spec.ts` | ❌ Wave 0 | ⬜ pending |
| TEST-04.6 | SSE disconnect/reconnect resilience | E2E | `tests/specs/sse-resilience.spec.ts` | ❌ Wave 0 | ⬜ pending |
| TEST-05 | Playwright isolated in test-only compose, prod image untouched | infra | `tests/docker-compose.test.yml` | ✅ existing, verified correct | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/specs/fresh-start.spec.ts` — covers DEPLOY-04 (restart persistence) + TEST-04 scenario 1
- [ ] `tests/specs/roster.spec.ts` — covers TEST-04 scenario 2 (via `request` fixture — no manual roster UI exists)
- [ ] `tests/specs/missions.spec.ts` — covers TEST-04 scenario 3
- [ ] `tests/specs/visualization.spec.ts` — covers TEST-04 scenario 4 (structural assertions only, per D-03)
- [ ] `tests/specs/chat.spec.ts` — covers TEST-04 scenario 5 (uses `mock_reply()`'s `"launch"`/`"recall"` keyword contract)
- [ ] `tests/specs/sse-resilience.spec.ts` — covers TEST-04 scenario 6
- [ ] `.dockerignore` — not a test gap but a Wave-0-appropriate hardening file (secret leakage into build context)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `start_windows.ps1`/`stop_windows.ps1` idempotency | DEPLOY-03 | No Windows runner available in this environment (CONTEXT.md Claude's Discretion) | Code-review against `start_mac.sh`/`stop_mac.sh`'s equivalent guard clauses (image-exists check, `docker rm -f` before rerun) line-by-line |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (7 new E2E specs + `.dockerignore`)
- [ ] No watch-mode flags
- [ ] Feedback latency < 6s (unit) / < 5min (E2E)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
