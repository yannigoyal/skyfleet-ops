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

### Active

- [ ] LLM flight-director chat (`backend/app/chat/` — currently an empty stub): structured-output mission dispatch and roster changes via LiteLLM → OpenRouter (Cerebras/gpt-oss-120b), delegating to the *same* `missions.service` / `roster.service` functions used by manual dispatch — no separate "trusted" write path
- [ ] LLM mock mode (`LLM_MOCK=true`) for deterministic testing without API calls
- [ ] Frontend buildout: drone detail panel, fleet heatmap (treemap), energy-budget chart, missions table, dispatch bar, AI chat panel with inline action-confirmation cards
- [ ] Dark ops-console visual theme (amber/teal/signal-orange accents, telemetry flash animations) applied across new frontend surfaces
- [ ] Multi-stage Docker build (Node → Python) serving frontend + backend on a single port (8000)
- [ ] Start/stop scripts for macOS/Linux and Windows
- [ ] Backend unit tests (pytest) for roster, chat/LLM parsing, and any gaps in mission-ops coverage
- [ ] Frontend unit tests (React Testing Library or similar) for new components
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
*Last updated: 2026-08-12 — Phase 1 (Roster Module) complete*
