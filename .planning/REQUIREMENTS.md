# Requirements: SkyFleet Ops

**Defined:** 2026-08-12
**Core Value:** The dispatcher can watch a fleet of drones stream live telemetry, launch/recall missions against an energy budget, and delegate that same dispatching to an AI flight director through natural-language chat — all in one ATC-style console, single Docker command to run.

## v1 Requirements

Requirements for this milestone (the entire remaining scope of PLAN.md). Database and fleet-operations service layer (launch/recall/budget accounting, mission queue, assignment scheduler) are already built and tested — see PROJECT.md Validated section — and are not re-listed here.

### Roster

- [x] **ROST-01**: Operator can add a drone to the fleet roster via `POST /api/roster`
- [x] **ROST-02**: Operator can remove a drone from the fleet roster via `DELETE /api/roster/{drone_id}`
- [x] **ROST-03**: Operator can view the current fleet roster with latest telemetry via `GET /api/roster`
- [x] **ROST-04**: Roster module (`backend/app/roster/`) follows the same models/service/repository/router layering as `backend/app/missions/`

### Chat (AI Flight Director)

- [x] **CHAT-01**: Operator can send a chat message via `POST /api/chat` and receive a complete structured JSON response (message + executed actions)
- [x] **CHAT-02**: AI flight director can launch missions on the operator's behalf through structured output, validated through the identical service-layer function manual dispatch uses (no separate "trusted" write path)
- [x] **CHAT-03**: AI flight director can recall missions on the operator's behalf through structured output, validated the same way
- [x] **CHAT-04**: AI flight director can add/remove roster drones through structured output, validated the same way
- [x] **CHAT-05**: Chat conversation history persists in `chat_messages` and recent history is loaded into the prompt context for follow-up messages
- [ ] **CHAT-06**: When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenRouter
- [ ] **CHAT-07**: When an LLM-issued mission/roster action fails validation (e.g., insufficient budget), the error is included in the chat response so the LLM can inform the operator
- [ ] **CHAT-08**: LLM calls use LiteLLM → OpenRouter → `openrouter/openai/gpt-oss-120b` on Cerebras inference with an explicit `response_format` schema (not relying on auto-detection, per research: LiteLLM's `supports_response_schema()` can silently drop the schema for OpenRouter)

### Frontend — Visualization & Detail

- [ ] **FE-01**: Per-drone sparkline mini-chart renders next to each roster row, built from the battery history already accumulated by `useTelemetryStream`
- [ ] **FE-02**: Clicking a drone in the roster opens a detail panel showing battery, altitude, speed, and current mission over time
- [ ] **FE-03**: Fleet heatmap (treemap) renders with rectangles sized by mission energy cost and colored by battery health (green = healthy, red = critical)
- [ ] **FE-04**: Energy-budget line chart shows remaining kWh over time, sourced from `GET /api/fleet/history`

### Frontend — Dispatch & Missions

- [ ] **FE-05**: Missions table shows drone, zone, distance, energy cost, status, and ETA for all missions
- [ ] **FE-06**: Dispatch bar (drone field, zone field, distance field, launch button, recall button) launches/recalls missions instantly with no confirmation dialog
- [ ] **FE-07**: Header shows live remaining energy budget, connection status indicator, and active mission count

### Frontend — AI Chat Panel

- [ ] **FE-08**: AI flight director chat panel (docked/collapsible sidebar) has a message input, scrolling conversation history, and a loading indicator while waiting for a response
- [ ] **FE-09**: Mission launches and roster changes executed by the AI are shown inline in the chat transcript as structured confirmation cards (action, params, result) — not buried in prose

### Deployment

- [ ] **DEPLOY-01**: Multi-stage Dockerfile builds the Next.js static export and Python backend into a single image serving both on port 8000
- [ ] **DEPLOY-02**: `scripts/start_mac.sh` / `scripts/stop_mac.sh` are idempotent and build/run/stop the container with the volume mount and `.env` file
- [ ] **DEPLOY-03**: `scripts/start_windows.ps1` / `scripts/stop_windows.ps1` are idempotent PowerShell equivalents
- [ ] **DEPLOY-04**: SQLite database persists across container restarts via the `database/` bind mount

### Testing

- [ ] **TEST-01**: Backend unit tests (pytest) cover roster service/repository/router logic
- [ ] **TEST-02**: Backend unit tests cover chat/LLM structured-output parsing, malformed-response handling, and mission/roster validation within the chat flow
- [ ] **TEST-03**: Frontend unit tests (React Testing Library or similar) cover the new components: detail panel, heatmap, budget chart, missions table, dispatch bar, chat panel
- [ ] **TEST-04**: Playwright E2E suite (run with `LLM_MOCK=true`) covers: fresh start with default roster/budget, roster add/remove, mission launch/recall with budget updates, visualization rendering, AI chat mocked flow, and SSE disconnect/reconnect resilience
- [ ] **TEST-05**: `tests/docker-compose.test.yml` spins up the app container plus a Playwright container, keeping browser dependencies out of the production image

## v2 Requirements

Deferred — not part of this milestone.

### Deployment

- **DEPLOY-05**: Terraform configuration for AWS App Runner deployment

## Out of Scope

| Feature | Reason |
|---------|--------|
| Authentication / multi-tenant support | Single-operator demo app; `operator_id` columns exist for future extensibility only |
| Partial/multi-leg mission dispatch, en-route re-routing | Deliberately excluded per PLAN.md — atomic launches keep fleet math simple; reintroducing this is a product decision, not a default extension |
| Confirmation dialog before AI-executed actions | Would kill the fluid agentic demo experience; stakes are zero (simulated fleet/budget) — mitigated instead with rich inline confirmation cards (FE-09) |
| WebSocket transport for chat or telemetry | SSE (one-way, already built) and plain POST (chat) are simpler and sufficient; mixing concerns into one socket adds complexity for no UX gain |
| Free-text LLM output parsed with regex/heuristics | Structured JSON output validated by Pydantic is required (CHAT-01–CHAT-04) — regex parsing silently drops or misfires actions |
| LLM writing directly to the database | LLM only proposes actions; execution always routes through the same service-layer functions manual dispatch uses (CHAT-02–CHAT-04) |
| Push/email/SMS alerting | Not in PLAN.md scope; visual alerting (color coding, flash animations) is sufficient for a single-session demo |
| Cloud deployment (Terraform/App Runner) | Explicit stretch goal in PLAN.md, deferred to v2 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ROST-01 | Phase 1 | Complete |
| ROST-02 | Phase 1 | Complete |
| ROST-03 | Phase 1 | Complete |
| ROST-04 | Phase 1 | Complete |
| CHAT-01 | Phase 2 | Complete |
| CHAT-02 | Phase 2 | Complete |
| CHAT-03 | Phase 2 | Complete |
| CHAT-04 | Phase 2 | Complete |
| CHAT-05 | Phase 2 | Complete |
| CHAT-06 | Phase 2 | Pending |
| CHAT-07 | Phase 2 | Pending |
| CHAT-08 | Phase 2 | Pending |
| FE-01 | Phase 3 | Pending |
| FE-02 | Phase 3 | Pending |
| FE-03 | Phase 3 | Pending |
| FE-04 | Phase 3 | Pending |
| FE-05 | Phase 3 | Pending |
| FE-06 | Phase 3 | Pending |
| FE-07 | Phase 3 | Pending |
| FE-08 | Phase 3 | Pending |
| FE-09 | Phase 3 | Pending |
| DEPLOY-01 | Phase 4 | Pending |
| DEPLOY-02 | Phase 4 | Pending |
| DEPLOY-03 | Phase 4 | Pending |
| DEPLOY-04 | Phase 4 | Pending |
| TEST-01 | Phase 4 | Pending |
| TEST-02 | Phase 4 | Pending |
| TEST-03 | Phase 4 | Pending |
| TEST-04 | Phase 4 | Pending |
| TEST-05 | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-08-12*
*Last updated: 2026-08-12 after roadmap creation (corrected v1 total from 29 to 30 — recount of listed requirements)*
