# Phase 2: AI Flight Director Chat - Pattern Map

**Mapped:** 2026-08-12
**Files analyzed:** 12 (5 new modules in `backend/app/chat/`, 4 new test files in `backend/tests/chat/`, plus `main.py`/`pyproject.toml` modifications, plus `__init__.py`)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/chat/models.py` | model | CRUD (dataclass + exceptions) | `backend/app/missions/models.py` | exact |
| `backend/app/chat/context.py` | utility | request-response (read-only aggregation) | `backend/app/roster/router.py` (`_entry_response` telemetry-merge helper) + `backend/app/missions/router.py` (`get_fleet_status`) | role-match |
| `backend/app/chat/llm.py` | service (external-call seam) | request-response (external API call + validation) | `backend/app/missions/service.py` | role-match (no direct analog for external LLM calls; service-layer shape reused) |
| `backend/app/chat/repository.py` | repository | CRUD | `backend/app/roster/repository.py` | exact |
| `backend/app/chat/router.py` | controller/router | request-response (orchestration + delegated CRUD) | `backend/app/missions/router.py` + `backend/app/roster/service.py` (delegation pattern) | exact (router shape) / role-match (orchestration logic) |
| `backend/app/chat/__init__.py` | config (barrel export) | — | `backend/app/roster/__init__.py` | exact |
| `backend/tests/chat/conftest.py` | test (fixtures) | — | existing `backend/tests/missions/conftest.py` or `backend/tests/roster/conftest.py` (db/cache fixtures) — verify path at plan time | role-match |
| `backend/tests/chat/test_llm.py` | test | — | `backend/tests/missions/test_service.py`-style unit tests | role-match |
| `backend/tests/chat/test_repository.py` | test | CRUD | `backend/tests/roster/test_repository.py`-style tests | role-match |
| `backend/tests/chat/test_router.py` | test | request-response | `backend/tests/roster/test_router.py` / `backend/tests/missions/test_router.py`-style endpoint tests | role-match |
| `backend/app/main.py` (modify) | config (wiring) | — | existing `create_roster_router` mount lines | exact |
| `backend/pyproject.toml` (modify) | config | — | n/a (dependency add via `uv add`) | n/a |

## Pattern Assignments

### `backend/app/chat/models.py` (model, CRUD)

**Analog:** `backend/app/missions/models.py`

**Module docstring + constants pattern** (lines 1-12):
```python
"""Data models, constants, and validation errors for mission scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MISSION_STATUSES = ("en_route", "delivered", "recalled")
UNSAFE_TELEMETRY_STATUSES = frozenset({"offline", "low_battery"})
```
For chat: `CHAT_ROLES = ("user", "assistant")` as the equivalent constant, matching the `chat_messages.role CHECK (role IN ('user','assistant'))` DB constraint.

**Frozen dataclass with `to_dict()`** (lines 15-41):
```python
@dataclass(frozen=True, slots=True)
class Mission:
    id: str
    operator_id: str
    drone_id: str
    zone: str
    distance_km: float
    energy_cost_kwh: float
    status: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "drone_id": self.drone_id,
            ...
        }
```
Mirror this exactly for `ChatMessage`: `id, operator_id, role, content, actions, created_at` fields, `@dataclass(frozen=True, slots=True)`, and a `to_dict()`.

**Error handling pattern** (lines 44-98) — exception hierarchy with `reason` class attribute:
```python
class MissionError(Exception):
    """Base class for mission validation failures raised by the service layer."""
    reason: str = "mission_error"


class UnknownDroneError(MissionError):
    reason = "unknown_drone"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone not on roster: {drone_id}")
```
Chat needs `LLMError` (per AI-SPEC's `chat/llm.py` sketch) following this exact shape — base exception with a `reason` attribute, raised on schema/parse failure. It does NOT need a `reason`-keyed HTTP-status lookup table entry unless the router maps it to 502 directly (see router pattern below).

---

### `backend/app/chat/repository.py` (repository, CRUD)

**Analog:** `backend/app/roster/repository.py`

**Imports + module docstring** (lines 1-13):
```python
"""SQLite-backed persistence for the fleet roster."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.db import Database

from .models import DroneAlreadyTrackedError, RosterEntry, UnknownDroneError

DEFAULT_OPERATOR_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
```

**Row-to-dataclass mapping + simple insert/query pattern** (lines 20-57):
```python
async def list_roster_entries(
    db: Database, operator_id: str = DEFAULT_OPERATOR_ID
) -> list[RosterEntry]:
    rows = await db.fetchall(
        "SELECT * FROM fleet_roster WHERE operator_id = ? ORDER BY drone_id", (operator_id,)
    )
    return [
        RosterEntry(id=row["id"], operator_id=row["operator_id"], drone_id=row["drone_id"], added_at=row["added_at"])
        for row in rows
    ]


async def add_drone(
    db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID
) -> RosterEntry:
    entry = RosterEntry(id=str(uuid.uuid4()), operator_id=operator_id, drone_id=drone_id, added_at=_now())
    await db.execute(
        "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
        (entry.id, entry.operator_id, entry.drone_id, entry.added_at),
    )
    return entry
```

Map directly onto `chat/repository.py`'s two functions (per RESEARCH.md Code Examples, already schema-verified against `backend/app/db/schema.py:48-55`):
```python
async def append_message(db, role, content, actions=None, operator_id="default") -> ChatMessage:
    # INSERT INTO chat_messages (id, operator_id, role, content, actions, created_at) VALUES (...)
    # actions param must be json.dumps(actions) if not None, else NULL

async def get_recent_messages(db, limit=20, operator_id="default") -> list[ChatMessage]:
    rows = await db.fetchall(
        "SELECT * FROM chat_messages WHERE operator_id = ? "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (operator_id, limit),
    )
    return [_row_to_message(row) for row in reversed(rows)]  # oldest-first for prompt replay
```
Note the `reversed(rows)` — this is the one departure from the roster analog's plain ascending-order query, required because `chat_messages` needs "most recent N, then oldest-first for replay," not a straightforward ORDER BY ASC.

**No custom exceptions needed here** — unlike `roster.repository`'s `sqlite3.IntegrityError` → `DroneAlreadyTrackedError` translation (lines 50-56), `chat_messages` has no UNIQUE constraint to violate on insert, so no `try/except sqlite3.IntegrityError` wrapping is needed in `chat/repository.py`.

---

### `backend/app/chat/context.py` (utility, request-response read-only aggregation)

**Analog:** `backend/app/missions/router.py::get_fleet_status()` (lines 53-63) + `backend/app/roster/router.py::_entry_response()` (lines 31-37)

**Read-only aggregation pattern** (missions/router.py lines 53-63):
```python
@router.get("")
async def get_fleet_status():
    remaining_kwh = await repository.get_remaining_kwh(db)
    budget = await repository.get_energy_budget(db)
    active = await repository.list_active_missions(db)
    return {
        "energy_budget_kwh": budget,
        "remaining_kwh": remaining_kwh,
        "active_mission_count": len(active),
        "missions": [_mission_response(mission, cache) for mission in active],
    }
```

**Telemetry-merge pattern** (roster/router.py lines 31-37):
```python
def _entry_response(entry: RosterEntry, cache: TelemetryCache) -> dict:
    payload = entry.to_dict()
    reading = cache.get(entry.drone_id)
    if reading:
        telemetry = reading.to_dict()
        payload.update({field: telemetry[field] for field in _TELEMETRY_FIELDS})
    return payload
```

`chat/context.py::build_fleet_context(db, cache) -> str` should combine both: call `missions.repository.get_remaining_kwh`, `get_energy_budget`, `list_active_missions`, `roster.repository.list_roster_entries`, then merge each roster drone with `cache.get(drone_id)` telemetry — exactly as `_entry_response` does — and format the whole thing as a system-message string (not a dict, since it becomes prompt text). This module has no writes and imports only from `app.missions.repository` and `app.roster.repository`, never their `service` modules (read-only, no mutation, no need for validation).

---

### `backend/app/chat/llm.py` (service — external-call seam, request-response)

**No direct in-repo analog** — this is the first module that calls an external API. Structural pattern borrowed from `missions/service.py`'s shape (validate → return typed model / raise typed exception) plus the exact implementation given in RESEARCH.md and AI-SPEC.md §3/§4b (already vetted against LiteLLM's OpenRouter pitfall).

**Service-layer shape to mirror** (`backend/app/missions/service.py` lines 30-46):
```python
async def launch_mission(
    db: Database, cache: TelemetryCache, *, drone_id: str, zone: str, distance_km: float
) -> Mission:
    """Validate and dispatch a mission to an explicit drone.

    Raises UnknownDroneError, DroneUnavailableError, DroneAlreadyEnRouteError,
    or InsufficientBudgetError on failure.
    """
    if not await repository.is_drone_on_roster(db, drone_id):
        raise UnknownDroneError(drone_id)
    ...
```
Same shape: `async def generate_reply(fleet_context, history, user_message) -> FlightDirectorReply`, docstring naming exactly which exception it raises (`LLMError`), keyword-only extra params if any are added later.

**Exact implementation (already correct per AI-SPEC/RESEARCH — copy near-verbatim, do not re-derive):**
```python
# From 02-AI-SPEC.md §3 Entry Point Pattern / §4b Structured Outputs
def mock_mode_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def parse_reply(raw_content: str) -> FlightDirectorReply:
    try:
        payload = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMError(f"non-JSON completion: {exc}") from exc
    payload.setdefault("missions", [])
    payload.setdefault("roster_changes", [])
    try:
        return FlightDirectorReply.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"schema validation failed: {exc}") from exc


async def generate_reply(fleet_context, history, user_message) -> FlightDirectorReply:
    if mock_mode_enabled():
        return FlightDirectorReply(message="Mock flight director reply.")

    response = await litellm.acompletion(
        model="openrouter/openai/gpt-oss-120b",
        api_key=os.environ["OPENROUTER_API_KEY"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": fleet_context},
            *history,
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        max_tokens=800,
        # response_format MUST be nested in extra_body for openrouter/* models
        extra_body={
            "response_format": {"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
            "provider": {"only": ["Cerebras"]},
        },
    )
    raw_content = response.choices[0].message.content
    return parse_reply(raw_content)
```
**Critical:** `response_format` and `provider` MUST be nested inside `extra_body`, never top-level (CHAT-08 / Pitfall 5). This is the single highest-risk correction versus the sibling-branch reference implementation.

---

### `backend/app/chat/router.py` (controller/router, request-response with delegated CRUD)

**Analog:** `backend/app/missions/router.py` (router factory + error-status mapping shape) + `backend/app/roster/service.py` (the "delegate to the exact same function manual dispatch uses" pattern)

**Router factory + dependency injection, no globals** (`missions/router.py` lines 49-51):
```python
def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:
    """Create the mission-dispatch router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/fleet", tags=["missions"])
```
Chat needs: `def create_chat_router(db: Database, cache: TelemetryCache, source: TelemetrySource | None) -> APIRouter` with `prefix="/api"` (endpoint is `/api/chat`, not `/api/chat/...`), `tags=["chat"]`.

**Error-to-HTTP-status lookup table pattern** (`missions/router.py` lines 15-22, `roster/router.py` lines 14-17):
```python
_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_en_route": 409,
    "drone_unavailable": 409,
    "no_active_mission": 404,
    "insufficient_budget": 422,
    "no_eligible_drone": 422,
}


def _error_response(exc: MissionError) -> HTTPException:
    status_code = _ERROR_STATUS.get(exc.reason, 400)
    detail: dict = {"reason": exc.reason}
    ...
    return HTTPException(status_code=status_code, detail=detail)
```
Chat's router does NOT need a `_ERROR_STATUS` table for mission/roster actions — per CHAT-07/Pattern 1, those errors are caught and turned into readable strings appended to the chat response body (200 OK with an `errors[]` array), not translated to HTTP status codes. The only place an HTTP-status mapping is needed is `LLMError` → `HTTPException(502, {"reason": "llm_unavailable", ...})` for the top-level malformed-completion case (per AI-SPEC §4b Retry logic), which is a single `except LLMError` clause, not a full lookup table.

**Request body validation model** (`missions/router.py` lines 25-28):
```python
class LaunchMissionRequest(BaseModel):
    drone_id: str | None = None
    zone: str
    distance_km: float = Field(gt=0)
```
Chat needs `ChatRequest(BaseModel): message: str = Field(min_length=1)`.

**Validated-boundary delegation pattern — the core of `router.py`** (from `02-RESEARCH.md` Pattern 1, corrected per Pitfall 1; also `02-AI-SPEC.md` §4 sketch):
```python
from app.missions import service as missions_service
from app.missions.models import MissionError
from app.roster import service as roster_service       # NOT roster.repository — Pitfall 1
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

**Full endpoint orchestration** (`02-AI-SPEC.md` §4 sketch, matches router-factory closure pattern used by `missions/router.py`/`roster/router.py`'s inner `@router.post` functions):
```python
def create_chat_router(db, cache, source) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["chat"])

    @router.post("/chat")
    async def post_chat(request: ChatRequest):
        fleet_context = await build_fleet_context(db, cache)
        history = await repository.get_recent_messages(db, limit=20)
        try:
            reply = await llm.generate_reply(fleet_context, _to_llm_history(history), request.message)
        except llm.LLMError as exc:
            raise HTTPException(status_code=502, detail={"reason": "llm_unavailable", "detail": str(exc)}) from exc

        executed_missions, mission_errors = [], []
        for action in reply.missions:
            result, error = await _execute_mission(db, cache, action)
            (executed_missions if result else mission_errors).append(result or error)

        executed_roster, roster_errors = [], []
        for change in reply.roster_changes:
            result, error = await _execute_roster_change(db, source, change)
            (executed_roster if result else roster_errors).append(result or error)

        await repository.append_message(db, "user", request.message, actions=None)
        await repository.append_message(
            db, "assistant", reply.message,
            actions={"missions": executed_missions, "roster_changes": executed_roster},
        )
        return {
            "message": reply.message,
            "missions": executed_missions,
            "roster_changes": executed_roster,
            "errors": mission_errors + roster_errors,
        }

    return router
```
**Critical (Pitfall 1 / D2 eval gate):** import `from app.roster import service as roster_service`, never `from app.roster import repository as roster_repository`. This is the single most likely regression to reintroduce — grep `app/chat/` for `roster.repository` or `roster_repository` at review time; it must return zero matches. Mission actions loop sequentially (one `await` per action, not batched) so a later action can correctly fail after an earlier one consumed budget — matches D6/Pitfall 3 requirement.

---

### `backend/app/chat/__init__.py` (config, barrel export)

**Analog:** `backend/app/roster/__init__.py` (exact shape, full file):
```python
"""Fleet roster: persistence for the drones an operator tracks."""

from .models import DroneAlreadyTrackedError, RosterEntry, RosterError, UnknownDroneError
from .router import create_roster_router

__all__ = [
    "DroneAlreadyTrackedError",
    "RosterEntry",
    "RosterError",
    "UnknownDroneError",
    "create_roster_router",
]
```
Chat's `__init__.py` (per RESEARCH.md's recommended structure comment: "exports CHAT_ROLES, ChatMessage, create_chat_router"):
```python
"""AI flight-director chat: LLM-proposed mission/roster actions, executed via the existing service layer."""

from .models import CHAT_ROLES, ChatMessage
from .router import create_chat_router

__all__ = ["CHAT_ROLES", "ChatMessage", "create_chat_router"]
```

---

### `backend/app/main.py` (config, wiring — modification)

**Analog:** existing roster import/mount lines (lines 22, 84):
```python
from app.roster import create_roster_router
...
app.include_router(create_roster_router(database, telemetry_cache, telemetry_source))
```
Add identically-shaped lines for chat:
```python
from app.chat import create_chat_router
...
app.include_router(create_chat_router(database, telemetry_cache, telemetry_source))
```
Insert both the import (grouped with the other `app.*` imports, alphabetically after `app.roster`... actually `chat` sorts before `db`/`missions`/`roster` alphabetically — follow existing import block ordering conventions at the edit site) and the `include_router` call directly after the roster line (line 84), preserving the `(database, telemetry_cache, telemetry_source)` argument order convention already established by roster's mount.

---

### Test files — `backend/tests/chat/{conftest,test_llm,test_repository,test_router}.py`

**Analogs:** existing `backend/tests/missions/` and `backend/tests/roster/` test suites (structure only — read the actual files at plan time to confirm exact fixture names/signatures, since they were not in this pattern-mapping pass's read budget but are directly referenced by RESEARCH.md as the established convention).

**`conftest.py` — stub for `litellm.acompletion`** (from `02-RESEARCH.md` Code Examples, verbatim-reusable):
```python
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
Combine with whatever `db`/`cache` pytest fixtures `tests/missions/conftest.py` or `tests/roster/conftest.py` already define (likely an in-memory/temp-file SQLite `Database` instance and a fresh `TelemetryCache()`) — reuse those exact fixtures via a shared `conftest.py` at `backend/tests/conftest.py` if one exists, or duplicate the pattern locally if each subsystem's tests are self-contained. Verify which at plan time by reading `backend/tests/missions/conftest.py` directly.

**Key assertion this fixture enables (CHAT-08/D3 gate):**
```python
assert calls[0]["extra_body"]["response_format"]["json_schema"] == RESPONSE_SCHEMA
assert calls[0]["extra_body"]["provider"] == {"only": ["Cerebras"]}
assert "response_format" not in calls[0]  # must NOT be top-level
```

**`test_router.py` — regression guard for Pitfall 1 (D2 eval gate):** assert `roster.service.add_drone`/`remove_drone` are called (e.g. via `monkeypatch` spy or by asserting DB side effects match the manual `DELETE /api/roster/{drone_id}` path's side effects), never `roster.repository.add_drone`/`remove_drone` directly.

---

## Shared Patterns

### Error handling — domain exception with `reason` attribute

**Source:** `backend/app/missions/models.py:44-98`, `backend/app/roster/models.py` (same shape)
**Apply to:** `chat/models.py`'s `LLMError`

```python
class MissionError(Exception):
    reason: str = "mission_error"

class UnknownDroneError(MissionError):
    reason = "unknown_drone"
    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone not on roster: {drone_id}")
```

### Router factory with injected dependencies, no globals

**Source:** `backend/app/missions/router.py:49-51`, `backend/app/roster/router.py:40-43`
**Apply to:** `chat/router.py::create_chat_router(db, cache, source)`

```python
def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:
    """Create the mission-dispatch router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/fleet", tags=["missions"])
```

### Validated-boundary delegation (LLM/chat proposes, existing service executes)

**Source:** `backend/app/roster/service.py:38-77` (`remove_drone`'s D-03 auto-recall guard — the exact behavior chat must not bypass) + `02-RESEARCH.md` Pattern 1
**Apply to:** `chat/router.py`'s `_execute_mission`/`_execute_roster_change` — must import `app.missions.service` and `app.roster.service`, never `app.missions.repository`/`app.roster.repository` directly.

### `_now()` UTC ISO-timestamp helper

**Source:** `backend/app/missions/repository.py:24-25`, `backend/app/roster/repository.py:16-17` (identical in both)
```python
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
```
**Apply to:** `chat/repository.py` — copy verbatim for `created_at` timestamps on `append_message`.

### `DEFAULT_OPERATOR_ID = "default"` module constant

**Source:** `backend/app/missions/repository.py:21`, `backend/app/roster/repository.py:13` (identical)
**Apply to:** `chat/repository.py` — same constant, same default-argument pattern (`operator_id: str = DEFAULT_OPERATOR_ID`) on both `append_message` and `get_recent_messages`.

## No Analog Found

None — every file has at least a role-match analog. The one structurally novel piece is the external LLM call in `chat/llm.py`, for which no in-repo analog exists (this is the first outbound network call in the backend besides the MAVLink gateway's `httpx` polling in `telemetry/mavlink_gateway.py`, which was not read this session but is worth a quick look at plan time for `httpx`/async-external-call conventions if `chat/llm.py`'s `litellm.acompletion()` usage needs additional error-handling precedent beyond RESEARCH.md/AI-SPEC.md's already-vetted implementation).

## Metadata

**Analog search scope:** `backend/app/missions/`, `backend/app/roster/`, `backend/app/main.py`, `backend/app/db/schema.py` (all read directly this session)
**Files scanned:** 12 (7 source files in missions/roster, `__init__.py`, `main.py`, plus RESEARCH.md/AI-SPEC.md's own embedded code excerpts from the sibling `agent_team_work` branch, cross-checked but not independently re-read since both docs already verified them against current source)
**Pattern extraction date:** 2026-08-12
