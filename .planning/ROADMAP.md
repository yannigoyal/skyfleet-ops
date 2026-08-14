# Roadmap: SkyFleet Ops

## Overview

The DB, telemetry (simulator + MAVLink client + SSE), and missions service layer (atomic launch/recall,
budget accounting, queue, schedulers) are already built and tested — this roadmap covers only the
remaining platform. Work is sequenced by a hard dependency the research surfaced: the AI chat's
`roster_changes` action has nothing to delegate to until the roster service exists, and chat must be
built against the same service layer manual dispatch uses from day one. So: Roster module first
(small, mirrors the proven `missions/` shape), then AI Flight Director Chat (the one component with
real external-integration and validation-boundary risk), then the Frontend buildout (visualization,
dispatch bar, and the chat panel, consuming the now-stable `/api/roster` and `/api/chat` contracts),
and finally Docker packaging plus the full unit/E2E test suites — which need every API surface
finalized to be meaningful, and reuse the `LLM_MOCK` path already proven out in the chat phase.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Roster Module** - Operator can add/remove/view tracked drones through a roster service mirroring the missions module shape (completed 2026-08-12)
- [x] **Phase 2: AI Flight Director Chat** - Operator can delegate mission and roster actions to an LLM copilot, validated identically to manual dispatch (completed 2026-08-13)
- [x] **Phase 3: Frontend Buildout** - Operator gets the full ops-console UI: visualization, dispatch bar, and AI chat panel (completed 2026-08-13)
- [ ] **Phase 4: Docker Packaging & Test Suites** - Operator runs the whole platform with one command, verified by unit and E2E test suites

## Phase Details

### Phase 1: Roster Module

**Goal**: Operator can manage the fleet roster through the API, kept in sync with live telemetry, using the same layered pattern as the existing missions module.
**Mode:** mvp
**Depends on**: Nothing (builds on the already-complete DB/Telemetry/Missions layers)
**Requirements**: ROST-01, ROST-02, ROST-03, ROST-04
**Success Criteria** (what must be TRUE):

  1. Operator can add a drone via `POST /api/roster` and it immediately appears in the roster with live telemetry from the `TelemetrySource`
  2. Operator can remove a drone via `DELETE /api/roster/{drone_id}` and it stops appearing in the roster, dispatch options, and telemetry stream
  3. `GET /api/roster` returns the current roster merged with each drone's latest telemetry reading
  4. The roster module (`backend/app/roster/`) is organized as models/service/repository/router, mirroring `backend/app/missions/`

**Plans:** 4/4 plans complete

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Tracer: add a drone end-to-end (router → service → repository → SQLite → TelemetrySource) and mount the roster router in `app.main`

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Removal slice: `DELETE /api/roster/{drone_id}` with auto-recall of any active mission (D-03) and log-and-continue telemetry sync (D-04)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Error matrix, single-operator isolation, and the ROST-04 layering assertion

**Gap closure** *(from 01-VERIFICATION.md Gap 1 — run via `/gsd-execute-phase 1 --gaps-only`)*

- [x] 01-04-PLAN.md — Close the ROST-02 check→recall race: guard `remove_drone`'s recall with `except NoActiveMissionError` so DELETE returns 204 instead of an unhandled 500 when the delivery scheduler resolves the mission mid-window (REVIEW CR-01, SECURITY T-01-09)

### Phase 2: AI Flight Director Chat

**Goal**: Operator can delegate mission and roster actions to an LLM copilot through natural-language chat, with every AI-proposed action validated exactly like manual dispatch.
**Mode:** mvp
**Depends on**: Phase 1 (roster.service must exist for the chat's roster_changes actions)
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06, CHAT-07, CHAT-08
**Success Criteria** (what must be TRUE):

  1. Operator sends a message via `POST /api/chat` and receives one complete structured JSON response containing a conversational message plus any executed actions
  2. AI-issued mission launches/recalls execute through the identical `missions.service` functions manual dispatch uses — no separate trusted write path
  3. AI-issued roster add/remove actions execute through `roster.service` the same way
  4. Chat conversation history persists in `chat_messages`, and recent turns are loaded into the prompt context for follow-up messages
  5. With `LLM_MOCK=true` the backend returns deterministic responses without calling OpenRouter; invalid or failing AI-proposed actions (unknown drone id, insufficient budget, malformed JSON) surface as readable errors in the chat response rather than crashing; real calls use an explicit `response_format` schema forced to Cerebras provider routing rather than relying on auto-detection

**Plans:** 4/4 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Tracer: mock-mode chat turn end-to-end (router → context → LLM seam → chat repository → SQLite → missions.service) plus the litellm legitimacy gate and the `app.main` mount

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — CHAT-08: real LiteLLM→OpenRouter→Cerebras call with `response_format` and `provider` nested in `extra_body`, the kwarg-shape regression gate, and the gated live smoke
- [x] 02-03-PLAN.md — Recall and roster delegation through `missions.service` / `roster.service`, with the chat-versus-manual differential test and the import-boundary assertion

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 02-04-PLAN.md — CHAT-07: fourteen-scenario reference dataset and replay harness, transparency and secret-hygiene gates, and the per-turn structured log line

### Phase 3: Frontend Buildout

**Goal**: Operator has the complete ops-console UI — visualization, manual dispatch, and the AI chat panel — built against the now-stable roster/chat/telemetry/missions contracts.
**Mode:** mvp
**Depends on**: Phase 1, Phase 2 (chat panel needs the `/api/chat` contract; other panels only need existing REST/SSE and can start earlier)
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07, FE-08, FE-09
**Success Criteria** (what must be TRUE):

  1. Each roster row shows a battery sparkline, and clicking a drone opens a detail panel showing battery, altitude, speed, and current mission over time
  2. Fleet heatmap renders drones sized by mission energy cost and colored by battery health, alongside an energy-budget line chart sourced from `GET /api/fleet/history`
  3. Missions table lists drone, zone, distance, energy cost, status, and ETA for every mission, and the dispatch bar launches/recalls missions instantly with no confirmation dialog
  4. Header shows live remaining energy budget, connection status, and active mission count
  5. The AI flight-director chat panel supports message input, scrolling conversation history, a loading indicator, and inline structured confirmation cards for AI-executed actions

**Plans:** 6/6 plans complete
**UI hint**: yes

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Wave 0 validation harness (Vitest + jsdom + `@/` alias) behind a blocking package-legitimacy gate for the three undeclared dev packages

**Wave 2** *(blocked on Wave 1)*

- [x] 03-02-PLAN.md — Tracer: launch a mission and watch the budget drop — `types/fleet.ts` + `FleetOpsProvider` (poll, accumulate, refetch — D-01/D-02/D-04) + `DispatchBar` launch (D-14/D-15) + live `Header` (FE-07)

**Wave 3** *(blocked on Wave 2)*

- [x] 03-03-PLAN.md — Recall plus the full inline backend-error matrix (FE-06, D-14), and the missions table over the accumulated history with the backend's `eta_minutes` (FE-05, supersedes D-13)

**Wave 4** *(blocked on Wave 3)*

- [x] 03-04-PLAN.md — Capped altitude/speed history (D-03), roster battery sparklines (FE-01), and the drone detail panel (FE-02, D-16)

**Wave 5** *(blocked on Wave 4)*

- [x] 03-05-PLAN.md — Recharts Treemap fleet heatmap (FE-03, D-09/D-10/D-11/D-12) and the energy-budget line chart (FE-04)

**Wave 6** *(blocked on Wave 5)*

- [x] 03-06-PLAN.md — AI flight-director sidebar: `useChat` with the shared refetch (D-07/D-08), inline confirmation cards (FE-09, D-06), collapsible docked panel (FE-08, D-05)

*Waves are strictly sequential: this is a single-page console, so every plan mounts its
panels into `frontend/src/app/page.tsx` and no two plans can own that file in the same wave.*

### Phase 4: Docker Packaging & Test Suites

**Goal**: Operator can launch the whole platform with a single command, and the remaining build (roster, chat, frontend, packaging) is verified by automated backend, frontend, and E2E test suites.
**Depends on**: Phase 1, Phase 2, Phase 3 (E2E scenarios need every API surface and the frontend finalized to be meaningful)
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):

  1. A single multi-stage Docker build (Node → Python) serves the Next.js static export and FastAPI backend together on port 8000
  2. Idempotent start/stop scripts for macOS/Linux and Windows build/run/stop the container with the volume mount and `.env` file
  3. SQLite data in `database/` persists across container restarts
  4. Backend and frontend unit test suites pass, covering roster service/repository/router logic, chat/LLM structured-output parsing and validation delegation, and the new frontend components
  5. A Playwright E2E suite, isolated via `tests/docker-compose.test.yml` and run with `LLM_MOCK=true`, passes covering fresh start, roster add/remove, mission launch/recall with budget updates, visualization rendering, mocked AI chat, and SSE disconnect/reconnect resilience

**Plans:** 3/4 plans executed

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — Tracer: bind-mount Docker packaging proven through build, serve, and restart; build-context hygiene; Windows script parity
- [x] 04-02-PLAN.md — Audit the existing pytest and Vitest suites against TEST-01/02/03's exact wording, gap-fill only where uncovered

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-03-PLAN.md — Serialize the E2E harness, add shared helpers, and cover TEST-04 scenarios 1-3 (fresh start, roster add/remove, launch/recall) plus TEST-05 browser isolation

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 04-04-PLAN.md — Cover TEST-04 scenarios 4-6 (visualization rendering, mocked AI chat, SSE disconnect/reconnect) and correct the suite README

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Roster Module | 4/4 | Complete    | 2026-08-12 |
| 2. AI Flight Director Chat | 4/4 | Complete    | 2026-08-13 |
| 3. Frontend Buildout | 6/6 | Complete    | 2026-08-13 |
| 4. Docker Packaging & Test Suites | 3/4 | In Progress|  |
