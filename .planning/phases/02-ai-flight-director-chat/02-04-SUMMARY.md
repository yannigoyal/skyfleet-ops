---
phase: 02-ai-flight-director-chat
plan: 04
subsystem: testing
tags: [pytest, evals, chat, litellm, structured-output, logging]

# Dependency graph
requires:
  - phase: 02-ai-flight-director-chat
    provides: "02-02's real LiteLLM/Cerebras call path (generate_reply, parse_reply, mock_mode_enabled) and 02-03's chat-issued mission/roster execution (router.py's sequential execution loops, error-string formatting)"
provides:
  - "Fourteen-fixture reference dataset replaying canned LLM completions through the real /api/chat endpoint offline"
  - "test_evals.py parametrised harness: the phase's CI gate, plus TestTransparency, TestSecretHygiene, TestTurnLogging"
  - "One structured logger.info line per completed chat turn in app/chat/router.py"
affects: [ai-integration, chat, observability]

# Actuals (#2632)
actuals:
  tokens: 8900
  tasks: 2
  commits: 2

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fixture-as-data eval scenarios: JSON files (seed/user_message/completion/expect) discovered by glob and parametrised over one harness, so adding a scenario is adding a file"
    - "Real-path replay: stub_completion + monkeypatched mock_mode_enabled() forces the canned completion through the real parse_reply and service-layer execution, never the keyword-based mock_reply"
    - "Percent-style lazy logging for structured per-turn metrics, never an f-string, so log aggregation stays parseable"

key-files:
  created:
    - backend/tests/chat/fixtures/README.md
    - backend/tests/chat/fixtures/01-explicit-launch.json
    - backend/tests/chat/fixtures/02-recall-en-route.json
    - backend/tests/chat/fixtures/03-roster-add.json
    - backend/tests/chat/fixtures/04-roster-remove-with-active-mission.json
    - backend/tests/chat/fixtures/05-read-only-question.json
    - backend/tests/chat/fixtures/06-hallucinated-drone.json
    - backend/tests/chat/fixtures/07-invalid-launch-arguments.json
    - backend/tests/chat/fixtures/08-over-budget-launch.json
    - backend/tests/chat/fixtures/09-recall-no-active-mission.json
    - backend/tests/chat/fixtures/10-non-json-completion.json
    - backend/tests/chat/fixtures/11-schema-violation.json
    - backend/tests/chat/fixtures/12-two-launches-budget-exhausted.json
    - backend/tests/chat/fixtures/13-contradictory-launch-and-recall.json
    - backend/tests/chat/fixtures/14-injection-style-message.json
    - backend/tests/chat/test_evals.py
  modified:
    - backend/app/chat/router.py

key-decisions:
  - "expect.missions/roster_changes compared as sets of (drone_id, action) pairs, not full mission objects — the harness pins outcome, not response-shape incidentals"
  - "Optional expect.final_mission_status / final_active_mission_count fields added beyond the plan's base schema to pin fixture 13's exact ordering outcome (recalled status, zero active) and fixture 14's containment outcome, without a bespoke test function"
  - "test_no_action_is_silently_dropped and TestTransparency both key off expect.status != 200 to skip the two malformed-completion fixtures, rather than re-deriving 'is this fixture malformed' from the completion string a second way"
  - "router.py imports `from . import llm` (module reference) alongside the existing `from .llm import ...` names, so tests can monkeypatch `llm.mock_mode_enabled` and have both generate_reply's internal call and the router's own log-line call see the patched value"
  - "Token counts recorded as None per the plan's explicit instruction — generate_reply's signature is unchanged in this plan, so there is no usage object to read"

requirements-completed: [CHAT-07]

coverage:
  - id: D1
    description: "Eleven-scenario reference dataset (explicit launch/recall/roster add/remove, read-only question, hallucinated drone, invalid launch args, over-budget launch, recall with no active mission, non-JSON completion, schema-violating completion) replaying through the real endpoint offline"
    requirement: "CHAT-07"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::test_fixture_scenario (parametrised, 11 of 14 ids)"
        status: pass
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::test_no_action_is_silently_dropped (parametrised)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Three adversarial/transparency fixtures: sequential budget exhaustion across two launches, contradictory launch+recall in one reply, injection-style message contained to a manual-equivalent removal"
    requirement: "CHAT-07"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::test_fixture_scenario[12-two-launches-budget-exhausted]"
        status: pass
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::test_fixture_scenario[13-contradictory-launch-and-recall]"
        status: pass
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::test_fixture_scenario[14-injection-style-message]"
        status: pass
    human_judgment: false
  - id: D3
    description: "Transparency: every executed action's drone id appears in the reply message; a rejected drone named in the message is never described as if it succeeded"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::TestTransparency::test_executed_and_failed_drones_named_correctly (parametrised)"
        status: pass
    human_judgment: false
  - id: D4
    description: "OPENROUTER_API_KEY never reaches a captured log record or a response body"
    requirement: "CHAT-07"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::TestSecretHygiene::test_api_key_never_logged_or_returned"
        status: pass
    human_judgment: false
  - id: D5
    description: "One structured INFO log line per completed chat turn, carrying elapsed time, token counts, executed/failed counts, reason keys, and mock-mode flag, using percent-style formatting"
    requirement: "CHAT-07"
    verification:
      - kind: unit
        ref: "backend/tests/chat/test_evals.py::TestTurnLogging::test_one_record_per_turn_carries_counts_and_mock_mode"
        status: pass
      - kind: other
        ref: "python -c \"import inspect, app.chat.router as r; assert inspect.getsource(r).count('logger.info') == 1\""
        status: pass
    human_judgment: false

# Metrics
duration: 45min
completed: 2026-08-13
status: complete
---

# Phase 2 Plan 4: Reference Evaluation Dataset and Chat Turn Logging Summary

**Fourteen-scenario fixture-driven eval harness replaying canned LLM completions through the real `/api/chat` endpoint offline, plus one structured `logger.info` line per completed chat turn in `app/chat/router.py`.**

## Performance

- **Duration:** 45 min
- **Completed:** 2026-08-13
- **Tasks:** 2
- **Files modified:** 17 (15 created, 2 modified — `README.md` counted with the fixture files)

## Accomplishments

- Fourteen JSON fixture files (`backend/tests/chat/fixtures/*.json`), each pairing a raw LLM completion string with the expected HTTP status, executed actions, error substrings, and mission/chat row + budget deltas — covering explicit launch/recall, roster add/remove-with-active-mission, a read-only question, a hallucinated drone, invalid launch arguments, an over-budget launch, a recall with no active mission, a non-JSON completion, a schema-violating completion, sequential budget exhaustion across two launches, a contradictory launch-then-recall in one reply, and an injection-style message.
- `backend/tests/chat/test_evals.py`: a glob-discovered `FIXTURES` list, `test_fixtures_directory_is_populated`, the parametrised `test_fixture_scenario` (asserts status, executed-action sets, error substrings with no traceback markers, and the three row/budget deltas), `test_no_action_is_silently_dropped` (executed + errors == proposed, skipping the two malformed-completion fixtures), `TestTransparency` (every executed drone id named in the reply message; a rejected drone named in the message must also appear in an error string), `TestSecretHygiene` (the API key sentinel appears in neither captured logs nor the response body), and `TestTurnLogging` (exactly one structured record per turn, carrying the executed/failed counts and mock-mode flag).
- `backend/app/chat/router.py`: a module-level `logger`, an `_extract_reason` helper that pulls the trailing `reason` key off a formatted error string, and one `logger.info` call — percent-style, never an f-string — emitted just before the handler's return, carrying elapsed milliseconds, prompt/completion token counts (`None`, since `generate_reply`'s signature is unchanged this plan), executed/failed action counts, the list of extracted reason keys, and `llm.mock_mode_enabled()`.

## Task Commits

1. **Task 1: Reference dataset and the replay harness that is this phase's CI gate** - `520a6e2` (test)
2. **Task 2: Adversarial turns, transparent narration, secret hygiene, and the per-turn log line** - `58cfcce` (feat)

## Files Created/Modified

- `backend/tests/chat/fixtures/README.md` - Fixture schema documentation and the "only from real observed failures" governance rule
- `backend/tests/chat/fixtures/01-explicit-launch.json` through `14-injection-style-message.json` - The fourteen canned-completion scenarios
- `backend/tests/chat/test_evals.py` - Discovery, harness (`test_fixture_scenario`, `test_no_action_is_silently_dropped`), `TestTransparency`, `TestSecretHygiene`, `TestTurnLogging`
- `backend/app/chat/router.py` - Module logger, `_extract_reason`, elapsed-time measurement around `generate_reply`, and the single `logger.info` call

## Decisions Made

- Compared executed actions as `(drone_id, action)` sets rather than full mission dicts, so fixtures don't need to restate `zone`/`distance_km` for comparison purposes.
- Added two optional `expect` fields (`final_mission_status`, `final_active_mission_count`) beyond the plan's base schema, used only by fixtures 13 and 14, to pin the exact post-turn database state the plan asked for ("assert the exact mission status and the exact active-mission count") without adding bespoke test functions per fixture.
- Router imports the `llm` submodule itself (`from . import llm`) in addition to the existing `from .llm import ...` names, so monkeypatching `llm.mock_mode_enabled` in tests is visible both to `generate_reply`'s internal call and to the router's own log-line call — a plain `from .llm import mock_mode_enabled` would have bound a stale reference at import time.
- `_setup_scenario`/test helpers set a placeholder `OPENROUTER_API_KEY` via `monkeypatch.setenv` before forcing the real (non-mock) reply path, since `generate_reply` raises `LLMError` before ever reaching the (already-stubbed) `litellm.acompletion` call if no key is present.

## Deviations from Plan

None - plan executed exactly as written. The two `expect` schema additions above extend the documented fixture schema (README updated accordingly) rather than deviating from the plan's action items; they were needed to literally satisfy task 2's stated fixture-13 assertion ("assert the exact mission status and the exact active-mission count... so a future change in execution order fails the test instead of passing silently") within the generic harness.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. This plan makes no network calls; `LLM_MOCK=true` / monkeypatched `litellm.acompletion` throughout.

## Next Phase Readiness

- Phase 2 (AI Flight Director Chat) is now fully covered by its CI gate: `LLM_MOCK=true uv run --extra dev pytest tests/chat/test_evals.py -v` runs all fourteen scenarios plus `TestTransparency`/`TestSecretHygiene`/`TestTurnLogging` offline in under 3 seconds.
- Full backend suite: 295 passed, 4 skipped (the two malformed-completion fixtures' skip in `test_no_action_is_silently_dropped` and `TestTransparency`), 3 deselected (the gated live smoke suite), 94% coverage, `app/chat/router.py` at 100%.
- `ruff check app/ tests/` clean.
- No blockers for the next phase.

## Self-Check: PASSED

- All key files (`fixtures/README.md`, all 14 fixture JSON files, `test_evals.py`, `app/chat/router.py`) verified present on disk.
- Both commits (`520a6e2`, `58cfcce`) verified present via `git log --oneline --all --grep="02-04"`.
- Re-ran plan `<verification>`: `tests/chat/test_evals.py` + `tests/chat` → 79 passed, 4 skipped, 3 deselected; `ruff check app/ tests/` → clean.

---
*Phase: 02-ai-flight-director-chat*
*Completed: 2026-08-13*
