# Architecture Research

**Domain:** Real-time ops console (telemetry + mission dispatch + LLM copilot) — FastAPI/SQLite/Next.js
**Researched:** 2026-08-12
**Confidence:** MEDIUM-HIGH (codebase facts are HIGH — read directly from the repo; LLM-integration pattern guidance is web-sourced/LOW individually but corroborates well-established service-layer conventions already used elsewhere in this codebase, so treated as directionally sound)

## Important Correction to Milestone Framing

The milestone context describes this as "adding SQLite persistence, fleet-ops/mission REST API, LLM chat... on top of a completed telemetry backend" — implying only telemetry exists. **The actual codebase is further along than that.** Per `.planning/codebase/ARCHITECTURE.md` and `STRUCTURE.md` (dated the same day as this research):

- **Already built and tested:** `backend/app/db/` (lazy-init SQLite, WAL mode, `asyncio.Lock`-serialized `transaction()`), `backend/app/telemetry/` (cache + SSE, confirmed complete), and `backend/app/missions/` — a full **models → service → repository → router** stack with atomic launch/recall against the energy budget, plus background schedulers (assignment retry, delivery completion, 30s budget snapshots).
- **Not built (empty/stub):** `backend/app/roster/` and `backend/app/chat/` (directories exist, no code). Frontend has only `Header`, `FleetRosterPanel`, `ConnectionDot`, and the `useTelemetryStream` SSE hook — no drone detail panel, heatmap, budget chart, missions table, dispatch bar, or chat UI.
- `.planning/PROJECT.md`'s "Active" checklist (DB layer, fleet-ops API, roster API, LLM chat, frontend — all unchecked) has not been refreshed to reflect this progress. **The roadmap should treat DB + Missions as done** and focus phase design on Roster, Chat/LLM, and Frontend buildout, not redo persistence/mission-ops from scratch.

This materially changes the "DB → API → LLM → Frontend" build-order assumption in the milestone question: DB and the core mission API already exist, so the real sequencing question is **Roster → Chat/LLM → Frontend buildout → Docker/E2E**, with Frontend able to start in parallel once Roster's contract is stable.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js static export, served by FastAPI, single origin)  │
│  Roster grid+sparklines | Detail panel | Heatmap | Budget chart |    │
│  Missions table | Dispatch bar | AI chat panel | Header              │
└───────────────┬───────────────────────────┬──────────────┬──────────┘
                │ SSE                        │ REST         │ REST
                ▼                            ▼              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        FastAPI Router Layer                          │
│  stream router | missions router | roster router (NEW) |             │
│  chat router (NEW)                                                    │
└───────────────┬───────────────┬───────────────┬──────────┬──────────┘
                │                │               │          │
                ▼                ▼               ▼          ▼
┌──────────────────────┐ ┌───────────────┐ ┌───────────┐ ┌──────────────────┐
│ TelemetryCache        │ │ Missions      │ │ Roster    │ │ Chat/LLM Layer   │
│ (in-memory, existing) │ │ Service       │ │ Service   │ │ (NEW)            │
│ - read-only fleet     │ │ (existing)    │ │ (NEW,     │ │ - context         │
│   state source        │ │ launch/recall │ │ mirrors   │ │   assembler       │
│                        │ │ /auto-assign  │ │ missions  │ │ - LiteLLM/        │
│                        │ │               │ │ shape)    │ │   OpenRouter call │
│                        │ │               │ │           │ │ - structured-     │
│                        │ │               │ │           │ │   output parse    │
│                        │ │               │ │           │ │ - invokes Missions │
│                        │ │               │ │           │ │   /Roster Service  │
│                        │ │               │ │           │ │   (no new logic)  │
└──────────┬─────────────┘ └───────┬───────┘ └─────┬─────┘ └─────────┬────────┘
           │ read only             │ read+write     │ write          │ read fleet ctx,
           │ (eligibility checks)  ▼                ▼                │ delegates writes
           │              ┌────────────────────────────────┐         │
           └─────────────▶│      Repository Layer           │◀───────┘
                          │  missions/repository.py,         │  (chat never touches
                          │  roster/repository.py (NEW)      │   repository directly)
                          └────────────────┬─────────────────┘
                                           ▼
                          ┌────────────────────────────────┐
                          │   Database (SQLite, WAL,        │
                          │   asyncio.Lock, transaction())   │
                          │   Tables: operator_profile,      │
                          │   fleet_roster, missions,        │
                          │   mission_log, budget_snapshots, │
                          │   chat_messages                  │
                          └──────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| TelemetryCache | Single source of truth for live drone state; read-only to everything downstream | Existing — no changes needed |
| Missions Service | Business rules for launch/recall (budget check, roster membership, telemetry safety, atomicity) | Existing — `backend/app/missions/service.py` |
| Roster Service (NEW) | Add/remove drones from `fleet_roster`; keep `TelemetryCache`/telemetry source in sync (call `source.add_drone()`/`remove_drone()`) | Mirror the missions module shape: `models.py`, `service.py`, `repository.py`, `router.py` |
| Chat/LLM Layer (NEW) | Assemble fleet context, call the LLM for structured output, validate the response shape, delegate every proposed mutation to Missions/Roster Service, persist `chat_messages` | `backend/app/chat/{models,service,repository,router}.py`; a `context.py` module for the read-side assembler |
| Repository Layer | SQL queries and multi-statement transactions | Existing pattern (`missions/repository.py`); extend with `roster/repository.py`, `chat/repository.py` |
| Database Layer | Lazy init, write serialization, `transaction()` | Existing — no changes needed |

## Recommended Project Structure

```
backend/app/
├── telemetry/            # unchanged — existing, complete
├── missions/              # unchanged — existing, complete
├── roster/                # NEW — mirrors missions/ shape exactly
│   ├── models.py          # RosterEntry dataclass, RosterError hierarchy
│   ├── service.py         # add_drone(), remove_drone() — validates + syncs telemetry source
│   ├── repository.py      # DB queries against fleet_roster
│   └── router.py          # POST/DELETE /api/roster
├── chat/                  # NEW
│   ├── models.py           # ChatMessage dataclass, ChatResponse schema (Pydantic, matches PLAN.md §9 schema)
│   ├── context.py          # assemble_fleet_context(): reads TelemetryCache + missions/roster repositories, no writes
│   ├── llm_client.py        # LiteLLM → OpenRouter call via the `cerebras` skill, structured-output request/parse, LLM_MOCK branch
│   ├── service.py           # orchestrates: build context → call LLM → for each proposed action, call missions.service/roster.service → collect results/errors
│   ├── repository.py        # persist/read chat_messages
│   └── router.py            # POST /api/chat
└── db/                     # unchanged — existing, complete
```

### Structure Rationale

- **`roster/` mirrors `missions/` exactly:** the codebase's own `STRUCTURE.md` already documents this as the intended pattern for new subsystems ("New Subsystem... Create `backend/app/geofencing/` with structure mirroring missions"). Following an established local convention beats inventing a new one.
- **`chat/context.py` is a separate module from `chat/service.py`:** the context assembler is read-only and has no dependency on the LLM client, so it can be unit-tested independently and reused (e.g., a future `/api/fleet/summary` endpoint could reuse it).
- **`chat/llm_client.py` isolates the LiteLLM/OpenRouter/Cerebras call and the `LLM_MOCK` branch:** keeps `service.py` free of provider-specific code and makes the mock path a single injectable seam for tests.

## Architectural Patterns

### Pattern 1: LLM Proposes, Service Layer Executes (validated-boundary pattern)

**What:** The chat layer never writes to the database directly and never re-implements budget/eligibility checks. It parses the LLM's structured JSON (`missions[]`, `roster_changes[]` per PLAN.md §9), then calls the exact same `missions.service.launch_mission()` / `recall_mission()` and `roster.service.add_drone()` / `remove_drone()` functions the REST routers already call. Every domain exception (`InsufficientBudgetError`, `UnknownDroneError`, etc.) the service layer already raises for manual dispatch is reused verbatim — caught in `chat/service.py`, turned into a per-action `{drone_id, action, error}` entry, and surfaced to the LLM's `message` text via the chat response, not silently dropped.
**When to use:** Any time an LLM (or any second entry point) needs to trigger the same mutation an existing API already performs.
**Trade-offs:** Requires the chat schema's action shape to line up closely with the service function signatures (or a thin adapter in between); in exchange, mission validation logic exists in exactly one place, so a future rule change (e.g., a new eligibility check) automatically applies to both manual and AI-initiated dispatch with no risk of drift.

**Example:**
```python
# backend/app/chat/service.py
async def handle_chat_message(db, cache, source, operator_message: str) -> ChatResult:
    context = await assemble_fleet_context(db, cache)
    history = await chat_repository.recent_messages(db)
    llm_response = await llm_client.get_structured_response(context, history, operator_message)

    executed, errors = [], []
    for m in llm_response.missions:
        try:
            if m.action == "launch":
                mission = await missions_service.launch_mission(db, cache, m.drone_id, m.zone, m.distance_km)
                executed.append(mission.to_dict())
            elif m.action == "recall":
                await missions_service.recall_mission(db, m.drone_id)
                executed.append({"drone_id": m.drone_id, "action": "recall"})
        except MissionError as e:
            errors.append({"drone_id": m.drone_id, "reason": str(e)})
    for r in llm_response.roster_changes:
        try:
            await roster_service.apply_change(db, source, r)
            executed.append(r.model_dump())
        except RosterError as e:
            errors.append({"drone_id": r.drone_id, "reason": str(e)})

    await chat_repository.save_turn(db, operator_message, llm_response.message, executed, errors)
    return ChatResult(message=llm_response.message, actions=executed, errors=errors)
```

### Pattern 2: Read-Side Context Assembler (composition over duplication)

**What:** A single `assemble_fleet_context()` function reads `TelemetryCache.get_all()`, active missions (`missions.repository.list_active_missions()`), remaining budget (`missions.repository.get_remaining_kwh()`), and roster — and returns one plain-data structure the LLM prompt is built from. No new read paths are invented for chat; it composes existing repository/cache reads.
**When to use:** Whenever a new consumer (chat, a future `/api/fleet/summary`, an admin dashboard) needs a fleet-wide snapshot that already exists piecemeal elsewhere.
**Trade-offs:** Slightly more indirection than inlining reads in the chat router, but keeps the chat layer decoupled from repository internals and testable with a fake cache/db.

### Pattern 3: Strategy Pattern for Pluggable Providers (already established, extend the convention)

**What:** `TelemetrySource` (Simulator vs. MAVLink Gateway) already uses an ABC + factory selected by env var. The LLM client should follow the same shape: a thin interface with a real (`LiteLLM → OpenRouter`) implementation and a mock implementation, selected by `LLM_MOCK`.
**When to use:** Any place PLAN.md specifies an env-var-toggled implementation swap (telemetry source, LLM provider).
**Trade-offs:** None significant — this is already the codebase's established idiom, so following it costs nothing and keeps conventions consistent.

## Data Flow

### Request Flow: Chat-Initiated Mission Dispatch (NEW)

```
Operator types message in chat panel
    ↓
POST /api/chat {message} → chat router
    ↓
chat/service.handle_chat_message()
    ├─→ chat/context.assemble_fleet_context()  [reads TelemetryCache + missions/roster repos — no writes]
    ├─→ chat/repository.recent_messages()       [reads chat_messages]
    ├─→ chat/llm_client.get_structured_response() [LiteLLM → OpenRouter/Cerebras, or LLM_MOCK]
    ├─→ FOR EACH proposed action: missions.service.launch_mission()/recall_mission()
    │                              or roster.service.add_drone()/remove_drone()
    │        (same functions the REST routers call — same validation, same DB transaction())
    └─→ chat/repository.save_turn()              [writes chat_messages with executed actions + errors]
    ↓
Router returns {message, actions, errors} JSON (no streaming — PLAN.md §9)
    ↓
Frontend chat panel renders response + inline action confirmations
```

### Request Flow: Manual Mission Dispatch (existing, unchanged)

Frontend dispatch bar → `POST /api/fleet/missions` → missions router → missions.service → missions.repository → `db.transaction()` (atomic: insert mission, insert mission_log, deduct budget, insert budget_snapshot) → 201 response.

### Telemetry Streaming (existing, unchanged)

`EventSource` → `/api/stream/telemetry` → `stream.py` polls `TelemetryCache.version` every ~500ms → pushes SSE JSON on change → frontend accumulates sparkline history client-side since page load.

### Key Data Flows

1. **Chat writes never bypass the service layer.** The chat router/service has zero direct SQL and zero direct `TelemetryCache` writes — it only reads the cache and calls the same service functions manual dispatch uses.
2. **TelemetryCache flows one direction only:** Simulator/Gateway → Cache → {SSE stream, Missions Service eligibility checks, Chat context assembler}. Nothing writes back into the cache except the telemetry source itself.
3. **Roster changes must stay in sync with the telemetry source**, not just the DB: adding/removing a drone via roster service must call `source.add_drone()`/`source.remove_drone()` (already exposed by `TelemetrySource`) in the same operation, or the SSE stream and the roster table will drift.

## Scaling Considerations

Not a meaningful axis for this project — it's a single-operator demo app by design (no auth, `operator_id="default"` hardcoded, SQLite with single-writer lock). Do not add scaling infrastructure (Postgres, Redis, multi-worker) — it would contradict the "single Docker container, single port" constraint in PLAN.md §3 and the explicit anti-goal of adding infrastructure this app doesn't need.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 operator, demo/course use (actual target) | Current design is correct as-is: single `asyncio.Lock`-serialized SQLite writer, in-memory telemetry cache, single-process uvicorn |
| If ever multi-operator | Would require dropping the hardcoded `operator_id="default"`, adding auth, and likely moving off SQLite's single-writer model — explicitly out of scope per `.planning/PROJECT.md` |

### Scaling Priorities

Not applicable — do not plan phases around scaling. If asked to "future-proof," the correct answer per PLAN.md is the existing `operator_id` columns already present on every table, not new infrastructure.

## Anti-Patterns

### Anti-Pattern 1: Chat Layer Reimplementing Mission/Roster Validation

**What people do:** Write budget checks, eligibility checks, or roster uniqueness checks inline in `chat/service.py` because "the LLM already decided this is valid."
**Why it's wrong:** Creates two divergent sources of truth for the same business rule (manual dispatch vs. AI dispatch). A future rule change (e.g., stricter low-battery threshold) silently applies to only one path. This is the single highest-risk pitfall for this milestone given the codebase already has a correct, tested `missions/service.py`.
**Do this instead:** Chat always calls `missions.service.*` / `roster.service.*` and only handles the resulting domain exceptions for user-facing messaging.

### Anti-Pattern 2: Chat Router Talking to the Database or TelemetryCache Directly

**What people do:** `chat/router.py` calls `db.fetchall()` or `cache.get_all()` directly to "save a layer."
**Why it's wrong:** Breaks the same router → service → repository layering the codebase already establishes for missions (documented as an explicit anti-pattern in `.planning/codebase/ARCHITECTURE.md`); makes the chat flow untestable without a live DB/cache.
**Do this instead:** Route everything through `chat/service.py`, which itself delegates reads to `chat/context.py` and writes to `missions.service`/`roster.service`/`chat/repository.py`.

### Anti-Pattern 3: Synchronous/Blocking LLM HTTP Call in the Async Event Loop

**What people do:** Use a blocking HTTP client (`requests`, or a sync LiteLLM call) inside an `async def` route handler.
**Why it's wrong:** FastAPI/uvicorn runs a single event loop (per `.planning/codebase/ARCHITECTURE.md`'s "Architectural Constraints" — no multi-worker deployment); a blocking LLM call (network round-trip to OpenRouter) would stall the SSE telemetry stream and all other requests for the duration of the call.
**Do this instead:** Use LiteLLM's async interface (or wrap the call in `asyncio.to_thread()`, matching the existing pattern already used for SQLite I/O), exactly as the telemetry MAVLink gateway client already does for its polling.

### Anti-Pattern 4: Tight-Coupling the LLM's JSON Schema to Internal Function Signatures

**What people do:** Pass the LLM's raw parsed JSON straight into `missions.service.launch_mission(**raw_dict)`.
**Why it's wrong:** Any drift between the documented structured-output schema (PLAN.md §9) and the internal service signature becomes a runtime `TypeError` with a confusing LLM-facing stack trace instead of a clean domain validation error.
**Do this instead:** Parse the LLM response into a small Pydantic model matching the PLAN.md §9 schema first (`ChatMissionAction`, `ChatRosterChange`), then explicitly map validated fields to the service function call.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenRouter (Cerebras `openrouter/openai/gpt-oss-120b`) | LiteLLM async client, structured-output request, called only from `chat/llm_client.py` | Must use the `cerebras` skill per CLAUDE.md; `OPENROUTER_API_KEY` from `.env`; never call from frontend (single-origin backend-only) |
| MAVLink Gateway (optional) | Existing — REST polling, unchanged by this milestone | No new integration needed |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Frontend ↔ Backend | REST (`/api/*`) + SSE (`/api/stream/*`), same origin | No CORS needed; chat is request/response JSON, not streamed token-by-token (PLAN.md §9) |
| Chat Service ↔ Missions/Roster Service | Direct in-process function calls, same signatures REST routers use | This is the core boundary this milestone must get right — see Pattern 1 and Anti-Pattern 1 |
| Chat Service ↔ TelemetryCache | Read-only via `context.py` | Chat never mutates the cache; only the telemetry source does |
| Roster Service ↔ TelemetrySource | `source.add_drone()`/`remove_drone()` called in the same operation as the DB write | Keeps roster table and live telemetry stream from drifting apart |
| Missions/Roster Service ↔ Database | Through `repository.py` + `db.transaction()` only | Existing convention; extend, don't bypass |

## Suggested Build Order

Given the corrected current state (DB + Missions + Telemetry already complete):

1. **Roster module** (`backend/app/roster/`) — no new architectural risk, mirrors the existing missions shape, small surface area (add/remove + sync telemetry source). Needed as a prerequisite for Chat, since the LLM's `roster_changes` action requires a working roster service to delegate to.
2. **Chat/LLM module** (`backend/app/chat/`) — depends on Roster (step 1) and Missions (existing) being callable. Build in this internal order: (a) `context.py` read-assembler first — testable with zero LLM involvement; (b) `llm_client.py` with `LLM_MOCK` branch built alongside the real OpenRouter path from the start, not bolted on later, so the mock path is exercised by the same tests as the real path; (c) `service.py` orchestration wiring context → LLM → service-layer delegation; (d) `repository.py` + `router.py`.
3. **Frontend buildout** — can start in parallel with step 2 for everything that only depends on existing REST/SSE contracts (drone detail panel, heatmap, budget chart, missions table, dispatch bar). The AI chat panel specifically depends on step 2's `/api/chat` contract being stable, so sequence it last within the frontend work, or stub it against the PLAN.md §9 schema and wire it up once chat lands.
4. **Docker packaging + start/stop scripts + E2E tests** — last, since Playwright E2E scenarios (per PLAN.md §12) exercise roster, missions, and chat end-to-end and need all API surfaces finalized; `LLM_MOCK=true` should already be proven out in step 2 so E2E chat scenarios are just exercising an existing, tested mock path rather than requiring new mock logic.

This order keeps every phase's blast radius small: Roster is isolated and low-risk, Chat is the one component with real integration complexity (external API, structured-output parsing, cross-service delegation) so it gets its own dedicated phase, and Frontend/Docker/E2E are consumers that stabilize last.

## Sources

- `.planning/codebase/ARCHITECTURE.md` (2026-08-12) — HIGH confidence, direct codebase read
- `.planning/codebase/STRUCTURE.md` (2026-08-12) — HIGH confidence, direct codebase read
- `planning/PLAN.md` §§3, 6, 7, 8, 9 — HIGH confidence, project's own binding spec
- `planning/TELEMETRY_SUMMARY.md` — HIGH confidence, direct codebase read
- Web search: LLM structured-output/tool-calling validation-boundary pattern — LOW confidence (general web search, uncorroborated by a named authority), but directionally consistent with the codebase's own existing service-layer convention, so used only to confirm (not originate) the recommendation
- Web search: agentic auto-execution risk/mitigation practices — LOW confidence, general web search; included as context only (PLAN.md §9 has already made the deliberate design call to auto-execute without confirmation for this zero-stakes simulated environment, and this research does not challenge that decision)

---
*Architecture research for: SkyFleet Ops — mission-ops/chat/frontend milestone*
*Researched: 2026-08-12*
