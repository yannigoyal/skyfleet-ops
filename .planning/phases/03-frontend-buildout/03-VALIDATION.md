---
phase: 03
slug: frontend-buildout
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-13
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.1.0 (declared in `frontend/package.json`) + `@testing-library/react` 16.0.0 |
| **Config file** | none — Wave 0 installs (`frontend/vitest.config.ts` does not exist yet) |
| **Quick run command** | `cd frontend && npm run build && npm run lint && npx vitest run <ComponentName>` |
| **Full suite command** | `cd frontend && npm test && npm run build` |
| **Estimated runtime** | ~30–60s (unverified — no frontend test suite has ever run in this project; ballpark for a Next.js static-export build + lint + a handful of Vitest component tests) |

---

## Sampling Rate

- **After every task commit:** `cd frontend && npm run build && npm run lint && npx vitest run <ComponentName>` for the component just touched (once Wave 0 config exists)
- **After every plan wave:** `cd frontend && npm test && npm run build`
- **Before `/gsd-verify-work`:** Full suite must be green, plus a manual UAT walkthrough against 03-UI-SPEC.md's 6 dimensions (Copywriting, Visuals, Color, Typography, Spacing, Registry Safety)
- **Max feedback latency:** ~60 seconds (local Vitest run + Next.js build, no network I/O in the automated path)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0/1 | FE-01 | — | Sparkline renders from `useTelemetryStream` history array | unit (render) | `npx vitest run DroneSparkline` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 0/1 | FE-02 | — | Detail panel shows battery/altitude/speed over time + current mission, or D-16 empty state | unit (render) | `npx vitest run DetailPanel` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 0/1 | FE-03 | — | Heatmap renders cells sized by `energy_cost_kwh`, colored by D-11 3-band thresholds, D-10 idle-drone floor applied | unit (render) | `npx vitest run FleetHeatmap` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 0/1 | FE-04 | — | Budget line chart renders from `GET /api/fleet/history` snapshots | unit (render) | `npx vitest run EnergyBudgetChart` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 0/1 | FE-05 | T-03-TBD | Missions table shows accumulated missions incl. recalled/delivered (client-side merge, not raw poll replace); ETA column renders backend `eta_minutes` verbatim | unit (`mergeMissions` logic + render) | `npx vitest run FleetOpsProvider` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 0/1 | FE-06 | T-03-TBD | Dispatch/recall calls correct endpoint, surfaces backend reason-coded error verbatim (no client-side eligibility duplication, D-14) | unit (mocked fetch) | `npx vitest run DispatchBar` | ❌ W0 | ⬜ pending |
| 03-01-07 | 01 | 0/1 | FE-07 | — | Header reflects live `remaining_kwh`/`active_mission_count`/connection status, not `page.tsx`'s hardcoded values | unit (render) | `npx vitest run Header` | ❌ W0 | ⬜ pending |
| 03-01-08 | 01 | 0/1 | FE-08 | T-03-TBD | Chat input disabled while awaiting response (D-08), transcript scrolls, no `dangerouslySetInnerHTML` on message text | unit (render + interaction) | `npx vitest run ChatPanel` | ❌ W0 | ⬜ pending |
| 03-01-09 | 01 | 0/1 | FE-09 | T-03-TBD | Confirmation cards render per D-06 format for `missions`/`roster_changes`/`errors` arrays | unit (render) | `npx vitest run ConfirmationCard` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs above are placeholders pending the planner's actual wave/task numbering — the planner should reconcile this table's Task ID column against the real PLAN.md task IDs it produces, keeping the Requirement/Test/Command columns intact.*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — set `test.environment: "jsdom"`, `test.setupFiles`, and the `@/*` path alias (mirroring `tsconfig.json`'s `paths`)
- [ ] `frontend/vitest.setup.ts` — `@testing-library/jest-dom` matchers, mock `window.EventSource`/`window.fetch` as needed per-test
- [ ] `frontend/package.json` devDependencies — add `jsdom`, `@testing-library/jest-dom`; confirm whether `@testing-library/user-event` is needed for D-08's disabled-input interaction test
- [ ] `npm install --save-dev jsdom @testing-library/jest-dom` (run inside `frontend/`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| Visual/UX conformance to 03-UI-SPEC.md across its 6 dimensions (Copywriting, Visuals, Color, Typography, Spacing, Registry Safety) | FE-01 through FE-09 (all) | Spacing, color precision, and copy tone are judgment calls not expressible as unit assertions; UI-SPEC's Checker Sign-Off section requires visual review | Run the UI-SPEC checker (`gsd-ui-checker`) or a manual UAT walkthrough against `03-UI-SPEC.md` before phase verification |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
