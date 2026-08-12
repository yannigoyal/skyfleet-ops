# Project Research Summary

**Project:** SkyFleet Ops — AI Drone Delivery Command Center
**Domain:** Real-time fleet-ops console (FastAPI + SQLite backend, Next.js static-export frontend, LLM-driven agentic mission dispatch)
**Researched:** 2026-08-12
**Confidence:** MEDIUM-HIGH

## Executive Summary

SkyFleet Ops is a single-operator, single-container ops console: a live telemetry dashboard for a simulated drone fleet, a mission-dispatch system gated by a shared energy budget, and an LLM "flight director" that can read fleet state and execute the same launch/recall/roster actions a human dispatcher would through a chat interface. Products in this category (aerospace mission control, fleet-management dashboards, agentic copilots) converge on a small set of proven patterns: a scannable live-status grid, a persistent action/history log, visible resource accounting, and — for agentic surfaces — a strict rule that the AI and the manual UI must execute mutations through one shared, validated service layer rather than duplicating business logic. SkyFleet Ops already follows this instinct in its own spec (PLAN.md §9 requires chat actions to go through "the same validation as manual dispatch"), and the architecture research confirms the existing codebase already implements this shape for missions.

Critically, architecture research found the project is **further along than PROJECT.md's checklist suggests**: the database layer, telemetry (simulator + SSE), and a full missions module (models/service/repository/router, atomic launch/recall, budget accounting, background schedulers) are already built and tested. Only `roster/` and `chat/` are unbuilt stubs, and the frontend has only the header, roster panel, and connection indicator — no detail panel, heatmap, budget chart, missions table, dispatch bar, or chat UI. The roadmap should treat DB + Missions as done and sequence remaining work as **Roster → Chat/LLM → Frontend buildout (parallelizable once Roster's contract is stable) → Docker/E2E**.

The primary risks are concentrated in three places: (1) concurrency correctness in the energy-budget/mission-eligibility read-then-write path, which the codebase's own `CONCERNS.md` already flags as a live bug pattern that chat will make worse by adding a second concurrent caller; (2) treating LLM structured output as fully validated because it matched a JSON schema, when it can still contain hallucinated drone IDs, invalid zones, or malformed/truncated responses — both classes of failure must be caught by the same validation the manual API already enforces, never a separate "trusted" chat path; and (3) infrastructure gotchas specific to this app's single-port packaging (SQLite lazy-init races on cold start, Next.js static-export routing/serving mismatches with FastAPI's `StaticFiles`, and SSE `EventSource` connection-lifecycle bugs). None of these require new infrastructure or scope changes — they require discipline in reusing the existing service-layer pattern and adding targeted concurrency/adversarial tests where PLAN.md and CONCERNS.md already point.

## Key Findings

### Recommended Stack

The remaining stack decisions are narrow: keep stdlib `sqlite3` (no ORM) matching the existing `backend/app/db/connection.py` pattern; use LiteLLM → OpenRouter for the chat call, but do **not** rely on LiteLLM's automatic `response_format` support-check for OpenRouter models — pass an explicit `response_format` dict and force provider routing to Cerebras (`extra_body={"provider": {"only": ["Cerebras"], "require_parameters": true}}`), since OpenRouter is not on LiteLLM's list of confirmed structured-output providers and a community-reported issue shows the auto-detection can silently drop schema enforcement. Stay on Next.js 15.x (no reason to chase 16.x mid-project) with `output: 'export'`, and use Recharts (already installed) for the line chart, sparklines, and treemap heatmap — it's the dominant React charting library and has a native `Treemap` primitive, unlike Lightweight Charts which PLAN.md mentions but which has no treemap support.

**Core technologies:**
- stdlib `sqlite3`, no ORM — matches existing lazy-init/WAL pattern; a 6-table single-writer schema doesn't need SQLAlchemy/SQLModel
- LiteLLM 1.96.x → OpenRouter (`openrouter/openai/gpt-oss-120b` via Cerebras) — unified completion API, but requires explicit `response_format` dict + forced provider routing, not the default auto-detection
- Next.js 15.x static export (`output: 'export'`) — unchanged behavior vs. 16.x, avoids unbudgeted upgrade risk
- Recharts (2.13.x installed, or deliberate upgrade to 3.x as its own task) — line chart, sparklines (minimal AreaChart), and Treemap-based heatmap with a custom color-by-battery `content` renderer

### Expected Features

PLAN.md already locks full feature scope for this milestone — feature research validates it against real fleet-ops/copilot patterns rather than proposing changes. Nothing should be cut; the only judgment calls are build order and which patterns to borrow from the copilot-UX literature (inline structured confirmation cards, not gated approval).

**Must have (table stakes):**
- Live telemetry grid with severity color-coding — already built
- Connection/health status indicator — already built (needs reconnect-state wiring, see pitfalls)
- Per-drone detail drill-down, resource/budget accounting always visible, mission history table
- Manual dispatch controls that remain independent of and equally capable as the AI chat

**Should have (differentiators):**
- LLM copilot that reads live fleet state AND executes mission/roster changes through the same validated service layer as manual dispatch — this is the project's actual differentiator
- Inline, structured (not prose-only) confirmation cards for every AI-executed action
- Fleet heatmap (treemap: size = mission energy cost, color = battery health) and accumulated client-side sparklines
- Deterministic `LLM_MOCK=true` mode as a first-class code path (required for E2E, not polish)

**Defer (v2+, explicitly out of this milestone per PLAN.md):**
- Confirmation dialogs before AI actions (deliberately rejected — auto-execute with rich after-the-fact transparency instead)
- Partial/multi-leg mission dispatch, WebSocket bidirectional channel, free-text/regex action parsing, full auth/multi-tenant, push/email/SMS alerting — all explicitly identified as anti-features/scope traps to avoid reintroducing

### Architecture Approach

The system is layered as Router → Service → Repository → Database, with the telemetry cache as a read-only fleet-state source consumed by SSE, missions eligibility checks, and the chat context assembler. The critical architectural rule for this milestone: **the chat/LLM layer proposes actions but never executes mutations itself** — it parses structured output into a Pydantic model, then calls the exact same `missions.service.launch_mission()`/`recall_mission()` and (new) `roster.service.add_drone()`/`remove_drone()` functions the REST routers already call, reusing every existing domain exception and validation rule. This is already partly proven out by the existing missions module and just needs to be extended, not invented.

**Major components:**
1. `roster/` (new) — mirrors the existing `missions/` module shape exactly (models/service/repository/router); must sync roster changes with the `TelemetrySource` (`add_drone()`/`remove_drone()`) in the same operation so the DB and live SSE stream don't drift
2. `chat/` (new) — `context.py` (read-only fleet-context assembler, testable without the LLM), `llm_client.py` (LiteLLM/OpenRouter call + `LLM_MOCK` branch, following the same strategy-pattern idiom already used for the telemetry source), `service.py` (orchestrates context → LLM → delegates every proposed action to missions/roster service, collects errors), `repository.py` (chat_messages persistence)
3. Existing `missions/`, `telemetry/`, `db/` — unchanged, already complete and tested; this milestone extends the codebase's established conventions rather than introducing new ones
4. Frontend — roster grid/detail panel/heatmap/budget chart/missions table/dispatch bar/chat panel, all consuming existing or soon-to-exist REST/SSE contracts; can be built largely in parallel with the chat backend once the `/api/roster` and `/api/chat` contracts are stable

### Critical Pitfalls

1. **Read-then-write budget/eligibility race (TOCTOU)** — concurrent launches (manual + chat-driven) can both pass validation before either writes, overdrawing budget or double-assigning a drone. Fix with a single atomic conditional UPDATE (`WHERE energy_budget_kwh >= ?`, check `rowcount`) inside the existing `asyncio.Lock`-serialized transaction, plus a partial unique index preventing two `en_route` rows per drone — verified with an `asyncio.gather` concurrency test, not just sequential manual testing.
2. **SQLite lazy-init race on cold start** — concurrent first requests can both observe "no tables" and race to create/seed, producing duplicate seed rows or `table already exists` errors. Fix by running init synchronously in FastAPI's `lifespan`/startup event rather than per-request, or guard lazy init with the existing write lock and idempotent `CREATE TABLE IF NOT EXISTS`/`INSERT OR IGNORE`.
3. **LLM auto-executes hallucinated or invalid actions** — structured output guarantees JSON *shape*, not semantic correctness (unknown drone_id, invented zone, negative distance). Every LLM-issued action must route through the identical validation/execution function the manual REST endpoints use — never a separate "trusted" chat path — with unknown IDs/out-of-range values rejected and surfaced as errors in the chat response, not silently dropped or executed.
4. **Malformed/truncated LLM response crashes the chat turn** — naive `json.loads()` + field access on a non-conformant response either 500s or executes garbage. Parse through a strict Pydantic model with try/except; on failure return a graceful fallback chat message, never partially execute an unvalidated response; explicitly test this path under `LLM_MOCK=true`.
5. **EventSource connection leaks and no-snapshot-on-reconnect** — recreating `EventSource` on every React re-render multiplies connections; missing a snapshot-on-connect/reconnect leaves the UI stuck on "Waiting for telemetry..." Fix with a single stable connection per mount (empty-deps `useEffect` + cleanup) and a full-snapshot push from the backend on every new/reconnected client.

## Implications for Roadmap

Based on combined research, the actual remaining build (not a from-scratch rebuild) should be sequenced as follows. DB, telemetry, and missions are already complete and should not be re-planned.

### Phase 1: Roster Module
**Rationale:** Small, isolated, no new architectural risk — mirrors the already-proven `missions/` shape. It's a hard prerequisite for chat, since the LLM's `roster_changes` action needs a working service to delegate to.
**Delivers:** `backend/app/roster/{models,service,repository,router}.py`, `GET/POST/DELETE /api/roster`, roster changes synced with `TelemetrySource`.
**Addresses:** "Manage the fleet roster" table-stakes feature (FEATURES.md).
**Avoids:** Roster/telemetry drift pitfall (roster DB write and `TelemetrySource.add_drone()`/`remove_drone()` must happen in the same operation).

### Phase 2: LLM Chat Integration
**Rationale:** Depends on Roster (Phase 1) and existing Missions being callable; this is the single component with real integration complexity (external API, structured-output parsing, cross-service delegation) so it earns its own dedicated phase.
**Delivers:** `backend/app/chat/{context,llm_client,service,repository,router}.py`, `POST /api/chat`, `LLM_MOCK=true` deterministic path built alongside the real path from the start (not bolted on later).
**Uses:** LiteLLM → OpenRouter with explicit `response_format` dict + forced Cerebras provider routing (STACK.md); Pydantic schema matching PLAN.md §9.
**Implements:** "LLM Proposes, Service Layer Executes" pattern — chat never writes to DB/cache directly, always delegates to `missions.service`/`roster.service`.
**Avoids:** Pitfalls 3 (hallucinated/invalid actions) and 4 (malformed response crashes) — both should be named acceptance criteria with adversarial `LLM_MOCK` test cases (unknown drone_id, negative distance, malformed JSON).

### Phase 3: Frontend Buildout
**Rationale:** Everything depending only on existing REST/SSE contracts (detail panel, heatmap, budget chart, missions table, dispatch bar) can start in parallel with Phase 2; the AI chat panel specifically depends on the `/api/chat` contract, so sequence it last within this phase or stub it against the documented schema.
**Delivers:** Full console per PLAN.md §10 — roster grid+sparklines, detail panel, heatmap, budget chart, missions table, dispatch bar, chat panel with inline structured confirmation cards, header status/budget.
**Addresses:** All remaining table-stakes and differentiator features from FEATURES.md (heatmap, sparklines, inline AI action confirmations).
**Avoids:** Pitfall 5 (EventSource connection leaks / no reconnect snapshot) — single stable `EventSource` per mount, wired to the existing green/yellow/red indicator.

### Phase 4: Docker Packaging + E2E Tests
**Rationale:** Must come last — Playwright E2E scenarios (PLAN.md §12) exercise roster, missions, and chat end-to-end and need all API surfaces finalized; `LLM_MOCK=true` should already be proven out by Phase 2 so E2E chat scenarios exercise an existing, tested mock path.
**Delivers:** Multi-stage Dockerfile (Node → Python), single-port FastAPI serving of the Next.js static export, start/stop scripts, `tests/docker-compose.test.yml` + Playwright suite covering PLAN.md §12's key scenarios.
**Uses:** `StaticFiles` mounted after all `/api/*` routers, with build-verification (`test -f static/index.html`) and a route-fallback smoke test.
**Avoids:** Pitfall 6 (static-export/FastAPI routing collisions, silent empty-build failures) and Pitfall 2 (SQLite lazy-init race — verify by hitting endpoints concurrently right after a fresh `docker run`).

### Phase Ordering Rationale

- Roster before Chat: Chat's `roster_changes` action has nothing to delegate to without a working roster service (dependency identified in both FEATURES.md and ARCHITECTURE.md).
- Chat gets its own phase rather than being folded into Frontend: it's the only component with genuine external-integration and validation-boundary risk (structured-output parsing, cross-service delegation, adversarial-input handling) — bundling it with UI work would obscure whether failures are backend logic or frontend wiring.
- Frontend can run mostly in parallel with Chat once Roster is stable, since most frontend panels only need existing REST/SSE contracts; only the chat panel itself is blocked on Phase 2.
- Docker/E2E last: E2E scenarios need all API surfaces (roster, chat) finalized to be meaningful, and depend on `LLM_MOCK` already being exercised by Phase 2's own tests rather than requiring new mock-mode work during packaging.
- Budget/concurrency-safety work (Pitfalls 1, 7) is technically inside the already-complete Missions module but should be explicitly re-verified with a concurrency test before Chat lands, since Chat introduces a second concurrent caller of the same launch path.

### Research Flags

Phases likely needing deeper research during planning:
- **Chat/LLM Integration phase:** Live-verify the LiteLLM/OpenRouter/Cerebras structured-output behavior early (STACK.md flags this as unconfirmed in practice — LiteLLM's own docs don't list OpenRouter as a supported structured-output provider). Do a smoke test against the real model before finalizing the `llm_client.py` implementation approach.
- **Docker Packaging phase:** Next.js static-export + FastAPI serving has several edge cases (trailingSlash conventions, route-fallback behavior) that should be verified against the actual `next.config.js` settings rather than assumed from general patterns.

Phases with standard patterns (skip research-phase):
- **Roster module:** Directly mirrors the already-built, already-tested `missions/` module — no new patterns needed.
- **Frontend buildout:** Recharts usage for line/sparkline/treemap charts is well-documented; component patterns already established by the existing `FleetRosterPanel`/`useTelemetryStream` code.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core recommendations (stdlib sqlite3, Next.js 15.x, Recharts) are well-grounded; the LiteLLM/OpenRouter structured-output support gap is corroborated by official docs + a community GitHub issue but not by a live test against this project's exact model/provider combination |
| Features | MEDIUM | PLAN.md is treated as ground truth for scope (HIGH confidence there); external competitor/pattern research is drawn from design portfolios and blog posts (LOW-MEDIUM individually) that mostly serve to validate PLAN.md's existing choices rather than introduce new ones |
| Architecture | MEDIUM-HIGH | Codebase facts (what's built, what's stubbed, existing module shapes) are HIGH confidence — read directly from `.planning/codebase/ARCHITECTURE.md`/`STRUCTURE.md` and the repo; the LLM-integration pattern recommendations are web-sourced/LOW individually but align directly with the codebase's own established service-layer convention |
| Pitfalls | HIGH | SQLite/async, SSE, and static-export pitfalls are verified against current official docs and cross-referenced with the project's own `.planning/codebase/CONCERNS.md` audit; LLM auto-execution risk pitfalls are MEDIUM (established general pattern, no SkyFleet-specific incident yet since chat is unbuilt) |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- LiteLLM's structured-output support for OpenRouter/Cerebras is unconfirmed in live practice — validate with a smoke test at the start of the Chat phase and be ready to fall back to explicit `response_format` dict + forced provider routing (already documented as the primary recommendation, not a distant fallback).
- PROJECT.md's "Active" checklist has not been refreshed to reflect that DB/Telemetry/Missions are already complete — flag this for correction alongside/before roadmap creation so the roadmap doesn't re-plan already-finished work.
- Recharts 3.x migration (if chosen over staying on 2.13.x) has real breaking changes (removed props/deps) — treat as its own small task if pursued, not a drive-by bump during chart-building work.
- No SkyFleet-specific incident data exists yet for LLM auto-execution risk (chat is unbuilt) — the Chat phase's adversarial test cases (unknown drone_id, negative distance, malformed JSON) should be treated as the first real validation of this risk, not just theoretical coverage.

## Sources

### Primary (HIGH confidence)
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONCERNS.md` (2026-08-12 codebase audit) — direct repo reads establishing current build state and existing bug patterns
- `planning/PLAN.md` — project's own binding specification (scope, schema, API contracts, LLM behavior)
- `/vercel/next.js/v15.1.8` (Context7) — `output: 'export'` config and incompatibilities
- Next.js: Static Exports guide, `trailingSlash` config reference — official docs

### Secondary (MEDIUM confidence)
- `/berriai/litellm` (Context7) — `response_format` conversion pattern
- `docs.litellm.ai/docs/completion/json_mode` — LiteLLM's supported structured-output provider list (OpenRouter absent)
- aiosqlite issue #251, tenthousandmeters.com SQLite concurrency article — SQLite concurrency corroboration
- Mission Control Software UX Design Patterns & Benchmarking, Human-in-the-Loop AI Agents: Chat & Confirm — feature/UX pattern grounding
- giskard.ai — Function calling in LLMs — LLM failure-mode taxonomy

### Tertiary (LOW confidence)
- GitHub discussion #11652 (BerriAI/litellm) — community-reported OpenRouter structured-output workaround, uncorroborated by official source but consistent with LiteLLM's own docs
- Design portfolio references (Dribbble, Contra case studies) for fleet-dashboard UI patterns — illustrative, not authoritative
- General web searches on Recharts vs. Nivo vs. visx, and Next.js static-export serving patterns — used to confirm, not originate, recommendations already implied by PLAN.md and the existing codebase

---
*Research completed: 2026-08-12*
*Ready for roadmap: yes*
