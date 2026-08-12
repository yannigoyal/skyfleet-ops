# Phase 2: AI Flight Director Chat - Research

**Researched:** 2026-08-12
**Domain:** Backend LLM tool-calling integration (LiteLLM → OpenRouter → Cerebras), structured-output validation, service-layer delegation
**Confidence:** HIGH (backend layering/exceptions verified by reading actual source; LLM structured-output risk verified via official docs + GitHub issue tracker; provider legitimacy see audit table)

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for this phase — `/gsd-discuss-phase` was skipped. This research and the resulting plan proceed from `REQUIREMENTS.md`, `STATE.md`, `PROJECT.md`, and `planning/PLAN.md` §9 only. There are no locked decisions, discretion areas, or deferred ideas to copy forward from a discuss-phase session.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CHAT-01 | `POST /api/chat` returns one complete structured JSON response (message + executed actions) | See Architecture Patterns → Pattern 1; Code Examples → router |
| CHAT-02 | LLM-issued mission launches validated/executed via the identical `missions.service` function manual dispatch uses | See Architecture Patterns → Pattern 1; Common Pitfalls → Pitfall 2 |
| CHAT-03 | LLM-issued mission recalls validated/executed via the identical `missions.service` function | Same as CHAT-02; `missions.service.recall_mission` verified by reading source |
| CHAT-04 | LLM-issued roster add/remove validated/executed via `roster.service` "the same way" | See Common Pitfalls → Pitfall 1 (critical: reference implementation bypasses this) |
| CHAT-05 | Chat history persists in `chat_messages`; recent turns loaded into prompt context | See Code Examples → repository; schema verified below |
| CHAT-06 | `LLM_MOCK=true` returns deterministic responses, no OpenRouter call | See Code Examples → mock_reply pattern |
| CHAT-07 | Invalid/failing LLM-proposed actions surface as readable chat errors, no crash | See Common Pitfalls → Pitfall 3, Pitfall 4 |
| CHAT-08 | LiteLLM→OpenRouter→Cerebras call uses explicit `response_format`, forced provider routing, not auto-detection | See Common Pitfalls → Pitfall 5 (the load-bearing finding of this research) |
</phase_requirements>

## Summary

Phase 2 adds one new backend module, `backend/app/chat/`, that assembles a fleet-state snapshot, calls an LLM for a structured JSON reply, and routes every proposed mutation through the exact same `missions.service` / `roster.service` functions the manual REST endpoints already call — no new "trusted" write path. The database table (`chat_messages`), the missions/roster service layer, and the layering convention (`models.py` / `repository.py` / `service.py` / `router.py`) all already exist and were verified by reading the current codebase; this phase is additive, not a refactor.

The single highest-risk item, and the reason this phase has its own dedicated research and a flagged blocker in STATE.md, is CHAT-08: **LiteLLM's OpenRouter adapter silently strips a top-level `response_format` parameter** because its internal `supports_response_schema()` check does not recognize OpenRouter as a supported provider (confirmed via official LiteLLM docs, three open GitHub issues, and one confirmed-fixed discussion thread on `BerriAI/litellm`). The verified fix is to nest `response_format` **inside** `extra_body` rather than passing it as a top-level keyword argument to `litellm.acompletion()`. This repo also contains a prior-art reference implementation of this exact module on a **sibling branch** (`agent_team_work`, commit `2ba52a8`) that gets the schema **and** provider-routing shape right but places `response_format` at the top level — i.e. it very likely hits the exact bug this research exists to catch. The plan must correct this placement, not copy the reference verbatim.

The second significant risk is CHAT-04: the reference branch's chat router calls `roster_repository.add_drone`/`remove_drone` **directly**, bypassing `roster.service`. That skips the Phase-1-built auto-recall-before-remove guard (`roster.service.remove_drone`'s D-03/ROST-02-TOCTOU pattern) — removing a drone with an active mission via chat would behave differently than removing it manually, which directly violates CHAT-04's "the same way" requirement. The plan must call `roster.service.add_drone(db, source, drone_id)` / `roster.service.remove_drone(db, source, drone_id)`, not the repository.

**Primary recommendation:** Build `backend/app/chat/{models,context,llm,repository,router}.py` mirroring the reference branch's module shape and validated-boundary pattern almost exactly, with two corrections: (1) nest `response_format` inside `extra_body` for the OpenRouter call, and (2) route roster actions through `roster.service`, not `roster.repository`. Add `litellm>=1.96.0` to `backend/pyproject.toml` (currently absent from the dependency list, though already present unpinned in the local `.venv` from an earlier session) and run `uv add litellm>=1.96.0` + `uv sync` in Wave 0. Include a live smoke-test task early in the plan that actually calls Cerebras via OpenRouter with `LLM_MOCK` unset, to close out STATE.md's flagged risk with real evidence rather than documentation alone.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Chat message intake (`POST /api/chat`) | API / Backend | — | New FastAPI router, same tier as existing `missions`/`roster` routers |
| Fleet-state snapshot for prompt context | API / Backend | Database / Storage | Read-only aggregation of live telemetry cache + DB state (`chat/context.py`), no new storage |
| LLM call (LiteLLM → OpenRouter → Cerebras) | API / Backend | External Service | Backend-only; must never be called from the frontend (no CORS/API-key exposure) |
| Structured-output parsing/validation | API / Backend | — | Pydantic models in `chat/llm.py`; schema validation happens before any execution |
| Mission/roster mutation execution | API / Backend | Database / Storage | Delegates to existing `missions.service` / `roster.service` — this phase adds no new mutation logic, only a new caller |
| Chat history persistence | Database / Storage | API / Backend | `chat_messages` table already exists in schema; `chat/repository.py` is the only new persistence code |
| Mock-mode determinism (`LLM_MOCK=true`) | API / Backend | — | Pure in-process branch, no I/O; must be the default in CI/E2E per PLAN.md §12 |

## User Constraints

See `<user_constraints>` above — none beyond the phase's own stated requirements and success criteria.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `litellm` | `>=1.96.0` (latest on PyPI: `1.96.2`, released via BerriAI, `1208` total releases on PyPI — mature, actively maintained) `[ASSUMED — see Package Legitimacy Audit]` | Unified OpenAI-compatible client for calling OpenRouter/Cerebras with `acompletion()` and `response_format` | Already the project's binding choice per PLAN.md §9 and `.claude/CLAUDE.md`; `>=1.96.0` is the exact version pinned by the sibling-branch reference implementation and matches the version already installed (unpinned) in the local `.venv` |
| `pydantic` | `2.13.4` (already installed, transitively via FastAPI) `[VERIFIED: backend/.venv/lib/python3.12/site-packages/pydantic-2.13.4.dist-info]` | Structured-output response models (`FlightDirectorReply`, `MissionAction`, `RosterChange`) and request body validation | Already the project's convention for router-layer request models (`missions/router.py`, `roster/router.py`) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | `>=0.24.0` (already a dev dependency) | Test `async def` chat service/router functions | Already used across `missions`/`roster`/`telemetry` test suites |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LiteLLM `acompletion()` | Raw `httpx` POST to OpenRouter's REST API | Rejected — PLAN.md §9 and `.claude/CLAUDE.md` fix LiteLLM as the required client ("Must use... LiteLLM"); not an open decision for this phase |
| Nesting `response_format` in `extra_body` | Waiting for/patching LiteLLM's `OpenrouterConfig.map_openai_params()` to add OpenRouter to `supports_response_schema()` | Rejected — patching a third-party library's internals is fragile across upgrades; `extra_body` is the documented, no-fork workaround confirmed by the library's own maintainers' discussion thread |
| `roster.service` for chat roster actions | `roster.repository` directly (what the sibling-branch reference does) | Rejected — bypasses the Phase-1 auto-recall-before-remove guard; see Pitfall 1 |

**Installation:**
```bash
cd backend
uv add "litellm>=1.96.0"
uv sync --extra dev
```

**Version verification:** `pip index versions litellm` was run against the live PyPI registry during this research session and returned `1.96.2` as the newest release, with `1.96.0` (the version the sibling-branch reference pins, and the version already present in the local `.venv`) also listed. `curl https://pypi.org/pypi/litellm/json` confirmed `project_urls.Repository = https://github.com/BerriAI/litellm` and `author = BerriAI`, with `1208` historical release entries — consistent with a long-lived, actively-maintained package, not a newly-registered or abandoned one. `[VERIFIED: npm registry` — n/a, this is PyPI; treat as `VERIFIED: pypi registry, live `pip index`/`curl` output this session]`.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|--------------|---------|-------------|
| `litellm` | PyPI | 1208 historical releases (multi-year project) `[confirmed via live PyPI JSON this session]` | Not resolvable this session (`pypistats.org` returned `429 rate limited`) | `github.com/BerriAI/litellm` `[confirmed via live PyPI JSON this session]` | `SUS` (per automated `package-legitimacy check` seam — see note) | Approved with note |

**Note on the `SUS` verdict:** The automated `gsd-tools query package-legitimacy check --ecosystem pypi litellm` seam returned `SUS` with signals `{exists: null, publishedAt: null, weeklyDownloads: null, repoUrl: null}` — every signal is `null`, indicating the check's data source did not return metadata for this run (a tooling/network gap), not that it found and rejected real risk signals. This research independently confirmed via direct `pip index versions` and `curl https://pypi.org/pypi/litellm/json` (both live registry calls this session) that `litellm` is registered under `BerriAI` with a linked GitHub repo (`github.com/BerriAI/litellm`) and 1208 release entries. Per protocol, the `SUS` disposition still stands and **the planner must add a `checkpoint:human-verify` task before the `uv add litellm` step**, even though the manually-gathered evidence is strong — do not let this note substitute for that gate.

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `litellm` — see note above; planner inserts `checkpoint:human-verify` before install.

## Architecture Patterns

### System Architecture Diagram

```
Operator (chat input, frontend — built in Phase 3, not this phase)
        │  POST /api/chat  {"message": "..."}
        ▼
┌───────────────────────────────────────────────────────────────┐
│ chat/router.py  — create_chat_router(db, cache, source)        │
│   1. build_fleet_context(db, cache)  ──────────────┐            │
│   2. repository.get_recent_messages(db, limit=20)  │  reads     │
│   3. llm.generate_reply(context, history, message) │  only      │
│        ├─ LLM_MOCK=true → llm.mock_reply()  (no network)        │
│        └─ else → litellm.acompletion(                           │
│               model="openrouter/openai/gpt-oss-120b",           │
│               extra_body={"response_format": {...json_schema},  │
│                            "provider": {"only": ["Cerebras"]}}) │
│   4. FlightDirectorReply parsed + Pydantic-validated             │
│   5. execute_actions(): for each proposed action ───────────────┼──┐
│   6. repository.append_message(db, "user", ...)                 │  │
│   7. repository.append_message(db, "assistant", ..., actions)   │  │
│   8. return {"message", "missions"?, "roster_changes"?}          │  │
└───────────────────────────────────────────────────────────────┘  │
                                                                     │
        ┌────────────────────────────────────────────────────────┘
        ▼
┌─────────────────────────────┐   ┌──────────────────────────────┐
│ missions.service             │   │ roster.service                │
│  launch_mission(db, cache,   │   │  add_drone(db, source, id)    │
│    drone_id=, zone=,         │   │  remove_drone(db, source, id) │
│    distance_km=)             │   │   (auto-recalls active        │
│  recall_mission(db, id)      │   │    mission first — D-03)      │
│  — SAME functions manual     │   │  — SAME functions manual      │
│    dispatch bar calls        │   │    roster router calls        │
└──────────────┬────────────────┘   └──────────────┬─────────────┘
               ▼                                    ▼
     repository.create_mission /          repository.add_drone /
     repository.recall (atomic            remove_drone
     db.transaction())                    (+ telemetry source sync)
               │                                    │
               ▼                                    ▼
        SQLite (missions, mission_log,      SQLite (fleet_roster)
        budget_snapshots) — single
        asyncio.Lock-serialized writer
```

A reader can trace the primary use case end to end: operator message → context assembly (read-only) → LLM structured reply (or mock) → per-action delegation to the *existing, unchanged* `missions.service`/`roster.service` → same atomic DB writes as manual dispatch → chat turn persisted → JSON response.

### Recommended Project Structure

```
backend/app/chat/
├── __init__.py       # exports CHAT_ROLES, ChatMessage, create_chat_router
├── models.py         # ChatMessage dataclass (mirrors a chat_messages row)
├── context.py         # build_fleet_context(db, cache) — read-only snapshot for the prompt
├── llm.py             # RESPONSE_SCHEMA, SYSTEM_PROMPT, FlightDirectorReply/MissionAction/
│                       # RosterChange Pydantic models, parse_reply(), mock_reply(),
│                       # generate_reply() (the LLM_MOCK branch lives here)
├── repository.py      # append_message(), get_recent_messages() against chat_messages
└── router.py           # create_chat_router(db, cache, source) — POST /api/chat,
                         # execute_actions() delegating to missions.service/roster.service

backend/tests/chat/
├── __init__.py
├── conftest.py        # db/cache fixtures + stub_completion() monkeypatch of litellm.acompletion
├── test_llm.py         # parse_reply/build_messages/mock_reply unit tests
├── test_repository.py  # append_message/get_recent_messages persistence tests
└── test_router.py      # full endpoint tests: happy path, malformed JSON, unknown drone,
                         # insufficient budget, LLM_MOCK on/off, provider-routing kwargs asserted
```

This mirrors the existing `missions/` and `roster/` module shape (`models.py`/`repository.py`/`service.py`or its chat-equivalent `llm.py`+`router.py`/`router.py`), which is the codebase's own established convention for new subsystems `[VERIFIED: backend/app/missions/*.py, backend/app/roster/*.py — read directly this session]`. Note `chat/` has **no `service.py`**; the reference implementation folds orchestration directly into `router.py`'s `execute_actions()` helper and keeps `llm.py` as the provider-specific seam — this is a reasonable, smaller variant since chat's "service logic" is almost entirely "call the LLM, then call missions/roster service," not new business rules.

### Pattern 1: LLM Proposes, Service Layer Executes (validated-boundary pattern)

**What:** The chat router never writes to the database directly and never re-implements budget/eligibility/roster checks. It parses the LLM's structured JSON into typed Pydantic models, then calls the exact same `missions.service.launch_mission()` / `recall_mission()` and `roster.service.add_drone()` / `remove_drone()` functions the REST routers already call. Every domain exception those functions already raise (`InsufficientBudgetError`, `UnknownDroneError`, `DroneAlreadyEnRouteError`, `NoActiveMissionError`, `DroneAlreadyTrackedError`, etc.) is caught per-action and turned into a human-readable failure string appended to the chat response — never silently dropped, never allowed to 500 the whole request.

**When to use:** Any time a second entry point (here, an LLM) needs to trigger a mutation an existing API already performs safely.

**Example** (adapted from the sibling-branch reference implementation, `git show 2ba52a8:backend/app/chat/router.py`, corrected for the roster-service delegation pitfall below):
```python
# Source: backend/app/missions/service.py (read this session) for the exact signature;
# pattern adapted from sibling branch agent_team_work commit 2ba52a8:backend/app/chat/router.py
from app.missions import service as missions_service
from app.missions.models import MissionError
from app.roster import service as roster_service       # NOT roster.repository — see Pitfall 1
from app.roster.models import RosterError

async def _execute_mission(db, cache, action) -> tuple[dict | None, str | None]:
    if action.action == "recall":
        try:
            await missions_service.recall_mission(db, action.drone_id)
        except MissionError as exc:
            return None, f"Could not recall {action.drone_id}: {exc.reason}."
        return {"drone_id": action.drone_id, "action": "recall"}, None

    if not action.zone or action.distance_km is None or action.distance_km <= 0:
        return None, f"Could not launch {action.drone_id}: missing zone or distance."
    try:
        await missions_service.launch_mission(
            db, cache, drone_id=action.drone_id, zone=action.zone, distance_km=action.distance_km
        )
    except MissionError as exc:
        return None, f"Could not launch {action.drone_id} to {action.zone}: {exc.reason}."
    return {"drone_id": action.drone_id, "action": "launch",
            "zone": action.zone, "distance_km": action.distance_km}, None


async def _execute_roster_change(db, source, change) -> tuple[dict | None, str | None]:
    try:
        if change.action == "add":
            await roster_service.add_drone(db, source, change.drone_id)
        else:
            await roster_service.remove_drone(db, source, change.drone_id)
    except RosterError as exc:
        return None, f"Could not {change.action} {change.drone_id}: {exc.reason}."
    return {"drone_id": change.drone_id, "action": change.action}, None
```

**Trade-offs:** Requires the chat schema's action shape (`drone_id`, `action`, `zone`, `distance_km`) to line up with the service function signatures, or a thin mapping step in between. In exchange, mission/roster validation logic exists in exactly one place — a future rule change automatically applies to both manual and AI-initiated dispatch with zero risk of drift.

### Pattern 2: LLM_MOCK as an early-return branch inside the LLM client module, not a separate code path in the router

**What:** `chat/llm.py` exposes one entry point, `generate_reply(fleet_context, history, user_message)`, which checks `os.environ.get("LLM_MOCK")` first and returns a deterministic `FlightDirectorReply` without importing/calling `litellm` at all when mocking. The router calls `generate_reply()` unconditionally and never branches on `LLM_MOCK` itself.

**When to use:** Any place PLAN.md §9's "LLM Mock Mode" requirement needs a single injectable seam for both `LLM_MOCK=true` production behavior and test monkeypatching.

**Example:**
```python
# Source: adapted from sibling branch agent_team_work commit 2ba52a8:backend/app/chat/llm.py
def mock_mode_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"

async def generate_reply(fleet_context, history, user_message) -> FlightDirectorReply:
    if mock_mode_enabled():
        return mock_reply(fleet_context, user_message)
    # ... real litellm.acompletion() call (see Pitfall 5 for exact kwargs) ...
```

**Why this matters here specifically:** PLAN.md §12 requires E2E tests to run with `LLM_MOCK=true` by default. Keeping the branch inside `llm.py` means `router.py`, `context.py`, and `repository.py` are completely mock-agnostic and testable identically in both modes — only `llm.py`'s own unit tests need to cover both branches.

### Anti-Patterns to Avoid

- **Bypassing `roster.service` for chat-initiated roster changes** (see Pitfall 1) — breaks CHAT-04's "same way" requirement and drops the Phase-1 auto-recall guard.
- **Passing `response_format` as a top-level kwarg to `litellm.acompletion()` for an `openrouter/*` model** (see Pitfall 5) — silently stripped, model never receives the schema instruction, defeating CHAT-08 entirely while looking like it works in casual manual testing (the model may still emit JSON-shaped prose from instruction-following alone, masking the bug until an edge-case prompt breaks it).
- **Trusting "the JSON parsed" as full validation** — structured output guarantees *shape*, not truthful/sane *values* (a hallucinated `drone_id` that matches the schema's `string` type but doesn't exist on the roster). Every proposed action must still pass through the real service-layer checks (Pattern 1) — this is exactly what routing through `missions.service`/`roster.service` already buys you, so don't add a second, weaker validation layer in `chat/llm.py` and treat it as sufficient.
- **Executing actions from a response that failed schema validation, even partially** — `parse_reply()` should raise `LLMError` on any structural failure (bad JSON, wrong types, missing `message`) and the router should treat that as *zero* actions, not best-effort partial execution.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| OpenAI-compatible client for OpenRouter/Cerebras | A custom `httpx` wrapper around OpenRouter's REST API | `litellm.acompletion()` | Already the fixed project choice (PLAN.md §9, `.claude/CLAUDE.md`); handles retries, response normalization, and the multi-provider abstraction so a future model/provider swap doesn't require rewriting the HTTP layer |
| JSON-schema-constrained model output | Regex/heuristic parsing of free-text LLM replies | `response_format={"type": "json_schema", ...}` + Pydantic `model_validate()` | Explicitly out of scope per `REQUIREMENTS.md` "Out of Scope" table: "Free-text LLM output parsed with regex/heuristics... structured JSON output validated by Pydantic is required" |
| Mission/roster mutation validation for AI-issued actions | A second, "trusted" write path that skips budget/eligibility checks because "the AI already reasoned about it" | The exact same `missions.service`/`roster.service` functions manual dispatch uses | Explicitly out of scope per `REQUIREMENTS.md`: "LLM writing directly to the database... LLM only proposes actions; execution always routes through the same service-layer functions" |
| Confirmation gate before AI-executed actions | A modal/dialog blocking auto-execution | Rich inline confirmation cards in the chat response (`message` text narrating exactly what executed) | Explicitly out of scope per `REQUIREMENTS.md`: "Would kill the fluid agentic demo experience; stakes are zero... mitigated instead with rich inline confirmation cards (FE-09)" — FE-09 is Phase 3's job; this phase's job is making sure `message`/`missions`/`roster_changes` carry enough detail for Phase 3 to render that card |

**Key insight:** Every "don't hand-roll" item in this phase is already a decided, non-negotiable constraint from `REQUIREMENTS.md`'s "Out of Scope" table — this phase's actual engineering risk is not *whether* to reuse the service layer, but *getting the LLM call's provider-routing kwargs right* (Pitfall 5) and *not accidentally bypassing the service layer for roster actions specifically* (Pitfall 1), because a sibling-branch reference implementation exists that gets one of these two things wrong.

## Common Pitfalls

### Pitfall 1: Chat's roster actions bypass `roster.service`, skipping the Phase-1 auto-recall guard

**What goes wrong:** The chat router calls `roster.repository.add_drone()`/`remove_drone()` directly (as the sibling-branch reference implementation does) instead of `roster.service.add_drone()`/`remove_drone()`. Removing a drone via chat that currently has an active mission then behaves differently than removing it manually: `roster.service.remove_drone()` checks for an active mission and calls `missions.service.recall_mission()` first (verified: `backend/app/roster/service.py:38-77`, its own docstring names this the "D-03" pattern and explicitly guards the `NoActiveMissionError` race against a concurrent scheduler/manual recall). Calling `roster.repository.remove_drone()` directly skips this entirely — the roster row is deleted while the mission stays `en_route` with no drone tracking it, an orphaned-state bug Phase 1 specifically fixed for the manual path.

**Why it happens:** The sibling-branch reference implementation (`git show 2ba52a8:backend/app/chat/router.py`) was written before/alongside the current `roster.service`'s D-03 guard existed in its current form, or by an agent that didn't realize a service layer (as opposed to the repository) was the correct integration point. Because both `roster.repository.add_drone`/`remove_drone` and `roster.service.add_drone`/`remove_drone` are valid, importable, similarly-named functions, this is an easy copy-paste mistake even when directly reusing working reference code.

**How to avoid:** In `chat/router.py`, import `from app.roster import service as roster_service` and call `roster_service.add_drone(db, source, drone_id)` / `roster_service.remove_drone(db, source, drone_id)` — the identical call shape `roster/router.py` itself uses (verified: `backend/app/roster/router.py:52-65`). Do not import `roster.repository` into the chat module at all.

**Warning signs:** A test that removes a drone with an active mission via `LLM_MOCK` "recall" text produces a different outcome (or a lingering `en_route` mission row) than the equivalent manual `DELETE /api/roster/{drone_id}` call in the roster test suite.

### Pitfall 2: Assuming `missions.service.launch_mission`/`recall_mission` need a *new* concurrency guard for chat

**What goes wrong:** STATE.md flags "re-verify the budget/eligibility read-then-write path... under concurrent access, since chat introduces a second concurrent caller." A plan might over-react to this and add new locking/guards around `launch_mission`/`recall_mission` before chat can call them.

**Why it happens:** The flagged concern conflates two different things: (a) `missions.repository.create_mission()` and `.recall()` are already fully atomic — the existing-en-route check, the budget check, and the write all happen inside one `db.transaction()` closure under the single `asyncio.Lock` (verified: `backend/app/missions/repository.py:106-152` for launch, `:165-202` for recall) — so budget overdraft and double-booking are already impossible regardless of how many concurrent callers exist; and (b) the one real, pre-existing race is in `missions.service.find_eligible_drone()`/`auto_assign_mission()` (documented in `.planning/codebase/CONCERNS.md` "Race Condition in Drone Eligibility Check", `backend/app/missions/service.py` lines 65-88) — but the chat's structured-output schema (PLAN.md §9) always specifies an explicit `drone_id` for launches, so chat calls `launch_mission()` (explicit-drone path), never `auto_assign_mission()`/`find_eligible_drone()` (auto-pick path). Chat does not exercise the one function with a known race.

**How to avoid:** Confirm in the plan's verification step that chat's `MissionAction` schema requires `drone_id` for launches (it does, per `RESPONSE_SCHEMA` in Pattern 2/Code Examples) and that `_execute_mission()` always calls `missions_service.launch_mission(..., drone_id=action.drone_id, ...)`, never `auto_assign_mission()`. No new locking code is needed in `missions/` for this phase. The one genuinely new, low-severity race this phase introduces — a concurrent `DELETE /api/roster/{id}` racing a chat-issued `launch_mission()`'s non-atomic `is_drone_on_roster()` pre-check — already exists today between two *manual* API calls (`POST /api/fleet/missions` vs `DELETE /api/roster/{id}`); chat adds a second caller of an existing window, it does not create a new one. Document this as an accepted, pre-existing limitation rather than adding scope to fix it in this phase.

**Warning signs:** A plan task titled something like "add a lock around launch_mission for chat safety" — this indicates the pre-existing atomicity guarantee wasn't verified against the actual repository code before planning the fix.

### Pitfall 3: LLM auto-executes a hallucinated or malformed mission/roster action with no confirmation gate

**What goes wrong:** PLAN.md deliberately auto-executes LLM-issued actions with no confirmation dialog. Structured output constrains JSON *shape*, not semantic correctness — the model can still emit a syntactically valid `drone_id` that doesn't exist on the roster, a negative or absurd `distance_km`, or duplicate/conflicting actions (launch and recall for the same drone in one reply).

**Why it happens:** Teams new to structured output trust "matched the schema" as sufficient validation and skip re-running the same business-rule checks applied to manual/API-driven actions.

**How to avoid:** This is exactly what Pattern 1 (validated-boundary) already buys — every action, regardless of source, passes through `missions.service`/`roster.service`'s real checks (unknown-drone, insufficient-budget, already-en-route, no-active-mission, already-tracked). No additional semantic validation layer is needed *if and only if* Pitfall 1 and Pitfall 2's guidance is followed (i.e., the service layer is never bypassed). If the reply contains multiple actions, execute them sequentially through the shared budget-checking path — not as a pre-validated batch — so a later action in the same reply can correctly fail if an earlier one already consumed the budget (this falls out naturally from calling `launch_mission()` once per action in a loop, per Pattern 1's `execute_actions()`).

**Warning signs:** Mission rows with `drone_id` values that never existed on the roster, or budget going negative after a multi-action chat reply — either indicates an action reached a DB write without going through the service layer.

**Phase to address:** This phase. Acceptance criterion: a mocked chat reply with an invalid `drone_id`/negative `distance_km` is rejected with an error surfaced in `message`, not silently executed or dropped (test this explicitly — see Validation Architecture below).

### Pitfall 4: Malformed/incomplete LLM JSON crashes the endpoint or executes garbage

**What goes wrong:** A naive `json.loads()` + direct field access on the model's raw content either raises an unhandled exception (500, no chat reply shown to the operator) or silently proceeds with `None`/missing fields.

**Why it happens:** Even with structured-output support, providers vary in strictness, and network/inference issues can return partial or empty completions. Development often only exercises the happy path.

**How to avoid:** `chat/llm.py`'s `parse_reply()` wraps `json.loads()` in `try/except (json.JSONDecodeError, TypeError)`, defaults missing/`None` `missions`/`roster_changes` arrays to `[]` before validation, and raises a single `LLMError` on any failure (bad JSON, non-object payload, missing `message`, invalid enum value for `action`). The router catches `LLMError` and returns `HTTPException(502, {"reason": "llm_unavailable", ...})` — a clean, diagnosable failure rather than an unhandled 500 masking the real cause. Exercise this explicitly in `LLM_MOCK`-driven or `stub_completion`-monkeypatched tests: at least one scenario returning non-JSON content, one with a missing `message` field, and one with an invalid `action` enum value.

**Warning signs:** Chat endpoint returns intermittent 500s correlated with longer conversations or unusual phrasing (more context = higher chance of a truncated/malformed completion). No test coverage exists for malformed responses today — `chat/` and `backend/tests/chat/` are both empty stubs as of this research (verified: `ls backend/app/chat/` and `backend/tests/chat/` both show only `__pycache__`, no `.py` files, despite compiled bytecode from a prior session existing there).

### Pitfall 5: `response_format` silently dropped by LiteLLM's OpenRouter adapter (the CHAT-08 blocker)

**What goes wrong:** Passing `response_format={"type": "json_schema", "json_schema": {...}}` as a **top-level keyword argument** to `litellm.acompletion(model="openrouter/openai/gpt-oss-120b", ...)` does not reliably reach OpenRouter. LiteLLM internally gates whether it forwards `response_format` on `litellm.utils.supports_response_schema(model, custom_llm_provider)`, and OpenRouter is not included in the provider list this function recognizes as structured-output-capable — so the OpenRouter-specific request-mapping code path (`OpenrouterConfig.map_openai_params()`) strips the parameter before the HTTP request is built. The official LiteLLM docs page on JSON mode (`docs.litellm.ai/docs/completion/json_mode`) lists structured-output support for "OpenAI, Azure OpenAI, xAI (Grok-2+), Google AI Studio (Gemini), Vertex AI (Gemini + Anthropic), Bedrock, Anthropic API, Groq, Ollama, and Databricks" — **OpenRouter is conspicuously absent from that list**, corroborating the bug reports. `[CITED: docs.litellm.ai/docs/completion/json_mode]`

**Why it happens:** LiteLLM maintains a hardcoded per-provider support matrix for structured outputs; OpenRouter (which itself proxies to many underlying model providers with varying schema support) was never added to that matrix, even though the underlying OpenRouter API and many of its routed models genuinely do support `response_format`. This is tracked as open/recently-fixed in the LiteLLM issue tracker: `BerriAI/litellm` issue #13438 ("Support OpenRouter `response_format`"), issue #10465 ("Response Format should be supported for OpenRouter"), and discussion #11652 ("Forcing Structured JSON Output in LiteLLM + OpenRouter (FIXED)"). `[CITED: github.com/BerriAI/litellm discussions #11652, issues #13438, #10465 — verified via WebSearch + WebFetch this session]`

**How to avoid:** Nest `response_format` **inside** `extra_body` instead of passing it top-level. This is the confirmed, maintainer-acknowledged workaround (`discussions/11652`, fetched and read this session):

```python
# Source: github.com/BerriAI/litellm discussion #11652 (fetched this session),
# adapted to this project's schema/provider-routing requirements
response = await litellm.acompletion(
    model="openrouter/openai/gpt-oss-120b",
    api_key=api_key,
    messages=messages,
    extra_body={
        "response_format": {
            "type": "json_schema",
            "json_schema": RESPONSE_SCHEMA,   # {"name": ..., "strict": True, "schema": {...}}
        },
        "provider": {"only": ["Cerebras"]},    # forces Cerebras as the OpenRouter inference provider
    },
)
```

Note the **capitalization**: Cerebras's own OpenRouter integration docs (`inference-docs.cerebras.ai/integrations/openrouter`, fetched this session) show the exact request body as `"provider": {"only": ["Cerebras"]}` — capital `"Cerebras"` — for the model `openai/gpt-oss-120b`. `[CITED: inference-docs.cerebras.ai/integrations/openrouter]` The sibling-branch reference implementation used lowercase `"cerebras"` in `PROVIDER_ROUTING = {"only": ["cerebras"]}`; OpenRouter's provider-routing matcher is commonly case-insensitive in practice, but since the authoritative Cerebras-published example uses the capitalized form, match it exactly rather than relying on undocumented case-insensitivity.

This satisfies CHAT-08's explicit requirement ("explicit `response_format` schema... forced to Cerebras provider routing rather than relying on auto-detection") precisely because it does *not* rely on LiteLLM's `supports_response_schema()` auto-detection at all — the schema is forced through regardless of what LiteLLM's internal provider matrix says.

**Warning signs:** The model's replies "usually" parse as JSON in casual manual testing (because a capable model follows the system-prompt instruction to emit JSON even without a hard schema constraint) but occasionally include markdown code fences, prose preambles, or drift from the exact field names/enum values — this is the tell that the schema constraint isn't actually being enforced server-side, only requested via prompt text.

**Phase to address:** This phase, and it must be verified with a **live smoke test** (real `OPENROUTER_API_KEY`, `LLM_MOCK` unset), not just unit tests against a monkeypatched `litellm.acompletion` — a monkeypatched test cannot catch a parameter-stripping bug that happens inside LiteLLM's real OpenRouter adapter. Recommend an early (Wave 0 or Wave 1) plan task: a standalone script or pytest-marked-`@pytest.mark.live`/skippable-by-default test that calls `generate_reply()` with mocking disabled and asserts the response is valid JSON matching `RESPONSE_SCHEMA` — this closes out STATE.md's flagged risk with executed evidence, not just documentation review. This research could not run that live call itself (no access to `.env`/`OPENROUTER_API_KEY` from this sandboxed research session by design — secrets are outside a research agent's read boundary).

## Code Examples

### Structured-output schema (matches PLAN.md §9's documented shape exactly)

```python
# Source: sibling branch agent_team_work commit 2ba52a8:backend/app/chat/llm.py,
# cross-checked against planning/PLAN.md §9's documented schema
RESPONSE_SCHEMA = {
    "name": "flight_director_reply",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "missions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drone_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["launch", "recall"]},
                        "zone": {"type": ["string", "null"]},
                        "distance_km": {"type": ["number", "null"]},
                    },
                    "required": ["drone_id", "action", "zone", "distance_km"],
                    "additionalProperties": False,
                },
            },
            "roster_changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drone_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["add", "remove"]},
                    },
                    "required": ["drone_id", "action"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["message", "missions", "roster_changes"],
        "additionalProperties": False,
    },
}
```

Note `zone`/`distance_km` are typed `["string"|"number", "null"]` and marked `required` (present-but-nullable) rather than omitted — this is the correct pattern for OpenAI/OpenRouter-style `strict: true` JSON-schema mode, which requires every property listed in `properties` to also appear in `required` when `additionalProperties: false` is set.

### Chat history persistence and replay (matches current `chat_messages` schema exactly)

```python
# Source: backend/app/db/schema.py (read this session, lines 48-55) —
# chat_messages table verified as already present, no migration needed:
#   CREATE TABLE IF NOT EXISTS chat_messages (
#       id TEXT PRIMARY KEY, operator_id TEXT NOT NULL DEFAULT 'default',
#       role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
#       content TEXT NOT NULL, actions TEXT, created_at TEXT NOT NULL);
#   CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages (created_at);
# Repository pattern adapted from sibling branch agent_team_work commit
# 2ba52a8:backend/app/chat/repository.py
async def get_recent_messages(db, limit: int = 20, operator_id: str = "default") -> list[ChatMessage]:
    """The last `limit` messages, oldest first — ready to replay as LLM history."""
    rows = await db.fetchall(
        "SELECT * FROM chat_messages WHERE operator_id = ? "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (operator_id, limit),
    )
    return [_row_to_message(row) for row in reversed(rows)]
```

`role` values are constrained by the schema's own `CHECK (role IN ('user', 'assistant'))` `[VERIFIED: backend/app/db/schema.py:51]` — matches `CHAT_ROLES = ("user", "assistant")` in `chat/models.py`.

### Test double for `litellm.acompletion` (avoids ever hitting the network in unit tests)

```python
# Source: sibling branch agent_team_work commit 2ba52a8:backend/tests/chat/conftest.py
@pytest.fixture
def stub_completion(monkeypatch):
    import litellm
    calls: list[dict] = []

    def _install(result):
        async def _fake_acompletion(**kwargs):
            calls.append(kwargs)   # assert extra_body shape here — catches Pitfall 5 regressions
            if isinstance(result, Exception):
                raise result
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=result))])
        monkeypatch.setattr(litellm, "acompletion", _fake_acompletion)
        return calls

    return _install
```

This fixture's recorded `calls` list is the right place to add an assertion like `assert calls[0]["extra_body"]["response_format"]["json_schema"] == RESPONSE_SCHEMA` and `assert calls[0]["extra_body"]["provider"] == {"only": ["Cerebras"]}` — a unit test that would have caught the top-level-vs-nested `response_format` placement bug if the reference implementation's tests had asserted on kwarg shape rather than only on parsed-reply behavior.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| Trusting LiteLLM's `supports_response_schema()` auto-detection for OpenRouter models | Explicitly nesting `response_format` in `extra_body`, bypassing the auto-detection gate | Ongoing as of this research (LiteLLM issues #13438/#10465 still open at time of research; #11652 documents the workaround, not a library-side fix) | CHAT-08 exists specifically because "auto-detection" is not yet reliable for this provider combination — this is not a stale/deprecated pattern to avoid, it is the *current* correct workaround until LiteLLM's internal provider matrix is updated |

**Deprecated/outdated:** None identified specific to this phase's stack — LiteLLM, OpenRouter, and Cerebras's OpenRouter integration are all actively maintained/current as of this research date.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `litellm>=1.96.0` is the correct version to pin (matches sibling-branch reference and already-installed `.venv` version) | Standard Stack, Package Legitimacy Audit | Low — `pip index versions` independently confirmed `1.96.0`/`1.96.2` exist on PyPI live this session; only the *legitimacy verdict* (not the version number) carries residual risk, gated by the required `checkpoint:human-verify` |
| A2 | OpenRouter's provider-routing matcher accepts capitalized `"Cerebras"` (per Cerebras's own docs) and is likely also tolerant of lowercase `"cerebras"` (as the sibling-branch reference uses) | Pitfall 5 / Code Examples | Low-medium — if case-sensitive and the plan uses lowercase, provider routing could silently fall through to a different/no provider; mitigated by the live smoke-test task recommended in Pitfall 5, which will surface this immediately as a real API response, not a guess |
| A3 | No confirmation gate is required before AI-executed actions (per `REQUIREMENTS.md` Out of Scope table) applies unchanged to this phase, with no new discussion-phase input to override it | User Constraints, Don't Hand-Roll | Low — this is a `REQUIREMENTS.md`-level decision already made for the whole milestone, not something this phase's research introduced |

**If this table is empty:** N/A — see entries above; none of them concern compliance/retention/security posture, only version-pin confidence and an unverified string-casing detail resolvable by the smoke test already recommended.

## Open Questions

1. **Does the plan need a `chat/service.py`, or is folding orchestration into `router.py` (as the reference implementation does) acceptable long-term?**
   - What we know: The milestone-level `ARCHITECTURE.md` research (written before Phase 1 completed) recommended a `service.py` for chat; the actual sibling-branch reference implementation skipped it and put `execute_actions()` directly in `router.py`, keeping `llm.py` as the only other non-router module.
   - What's unclear: Whether the planner should follow the milestone-level architecture doc's original recommendation (a `service.py`) or the working reference implementation's simpler shape.
   - Recommendation: Follow the reference implementation's simpler shape (no `chat/service.py`) — it's proven-buildable code, the "service logic" here is thin (call LLM, loop over actions, persist), and `router.py`'s `execute_actions()` is already unit-testable in isolation from the FastAPI route itself (it's a plain async function, not embedded in the route closure). The planner should treat this as Claude's discretion, not a blocking question, since no CONTEXT.md exists to weigh in.

2. **Should the live OpenRouter/Cerebras smoke test run automatically in CI, or only manually/gated?**
   - What we know: PLAN.md §12 and this project's `LLM_MOCK=true` default mean E2E/CI tests should not need a real API key. `OPENROUTER_API_KEY` is present in the project's `.env` (per PROJECT.md) but this research session could not and should not read that file's contents.
   - What's unclear: Whether CI has `OPENROUTER_API_KEY` available as a secret, or whether the smoke test is a manual/local-only verification step.
   - Recommendation: Make the smoke test skippable-by-default (e.g., `pytest.mark.skipif` on a missing `OPENROUTER_API_KEY` env var, or a standalone script invoked manually), run once during phase execution/verification with the operator's real key, and never required for the automated pytest suite or E2E `LLM_MOCK=true` runs.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|-----------|
| `litellm` (PyPI package) | CHAT-08 LLM calls | Partially — already installed in local `.venv` (`litellm-1.96.0.dist-info` found) but **not yet declared** in `backend/pyproject.toml`/`backend/uv.lock` `[VERIFIED: backend/pyproject.toml — read this session, no `litellm` line present; backend/.venv/lib/python3.12/site-packages/litellm-1.96.0.dist-info — confirmed present via `find` this session]` | `1.96.0` (installed, undeclared) | Run `uv add "litellm>=1.96.0"` + `uv sync` in Wave 0 to reconcile the lockfile with what's already on disk |
| `OPENROUTER_API_KEY` | Real (non-mock) LLM calls, the CHAT-08 smoke test | Not verified this session — reading `.env` is outside this research agent's permitted boundary; PROJECT.md states it is present in the project root `.env` | — | `LLM_MOCK=true` covers all automated tests; only the recommended live smoke test needs the real key, and only for a manual/gated run (see Open Question 2) |
| `ctx7` CLI (Context7 documentation lookup) | This research session's own tooling | Not installed globally; `npx ctx7@latest` worked when run with the sandbox override (`dangerouslyDisableSandbox`) due to an `EROFS` write-permission error on `~/.npm/_cacache` under default sandboxing | n/a | Not a build-time dependency of the phase itself — informational only |

**Missing dependencies with no fallback:** None — `litellm` has a clear one-command fix (`uv add`), and the API key's presence is asserted by prior project docs even though unverified in this session.

**Missing dependencies with fallback:** `OPENROUTER_API_KEY` (fallback: `LLM_MOCK=true` for all automated testing).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=8.3.0` + `pytest-asyncio>=0.24.0` `[VERIFIED: backend/pyproject.toml — read this session]` |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `asyncio_mode = "auto"` `[VERIFIED: backend/pyproject.toml, read this session]` |
| Quick run command | `cd backend && uv run --extra dev pytest tests/chat -v` |
| Full suite command | `cd backend && uv run --extra dev pytest -v --cov=app` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| CHAT-01 | `POST /api/chat` returns `{message, missions?, roster_changes?}` | integration | `pytest tests/chat/test_router.py::test_returns_structured_response -x` | ❌ Wave 0 |
| CHAT-02 | Launch action delegates to `missions.service.launch_mission` with matching kwargs | unit | `pytest tests/chat/test_router.py::test_launch_delegates_to_missions_service -x` | ❌ Wave 0 |
| CHAT-03 | Recall action delegates to `missions.service.recall_mission` | unit | `pytest tests/chat/test_router.py::test_recall_delegates_to_missions_service -x` | ❌ Wave 0 |
| CHAT-04 | Roster add/remove delegates to `roster.service`, not `roster.repository` (Pitfall 1 regression guard) | unit | `pytest tests/chat/test_router.py::test_roster_change_uses_roster_service -x` | ❌ Wave 0 |
| CHAT-05 | Recent `chat_messages` rows load into prompt history, oldest-first | unit | `pytest tests/chat/test_repository.py::test_get_recent_messages_ordering -x` | ❌ Wave 0 |
| CHAT-06 | `LLM_MOCK=true` never calls `litellm.acompletion` | unit | `pytest tests/chat/test_llm.py::test_mock_mode_skips_network_call -x` | ❌ Wave 0 |
| CHAT-07 | Invalid `drone_id`/negative `distance_km`/malformed JSON surfaces as chat-response error, not a crash | unit + integration | `pytest tests/chat/test_llm.py::TestParseReply -x` and `tests/chat/test_router.py::test_invalid_action_surfaces_error -x` | ❌ Wave 0 |
| CHAT-08 | `extra_body` contains nested `response_format` + `provider: {"only": ["Cerebras"]}`; live smoke test parses real Cerebras output | unit + live (manual/gated) | `pytest tests/chat/test_llm.py::test_extra_body_shape -x` (unit, via `stub_completion`) + a manual/skippable live smoke script | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && uv run --extra dev pytest tests/chat -v`
- **Per wave merge:** `cd backend && uv run --extra dev pytest -v --cov=app`
- **Phase gate:** Full backend suite green before `/gsd-verify-work`, plus the live CHAT-08 smoke test executed at least once with a real `OPENROUTER_API_KEY` and its output (raw JSON reply) captured as verification evidence.

### Wave 0 Gaps

- [ ] `backend/tests/chat/__init__.py`, `conftest.py` — currently empty stub directories (pycache-only); need the `db`/`cache`/`stub_completion` fixtures (Code Examples above)
- [ ] `backend/tests/chat/test_llm.py`, `test_repository.py`, `test_router.py` — none exist yet
- [ ] `litellm` dependency declaration: `uv add "litellm>=1.96.0"` in `backend/pyproject.toml` + `uv sync` (package-legitimacy `checkpoint:human-verify` gate applies here — see Package Legitimacy Audit)
- [ ] `backend/app/main.py` wiring: add `from app.chat import create_chat_router` and `app.include_router(create_chat_router(database, telemetry_cache, telemetry_source))` — verified current `main.py` (read this session) does not yet import or mount `chat` at all, and does not yet mount `roster` either despite Phase 1 being complete (`create_roster_router` is imported but never `include_router`-ed in the version read this session) — **the planner should confirm/fix the roster-router mounting gap as part of this phase's Wave 0 or flag it as a pre-existing Phase 1 loose end**, since chat's roster actions are meaningless if `/api/roster` itself isn't reachable

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|-----------------|---------|---------------------|
| V2 Authentication | No | Explicitly out of scope for the whole milestone (`REQUIREMENTS.md` Out of Scope: "Authentication / multi-tenant support") — single-operator, no-auth by design |
| V3 Session Management | No | No sessions; single hardcoded `operator_id="default"` |
| V4 Access Control | No | Same as V2 — no access control boundary exists in this milestone |
| V5 Input Validation | Yes | Pydantic (`ChatRequest.message: str = Field(min_length=1)` for the HTTP boundary; `FlightDirectorReply`/`MissionAction`/`RosterChange` for the LLM-output boundary) — both boundaries already covered by the validated-boundary pattern (Pattern 1) |
| V6 Cryptography | No | No new cryptographic operations in this phase; `OPENROUTER_API_KEY` is an opaque bearer credential read from environment, not a cryptographic primitive this phase implements |

### Known Threat Patterns for LLM tool-calling / structured-output backends

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| Prompt injection via operator chat message causing the LLM to propose unintended mission/roster actions | Tampering / Elevation of Privilege | Not preventable at the prompt layer alone (out of scope to attempt full prompt-injection hardening per PLAN.md's zero-stakes design decision) — but fully *contained* by Pattern 1: every proposed action still passes through real `missions.service`/`roster.service` validation (unknown drone rejected, budget enforced, one-active-mission-per-drone enforced) regardless of why the LLM proposed it, so the blast radius of a successful injection is bounded to "a valid mission/roster mutation the same UI already allows a human to make manually," not arbitrary code/DB access |
| Secrets (`OPENROUTER_API_KEY`) leaking into logs at DEBUG level | Information Disclosure | Already flagged in `.planning/codebase/CONCERNS.md` as a pre-existing project-wide concern, not new to this phase — logging is INFO by default; this phase should not add any `logger.debug()` call that includes `api_key`, request headers, or raw LiteLLM `extra_body` kwargs (which contain no secrets themselves, but adjacent logging of the full `acompletion()` call could accidentally capture `api_key` if logged carelessly) |
| LLM response used to construct a DB query/shell command without going through typed models first | Tampering | Prevented by design: `parse_reply()` validates into typed Pydantic models before any field is read; no raw string interpolation of LLM output into SQL (all DB access already goes through parameterized queries in `missions.repository`/`roster.repository`, unchanged by this phase) |

## Sources

### Primary (HIGH confidence)
- `backend/app/missions/service.py`, `repository.py`, `models.py`, `router.py` — read directly this session
- `backend/app/roster/service.py`, `repository.py`, `models.py`, `router.py`, `__init__.py` — read directly this session
- `backend/app/db/schema.py`, `connection.py` — read directly this session
- `backend/app/main.py` — read directly this session
- `backend/pyproject.toml`, `backend/.venv/lib/python3.12/site-packages/*.dist-info` — read/inspected directly this session
- Sibling git branch `agent_team_work`, commit `2ba52a8` (`backend/app/chat/{models,context,llm,repository,router}.py`, `backend/tests/chat/*.py`) — read directly via `git show` this session; treated as prior-art reference to adapt, not authoritative spec, since it predates/parallels the current `roster.service` shape and has the CHAT-08 placement bug
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/PROJECT.md`, `planning/PLAN.md` §9 — read directly this session (project's own binding spec/state)
- `.planning/codebase/CONCERNS.md`, `INTEGRATIONS.md` — read directly this session

### Secondary (MEDIUM confidence)
- `docs.litellm.ai/docs/completion/json_mode` (via Context7, library `/websites/litellm_ai`) — "Structured Outputs (JSON Mode)" supported-provider list, notably omitting OpenRouter
- `docs.litellm.ai/docs/providers/openrouter` (via Context7) — custom OpenRouter parameter passthrough (`transforms`, `route`, `models`) confirms `extra_body`/direct-kwarg passthrough is a supported mechanism for this provider
- `github.com/BerriAI/litellm` discussion #11652 ("Forcing Structured JSON Output in LiteLLM + OpenRouter (FIXED)") — fetched and read this session; the primary source for the `extra_body`-nesting workaround
- `inference-docs.cerebras.ai/integrations/openrouter` — fetched this session; exact `provider: {"only": ["Cerebras"]}` request-body example and model id confirmation

### Tertiary (LOW confidence)
- WebSearch summaries of `github.com/BerriAI/litellm` issues #13438 and #10465 — corroborating evidence for the `supports_response_schema()` gap, not fetched in full; treated as directional confirmation of the discussion #11652 finding, not an independent primary source
- `gsd-tools query package-legitimacy check --ecosystem pypi litellm` seam output — returned `SUS` with all-`null` signals (tooling/network gap, not a substantive finding); superseded in this document's actual risk assessment by the directly-verified live PyPI registry data, but the `SUS` disposition and required `checkpoint:human-verify` are preserved per protocol regardless

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `litellm` version/repo confirmed via live PyPI registry calls this session; only the automated legitimacy-seam verdict (not the underlying facts) is unresolved, and that's handled via the required checkpoint
- Architecture: HIGH — every function signature, exception class, and schema referenced in this document was read directly from the current codebase this session, not inferred or assumed from the sibling branch
- Pitfalls: HIGH for Pitfalls 1-4 (directly verified against current source); HIGH for Pitfall 5's problem statement (confirmed via official docs + GitHub issue tracker) and MEDIUM for the exact fix's guaranteed effectiveness against `openrouter/openai/gpt-oss-120b` + Cerebras specifically (the discussion thread's example used a different underlying model; the mechanism — bypassing `supports_response_schema()` via `extra_body` — is general, but this phase's plan should still include the live smoke test to confirm empirically, as recommended)

**Research date:** 2026-08-12
**Valid until:** 2026-09-11 (30 days — LiteLLM releases frequently and issues #13438/#10465 could be resolved upstream within that window, which would make the `extra_body` nesting workaround still-correct-but-no-longer-strictly-necessary; re-check `supports_response_schema()`'s provider list before reusing this research past that date)
