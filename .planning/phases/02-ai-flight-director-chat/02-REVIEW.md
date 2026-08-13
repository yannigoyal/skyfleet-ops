---
phase: 02-ai-flight-director-chat
reviewed: 2026-08-13T02:58:18Z
depth: deep
files_reviewed: 20
files_reviewed_list:
  - backend/app/chat/__init__.py
  - backend/app/chat/context.py
  - backend/app/chat/llm.py
  - backend/app/chat/models.py
  - backend/app/chat/repository.py
  - backend/app/chat/router.py
  - backend/app/main.py
  - backend/pyproject.toml
  - backend/tests/chat/__init__.py
  - backend/tests/chat/conftest.py
  - backend/tests/chat/test_evals.py
  - backend/tests/chat/test_live_smoke.py
  - backend/tests/chat/test_llm.py
  - backend/tests/chat/test_repository.py
  - backend/tests/chat/test_router.py
  - backend/tests/chat/fixtures/README.md
  - backend/tests/chat/fixtures/01-explicit-launch.json
  - backend/tests/chat/fixtures/02-recall-en-route.json .. 14-injection-style-message.json (14 fixture files, all read)
  - backend/uv.lock
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-08-13T02:58:18Z
**Depth:** deep
**Files Reviewed:** 20 (backend/app/chat/ full package, backend/app/main.py wiring diff, backend/pyproject.toml, and the full backend/tests/chat/ package including all 14 fixtures)
**Status:** issues_found

## Summary

The chat package is well-structured and largely delivers on the AI-SPEC's headline promise: every write path in `backend/app/chat/router.py` genuinely reaches `missions.service`/`roster.service` only (verified independently by re-reading the service/repository layers, and confirmed by the codebase's own AST-based `TestImportBoundary` tests, which are not vacuous — the SUMMARY documents they were proven to fail against a reproduced regression before being trusted). The `extra_body` nesting for `response_format`/`provider` in `llm.py` is correct, single-definition-sited via `_extra_body()`, and locked in by a kwarg-shape regression test (`TestExtraBodyShape`) that the SUMMARY documents as RED-before-GREEN verified. Secret hygiene for the `OPENROUTER_API_KEY` value itself is solid — it is never logged and never echoed into a response body anywhere I could find, and this is independently tested (`TestSecretHygiene`).

However, tracing the numeric `distance_km` field all the way from the LLM's raw JSON through Pydantic, the router's own precondition guard, and into `missions.repository.create_mission`'s budget check turned up a genuine data-integrity hole: a completion containing a literal `NaN` for `distance_km` silently bypasses every guard in the chain and can permanently corrupt the operator's energy budget. This is exactly the class of "constraint parity with manual dispatch" regression (AI-SPEC dimension D2, Critical) the differential-testing pattern in this phase was built to catch for roster removal — but the same rigor was not applied to the launch-argument numeric guard (AI-SPEC guardrail G3 explicitly names NaN/inf as in-scope, but the implementation only checks `<= 0`). I also found that the phase's own documented "single most important number" — the schema-failure rate captured by the one mandated per-turn log line — is structurally unobservable for exactly the requests it exists to detect (502/`LLMError` turns never reach the `logger.info` call), and that the "second, independent validation layer" (Pydantic) is more permissive than the JSON schema it's supposed to mirror (`additionalProperties: false` vs. Pydantic's default `extra="ignore"`).

None of these are exotic to trigger — the NaN case in particular is empirically reproducible with plain Python (`json.loads` accepts bare `NaN`/`Infinity` tokens by default, and Pydantic's plain `float` type accepts `nan` with no complaint), and it lands squarely inside the phase's own "structured-output enforcement silently degrading to prompt-only compliance" failure mode (AI-SPEC §1, failure mode 4) — the exact scenario under which a model is most likely to emit a non-numeric literal instead of a well-formed number.

## Critical Issues

### CR-01: A `NaN` `distance_km` from the LLM bypasses every guard and permanently corrupts the operator's energy budget

**File:** `backend/app/chat/router.py:54`, `backend/app/chat/llm.py:87`
**Issue:**
`_execute_mission`'s launch-argument precondition is:
```python
if not action.zone or action.distance_km is None or action.distance_km <= 0:
    return None, f"Could not launch {action.drone_id}: missing zone or distance."
```
`MissionAction.distance_km` (llm.py:87) is a plain `float | None = None` with no `gt`/`allow_inf_nan` constraint. Contrast this with the **manual** REST dispatch path (`backend/app/missions/router.py:28`), which declares `distance_km: float = Field(gt=0)` — Pydantic's `Gt` constraint does reject `NaN` (because `nan > 0` evaluates `False`, and Pydantic raises when the comparison isn't `True`). The chat path has no such constraint and instead relies on the router's own hand-rolled `<= 0` check, which is **not** equivalent: NaN comparisons are always `False` in Python, so `nan <= 0` is `False` and the guard is silently skipped.

I traced the full chain end to end and reproduced the key steps:
```
>>> json.loads('{"distance_km": NaN}')          # Python's json module accepts bare NaN by default
{'distance_km': nan}
>>> nan <= 0                                     # router.py:54's guard
False
>>> Pydantic float field accepts nan with no error (verified against backend/.venv)
>>> energy_cost_kwh = round(nan * 0.8, 4)        # missions/service.py -> Mission.energy_cost_for
nan
>>> nan > remaining                              # missions/repository.py:132's budget check
False
```
A mission is created with `energy_cost_kwh = NaN`, which is written into the **append-only** `mission_log` table. From that point forward, `_spent_kwh()`'s `SUM(energy_cost_kwh)` returns `NaN` for the operator, and every subsequent `remaining_kwh` computation — for **both** the chat path and the manual REST dispatch bar, since they share `missions.repository` — permanently returns `NaN`. There is no delete path for `mission_log` rows (by design, per `PLAN.md` §7 and the repository's own docstring), so this is not self-healing; it requires manual DB surgery to recover.

This is precisely the AI-SPEC's own documented risk: guardrail **G3** ("Launch-argument completeness precondition") explicitly names `NaN` and `inf` as values that must be blocked ("A `launch` action with `zone=None`, `distance_km=None`, `<= 0`, `NaN`, or `inf`"), and dimension **D2** ("Constraint parity with manual dispatch") is rated Critical specifically because a chat-issued action taking a *looser* validation path than the manual REST equivalent is the named regression pattern for this phase. The roster-removal case of this exact pattern (Pitfall 1) got a dedicated differential test; this numeric case did not, and no fixture or unit test in `tests/chat/` exercises a NaN/Infinity `distance_km`.

(`Infinity`/`-Infinity` are, by contrast, actually caught — `inf > remaining` is `True` in Python, so `InsufficientBudgetError` correctly fires downstream in `missions/repository.py`, just not via the router's own G3 guard as documented.)

**Fix:**
```python
# backend/app/chat/router.py
import math
...
if (
    not action.zone
    or action.distance_km is None
    or not math.isfinite(action.distance_km)
    or action.distance_km <= 0
):
    return None, f"Could not launch {action.drone_id}: missing zone or distance."
```
Also consider hardening the Pydantic side to match the manual REST model's rigor, so the guard doesn't live only in router.py:
```python
# backend/app/chat/llm.py
class MissionAction(BaseModel):
    drone_id: str
    action: Literal["launch", "recall"]
    zone: str | None = None
    distance_km: float | None = Field(default=None, allow_inf_nan=False)
```
Add a fixture (e.g. `15-nan-distance-launch.json`) pinning `distance_km: NaN`/`Infinity` to a rejected, zero-delta outcome, mirroring the rigor already applied to fixture 4's roster-removal differential.

## Warnings

### WR-01: The schema-failure rate — "the single most important number in this phase" — is unobservable from the mandated log line, and the raw failed completion is never logged anywhere

**File:** `backend/app/chat/router.py:106-113`, `backend/app/chat/llm.py` (no logger)
**Issue:** AI-SPEC §7 states the per-turn `logger.info` line is designed to carry "Schema-failure rate — `LLMError`/502 count per 100 turns. *The* CHAT-08 regression canary; the single most important number in this phase," and §6 guardrail G1 requires "Log the raw failed `content` string at INFO for diagnosis." In the actual implementation:
```python
try:
    reply = await generate_reply(fleet_context, history, request.message)
except LLMError as exc:
    raise HTTPException(status_code=502, detail={"reason": exc.reason, "detail": str(exc)}) from exc
elapsed_ms = (time.monotonic() - start_time) * 1000
...
logger.info("chat turn: ...", ...)
```
The single `logger.info` call sits *after* the `try/except`, so any turn that raises `LLMError` (non-JSON completion, schema violation, transport failure, missing API key) returns via the `except` branch and never reaches the log line. `grep -rn "logger\.\|logging\." app/chat/` confirms there is exactly one `logger.info` call in the whole package and no logging anywhere in `llm.py` — so the raw failed `content` that G1 says should be logged for diagnosis is never logged at all; it only ever reaches the operator via the 502 response body. There is no test anywhere in `tests/chat/` that asserts a log record for a malformed-completion (502) turn — fixtures 10 and 11 (the two malformed-completion scenarios) only assert HTTP status and DB deltas, never log content.
**Fix:** Log inside the `except LLMError` branch before re-raising, and inside `parse_reply`'s failure branches (or pass the raw content back on the exception so the router can log it):
```python
except LLMError as exc:
    logger.info("chat turn: llm_error reason=%s detail=%s", exc.reason, str(exc)[:500])
    raise HTTPException(status_code=502, detail={"reason": exc.reason, "detail": str(exc)}) from exc
```

### WR-02: Pydantic reply models accept extra/unexpected fields, undermining the "second independent validation layer" the design relies on

**File:** `backend/app/chat/llm.py:83-98`
**Issue:** `RESPONSE_SCHEMA` (the JSON schema sent to the provider) sets `"additionalProperties": False` at every object level. AI-SPEC §3's Key Abstractions table describes `model_validate()` as "the second, independent validation layer... the layer actually trusted" precisely because the provider's own `strict:true` enforcement (layer 1) is the thing CHAT-08 already proved can silently regress. But `FlightDirectorReply`, `MissionAction`, and `RosterChange` don't set `model_config = ConfigDict(extra="forbid")`, so Pydantic's default (`extra="ignore"`) applies: if a completion ever contains stray/unexpected fields — exactly the shape drift you'd expect from the "structured-output enforcement silently regressing to prompt-only compliance" failure mode this phase is built around — layer 2 silently accepts it instead of raising `LLMError` the way the schema's `additionalProperties: false` says it should. No test in `test_llm.py::TestParseReply` exercises an extra-field completion.
**Fix:**
```python
from pydantic import BaseModel, ConfigDict, Field

class FlightDirectorReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    missions: list[MissionAction] = Field(default_factory=list)
    roster_changes: list[RosterChange] = Field(default_factory=list)
```
(and likewise for `MissionAction`/`RosterChange`), plus a parametrized case in `TestParseReply` for an extra-field completion.

### WR-03: `ChatRequest.message` has no upper bound

**File:** `backend/app/chat/router.py:40-41`
**Issue:** `ChatRequest.message` is constrained with `StringConstraints(strip_whitespace=True, min_length=1)` but no `max_length`. An arbitrarily large operator message is persisted verbatim to `chat_messages` and gets embedded in full into every subsequent prompt for the life of the 20-turn history window (`build_messages`), inflating LLM cost/latency per turn (working against AI-SPEC §4b's own token-budget discipline and G4) with no bound.
**Fix:**
```python
class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
```

### WR-04: Raw third-party exception text flows unsanitized into the HTTP 502 response body

**File:** `backend/app/chat/llm.py:206-219`
**Issue:**
```python
try:
    response = await litellm.acompletion(...)
    raw_content = response.choices[0].message.content
except Exception as exc:
    raise LLMError(f"flight director call failed: {exc}") from exc
```
and in `router.py`:
```python
raise HTTPException(status_code=502, detail={"reason": exc.reason, "detail": str(exc)}) from exc
```
The broad `except Exception` catches anything `litellm.acompletion` raises and folds `str(exc)` — the third-party library's own exception message, whose contents this codebase doesn't control — directly into an HTTP response body returned to the caller. This isn't a proven key leak (the key is passed as `api_key=`, not embedded in a URL/body litellm would echo back), but it's an unaudited pass-through of arbitrary internal error text (which can include request/response fragments depending on the underlying HTTP client's exception `__str__`) to any client hitting `/api/chat`, and it is not covered by any test — `TestSecretHygiene` only exercises the mock/stub path, never a real exception object from a failing transport call.
**Fix:** Log the full exception server-side (see WR-01) and return a generic, fixed message to the client:
```python
except Exception as exc:
    raise LLMError("flight director call failed") from exc  # detail logged separately, not echoed to the client
```

## Info

### IN-01: Dual import of the `llm` module and its named members is undocumented in the source

**File:** `backend/app/chat/router.py:32,34`
**Issue:**
```python
from . import llm, repository
from .llm import LLMError, MissionAction, RosterChange, generate_reply
```
Both the `llm` submodule and several of its members are imported side by side. This is deliberate (per `02-04-SUMMARY.md`: "so tests can monkeypatch `llm.mock_mode_enabled` and have both `generate_reply`'s internal call and the router's own log-line call see the patched value") — but that rationale lives only in the SUMMARY, not in the source file. A future maintainer reading only `router.py` would likely see this as duplicate/redundant imports and "clean it up" to a single `from .llm import ...`, silently breaking `llm.mock_mode_enabled` monkeypatch visibility for the log line.
**Fix:** Add a one-line comment at the import site, e.g. `# llm imported both ways: llm.mock_mode_enabled() below must see test monkeypatches of the module attribute.`

### IN-02: `_extract_reason` re-derives structured data from a formatted string

**File:** `backend/app/chat/router.py:88-92`
**Issue:** `_execute_mission`/`_execute_roster_change` already have `exc.reason` in hand at the point they format the error string (`f"Could not launch {action.drone_id} to {action.zone}: {exc.reason}."`), then later `_extract_reason` re-parses that same string via `error_message.rsplit(": ", 1)[-1].rstrip(".")` to recover the reason for the log line. It works today because every call site follows the same trailing `": {reason}."` convention, but it's fragile glue — a future error-message format change (e.g., adding trailing context after the reason) would silently break the log line's `reasons=` field without any test catching it, since nothing asserts `_extract_reason`'s output against the original `exc.reason` value directly.
**Fix:** Return the reason alongside the message from `_execute_mission`/`_execute_roster_change` (e.g. a small `Failure(drone_id, message, reason)` dataclass or a tuple), and pass reasons straight through to the log line instead of re-deriving them.

---

_Reviewed: 2026-08-13T02:58:18Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
