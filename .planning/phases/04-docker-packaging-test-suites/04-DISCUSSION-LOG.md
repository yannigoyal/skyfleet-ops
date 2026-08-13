# Phase 4: Docker Packaging & Test Suites - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-13
**Phase:** 4-Docker Packaging & Test Suites
**Areas discussed:** Docker Volume Strategy, Existing Unit Test Coverage, E2E Assertion Depth, Static Export / StaticFiles Serving Risk

---

## Docker Volume Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Switch to bind mount (matches spec) | Update docker-compose.yml and start_mac.sh/start_windows.ps1 to bind-mount ./database, matching PLAN.md §11 and DEPLOY-04's literal wording. Operator can see/back up skyfleet.db directly on the host. | ✓ |
| Keep named volume | Leave the existing named-volume setup as-is — it already satisfies "persists across restarts" functionally, and rewriting working scripts adds re-verification risk for a demo app. | |

**User's choice:** Switch to bind mount (matches spec)
**Notes:** docker/docker-compose.yml and scripts/start_mac.sh currently use a named Docker volume (`skyfleet-data:/app/database`), discovered by direct file inspection — a genuine deviation from PLAN.md §11's specified bind-mount command.

---

## Existing Unit Test Coverage

| Option | Description | Selected |
|--------|-------------|----------|
| Audit for gaps, don't rewrite (Recommended) | Treat existing 300+81 tests as the baseline. Phase 4 runs a coverage audit against TEST-01/02/03's exact wording, adds only what's missing, and marks the requirement satisfied by the existing suite plus any gap-fill. | ✓ |
| Full fresh review of all backend/frontend tests | Re-examine every existing test file for quality/completeness against TEST-01/02/03 in detail before deciding what (if anything) to add — more thorough, more time. | |

**User's choice:** Audit for gaps, don't rewrite (Recommended)
**Notes:** Confirmed on disk: backend/tests/roster/ and backend/tests/chat/ already have full test suites (models, repository, router, service); frontend has .test.tsx files for DetailPanel, FleetHeatmap, DispatchBar, ChatPanel, ConfirmationCard, and others — built during Phases 1–3.

---

## E2E Assertion Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Structural checks (Recommended) | Assert the heatmap/chart/sparkline DOM elements render with expected data-driven attributes (e.g. correct number of treemap cells, chart has data points) — fast, stable, avoids pixel-fragile visual assertions. | ✓ |
| Visual/pixel-level checks | Add Playwright screenshot comparisons for charts/heatmap — catches visual regressions but is slower and more brittle (flaky on font/rendering differences across environments). | |

**User's choice:** Structural checks (Recommended)
**Notes:** Only tests/specs/health.spec.ts exists today; the other 5 TEST-04 scenarios need new spec files.

---

## Static Export / StaticFiles Serving Risk

| Option | Description | Selected |
|--------|-------------|----------|
| Smoke-test only (Recommended) | Since it's a single-page app with one route, a build + container-start + GET / E2E check (already covered by the "fresh start" TEST-04 scenario) is sufficient — the flagged risk mainly applies to multi-route apps. | ✓ |
| Dedicated edge-case tests | Add explicit tests for direct URL access, browser refresh, and any 404/fallback behavior — more thorough given this was explicitly flagged as a concern, even for a single route. | |

**User's choice:** Smoke-test only (Recommended)
**Notes:** STATE.md's Phase 3 handoff explicitly flagged this risk. Verified frontend/next.config.js does not set trailingSlash (defaults to false). App has exactly one route (frontend/src/app/page.tsx).

---

## Claude's Discretion

- `backend/app/demo/mission_demo.py` (untracked scratch utility) — leave as-is, not part of DEPLOY/TEST requirements.
- Windows script verification depth — no Windows runner available in this environment; verify via code review against bash equivalents rather than live execution.
- Exact migration/reset approach for moving the named-volume database to the new bind mount (D-01).

## Deferred Ideas

None — discussion stayed within phase scope.
