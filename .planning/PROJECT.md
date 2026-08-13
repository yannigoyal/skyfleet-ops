# SkyFleet Ops

## What This Is

SkyFleet Ops is a real-time operations console for a simulated last-mile drone delivery fleet. It streams live telemetry for 10 delivery drones, lets a dispatcher launch and monitor missions against a shared energy budget, and integrates an LLM "flight director" that can analyze fleet health and dispatch missions on the dispatcher's behalf. It's a demonstration capstone for an agentic AI coding course, showing how independent frontend/backend workstreams develop against a shared spec.

## Core Value

The dispatcher can watch a fleet of drones stream live telemetry, launch/recall missions against an energy budget, and delegate that same dispatching to an AI flight director through natural-language chat — all in one ATC-style console, single Docker command to run.

## Requirements

### Validated

- ✓ Fleet telemetry simulation (Ornstein-Uhlenbeck-style battery drain, squadron-correlated turbulence, wind-gust events) — telemetry phase
- ✓ MAVLink gateway client for real hardware, sharing the same interface as the simulator — telemetry phase
- ✓ Thread-safe in-memory telemetry cache with version-based change detection — telemetry phase
- ✓ SSE streaming endpoint (`/api/stream/telemetry`) — telemetry phase
- ✓ SQLite database layer: lazy init, schema, seed data (`backend/app/db/`) — db phase
- ✓ Fleet operations service/repository/router: atomic mission launch/recall, energy-budget accounting, mission queue, assignment scheduler (`backend/app/missions/`, 962 lines) — missions phase
- ✓ Next.js frontend shell: header, connection-status dot, fleet roster panel, SSE consumption hook (`frontend/src/`) — telemetry phase
- ✓ Roster management module (`backend/app/roster/`: models/service/repository/router mirroring the `missions/` shape) — add/remove/view tracked drones, kept in sync with live telemetry, including the check→recall race guard for concurrent mission resolution — Phase 1
- ✓ LLM flight-director chat (`backend/app/chat/`): structured-output mission dispatch and roster changes via LiteLLM → OpenRouter (Cerebras/gpt-oss-120b), delegating to the same `missions.service` / `roster.service` functions used by manual dispatch — Phase 2
- ✓ LLM mock mode (`LLM_MOCK=true`) for deterministic testing without API calls — Phase 2
- ✓ Backend unit tests (pytest) for telemetry, db, missions, roster, and chat/LLM — 300 tests passing across `backend/tests/` — Phases 1-2, confirmed still green after Phase 3
- ✓ Frontend buildout: fleet roster with battery sparklines, drone detail panel, dispatch bar (launch/recall), missions table, fleet heatmap (treemap), energy-budget chart, AI flight-director chat panel with inline action-confirmation cards — Phase 3 (`frontend/src/components/`, `frontend/src/lib/`)
- ✓ Dark ops-console visual theme (amber/teal/signal-orange accents) applied across all frontend surfaces per `03-UI-SPEC.md` — Phase 3
- ✓ Frontend unit tests (Vitest + Testing Library) — 81 tests across 14 files, `frontend/vitest.config.ts` — Phase 3

### Active

- [ ] Multi-stage Docker build (Node → Python) serving frontend + backend on a single port (8000)
- [ ] Start/stop scripts for macOS/Linux and Windows
- [ ] Playwright E2E test suite with `docker-compose.test.yml`, run against `LLM_MOCK=true`

### Out of Scope

- Authentication / multi-tenant support — single-operator demo app; schema has `operator_id` columns for future extensibility but no auth is built now
- Partial/multi-leg mission dispatch or en-route re-routing — mission launches are atomic by design, dramatically simplifying fleet math
- WebSocket-based real-time transport — SSE chosen instead (one-way push is sufficient, simpler, universal browser support)
- Postgres or any external database server — SQLite is sufficient for a single-operator, no-auth app
- Cloud deployment (Terraform/App Runner) — noted as a stretch goal in PLAN.md, not part of this milestone's core build

## Context

- This is a course capstone demonstrating orchestrated coding agents building from a shared spec (`planning/PLAN.md`).
- The telemetry subsystem is complete and tested: 69 tests passing, 83% coverage, documented in `planning/TELEMETRY_SUMMARY.md`. It lives in `backend/app/telemetry/` (8 modules, ~650 lines) and exposes `TelemetryCache` + `create_telemetry_source()` as the integration surface for downstream code (mission validation, fleet health scoring, SSE streaming).
- A codebase map exists at `.planning/codebase/` (STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, INTEGRATIONS, CONCERNS) — consult before planning phases that touch existing code.
- Full technical spec, API contracts, database schema, and LLM integration details live in `planning/PLAN.md` — this is the shared contract that all phases build against; do not duplicate it here, reference it.
- Corrected during research (architecture dimension): the codebase is further along than initially assumed. DB layer and mission-ops (atomic launch/recall, budget accounting, queue, assignment scheduler — `backend/app/missions/`, 962 lines) are already built and tested. Only `roster/` and `chat/` are empty stubs; the frontend has just the header, connection dot, and roster panel. Remaining build order per research: Roster → Chat/LLM (built against the same service layer as manual dispatch, from day one with `LLM_MOCK`) → Frontend buildout → Docker/E2E.
- This is a self-paced project with no external deadline. The user explicitly prioritizes correctness, quality, and production-quality implementation over speed.
- Full workflow rigor requested: research, plan-check, and verifier agents enabled for every phase.
- Scope is the *entire* remaining platform in one milestone — database, mission execution, chat, frontend, Docker packaging, and E2E tests — not a narrower vertical slice.

## Constraints

- **Tech stack**: Backend is FastAPI (Python) managed via `uv`; frontend is Next.js/TypeScript as a static export; database is SQLite. These are fixed by PLAN.md, not open decisions.
- **Architecture**: Single Docker container, single port (8000), FastAPI serves both `/api/*` routes and the static frontend build — no CORS configuration needed, no docker-compose in production.
- **LLM integration**: Must use the `cerebras` skill to call LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` on Cerebras inference, with structured outputs. `OPENROUTER_API_KEY` is available in the project root `.env`.
- **Telemetry interface**: All downstream code (mission validation, SSE, frontend) must consume telemetry through the existing `TelemetryCache` / `TelemetrySource` interface — do not bypass or duplicate it.
- **Testing**: E2E tests must default to `LLM_MOCK=true` for speed/determinism; Playwright infra stays isolated in `tests/` via `docker-compose.test.yml`, not in the production image.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build entire remaining platform in one milestone (not a vertical slice) | User wants the complete spec delivered end-to-end per PLAN.md | — Pending |
| Full workflow rigor (research + plan-check + verifier every phase) | User explicitly values correctness/quality over speed on this self-paced project | — Pending |
| Docker packaging and E2E tests included in this milestone's scope | User confirmed PLAN.md's full scope, not deferred to a later pass | — Pending |
| Phase 3 built as 6 strictly sequential waves (tracer slice first, then feature slices), one plan per wave | Every plan after 03-01 shares `page.tsx` and/or `FleetOpsProvider`; parallel execution would conflict | Shipped clean — all 6 waves merged with zero cross-plan conflicts |
| Code review's 1 critical + 4 warning findings (incl. a real crash bug in `FleetOpsProvider.refetch()` with no error handling) fixed directly by the orchestrator rather than via the fix-agent pipeline | Fix-agent dispatch hit a session usage-quota error mid-review; findings were small, well-scoped, and already had exact suggested diffs | Fixed in commit `703dbc7`, independently re-verified by the phase verifier (tsc clean, 81/81 tests, build succeeds) |
| Phase 3 tagged `mode: mvp` in ROADMAP.md but its goal isn't authored as a User Story | Goal was written before MVP-mode tagging was retrofitted onto the roadmap | Flagged by the verifier as unresolved — recommend `/gsd mvp-phase 3` to reformat or clearing the `mvp` flag before Phase 4 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-13 — Phase 3 (Frontend Buildout) complete*
