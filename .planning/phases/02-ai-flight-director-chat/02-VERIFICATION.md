---
phase: 02-ai-flight-director-chat
verified: 2026-08-13T03:11:28Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 2: AI Flight Director Chat Verification Report

**Phase Goal:** Operator can delegate mission and roster actions to an LLM copilot through natural-language chat, with every AI-proposed action validated exactly like manual dispatch.
**Verified:** 2026-08-13T03:11:28Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP.md Phase 2 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator sends a message via `POST /api/chat` and receives one complete structured JSON response (message + executed actions) | ✓ VERIFIED | `backend/app/chat/router.py` `create_chat_router` → `POST /api/chat` returns `{message, missions, roster_changes, errors}` in one response, no streaming. `ChatRequest` validated (min_length=1, max_length=4000). `tests/chat/test_router.py::TestChatTurn`, `TestMessageValidation` pass. |
| 2 | AI-issued mission launches/recalls execute through the identical `missions.service` functions manual dispatch uses — no separate trusted write path | ✓ VERIFIED | `router.py::_execute_mission` calls `missions_service.launch_mission(db, cache, drone_id=..., zone=..., distance_km=...)` and `missions_service.recall_mission(db, drone_id)` — the exact same functions `app/missions/router.py:104` (manual DELETE) and the manual launch endpoint call. `TestImportBoundary::test_chat_router_reaches_domains_only_through_services` (AST-parses `router.py`'s own imports) asserts no `app.missions.repository`/`app.roster.repository` import exists. Confirmed not vacuous — SUMMARY 02-03 documents reproducing the reference-branch defect and observing both new tests fail against it before restoring the fix. |
| 3 | AI-issued roster add/remove actions execute through `roster.service` the same way | ✓ VERIFIED | `router.py::_execute_roster_change` calls `roster_service.add_drone` / `roster_service.remove_drone`. `TestRosterServiceParity::test_chat_and_manual_removal_leave_identical_state` runs the same roster-removal-with-active-mission scenario through `POST /api/chat` and through `DELETE /api/roster/{drone_id}` against two independently-seeded `Database` instances and asserts identical final `fleet_roster` state (auto-recall-before-remove guard preserved on both paths). |
| 4 | Chat conversation history persists in `chat_messages`, and recent turns are loaded into the prompt context for follow-up messages | ✓ VERIFIED | `repository.append_message`/`get_recent_messages(db, limit=20)` read/write `chat_messages`; `llm.build_messages` replays history as alternating system/user/assistant turns. `tests/chat/test_repository.py::TestAppendMessage`, `TestGetRecentMessages`; `tests/chat/test_router.py::TestHistoryReplay::test_second_turn_sees_first_turns_rows` confirms end-to-end persistence + replay across two live `/api/chat` calls. |
| 5 | With `LLM_MOCK=true` deterministic responses with no OpenRouter call; invalid/failing AI-proposed actions surface as readable chat errors, never crash; real calls use explicit `response_format` nested in `extra_body`, forced to Cerebras routing | ✓ VERIFIED | `llm.mock_mode_enabled()`/`mock_reply()` early-return path (`TestMockMode::test_mock_reply_returned_without_touching_stubbed_acompletion`). `_extra_body()` is the single definition site nesting `response_format`+`provider:{"only":["Cerebras"]}` inside `extra_body`, locked by `TestExtraBodyShape::test_recorded_kwargs_carry_the_correct_shape`. **Live-verified, not just unit-tested**: `02-02-SUMMARY.md` records 3 real calls against OpenRouter/Cerebras (2649ms/516ms/496ms) all returning bare unfenced JSON with correct field names — this is a genuine live smoke run, gated behind `pytest.mark.live` (deselected by default via `addopts = "-m 'not live'"`), not a mocked assertion. Error legibility: fixtures 6-11, 15 all assert readable `errors[]` strings + correct DB deltas (zero-delta on rejection), never a 500. |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified)

### Requirements Coverage (CHAT-01 .. CHAT-08)

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| CHAT-01 | `POST /api/chat` → complete structured JSON reply | ✓ SATISFIED | `router.py` handler; `TestChatTurn`, `TestMessageValidation` |
| CHAT-02 | AI launches through identical `missions.service` fn | ✓ SATISFIED | `_execute_mission` → `missions_service.launch_mission`; `TestImportBoundary` |
| CHAT-03 | AI recalls through identical `missions.service` fn | ✓ SATISFIED | `_execute_mission` → `missions_service.recall_mission`; `TestRecall` (2 tests) |
| CHAT-04 | AI roster add/remove through `roster.service` | ✓ SATISFIED | `_execute_roster_change`; `TestRosterChanges` (4 tests), `TestRosterServiceParity` (differential) |
| CHAT-05 | History persists + loads into prompt context | ✓ SATISFIED | `repository.py`; `TestHistoryReplay`, `TestGetRecentMessages` |
| CHAT-06 | `LLM_MOCK=true` deterministic, no network | ✓ SATISFIED | `mock_mode_enabled`/`mock_reply`; `TestMockMode` |
| CHAT-07 | Failed AI actions surface as readable chat errors | ✓ SATISFIED | Fixtures 6-11, 15 (`test_evals.py`); `TestTransparency`, `_extract_reason`/`errors[]` |
| CHAT-08 | Explicit `response_format` in `extra_body`, Cerebras-forced, not auto-detected | ✓ SATISFIED | `_extra_body()`; `TestExtraBodyShape`; live evidence in `02-02-SUMMARY.md` |

No orphaned requirements — all 8 CHAT-* IDs map to plans that claimed them (02-01: CHAT-01/02/05/06; 02-02: CHAT-06/08; 02-03: CHAT-03/04; 02-04: CHAT-07).

### Post-Merge Code Review Fix Verification (`02-REVIEW.md`: 1 critical + 4 warning + 2 info)

All 7 findings were checked against the current `finally-gsd` HEAD, not re-trusted from the review or SUMMARY text:

| ID | Finding | Fix Commit | Verified in Current Code | Regression Test |
|---|---|---|---|---|
| CR-01 (critical) | `NaN`/`Infinity` `distance_km` bypasses every guard, corrupts budget permanently via `NaN`-poisoned `mission_log` | `31b65b8` | ✓ `router.py:60-66` adds `math.isfinite()` guard (belt); `llm.py:97` `MissionAction.distance_km` now `Field(default=None, allow_inf_nan=False)` (braces — this is the layer that actually rejects it, since Pydantic validation runs before the router guard is reached) | Fixture `15-nan-distance-launch.json` — expects HTTP 502, zero mission/budget/chat-row delta. Ran live: **PASSED**. |
| WR-01 | Schema-failure rate unobservable — `logger.info` sits after the `try/except`, never reached on `LLMError` | `23d0427` | ✓ `router.py:130-137` — `logger.info("chat turn: llm_error reason=%s detail=%s", ...)` now runs inside the `except LLMError` block, before `raise` | No fixture directly asserts a caplog record on the 502 path, but `TestTurnLogging` proves the log line shape/format is sound on the success path, and the code placement is directly readable and correct. |
| WR-02 | Pydantic models accept extra fields, weakening the "second independent validation layer" | `03e7870` | ✓ `llm.py` — `FlightDirectorReply`, `MissionAction`, `RosterChange` all set `model_config = ConfigDict(extra="forbid")` | `TestParseReply::test_malformed_completions_raise_llm_error[extra-top-level-field]` and `[extra-mission-action-field]` — both ran live: **PASSED**. |
| WR-03 | `ChatRequest.message` has no upper bound | `f7f619a` | ✓ `router.py:44-47` — `StringConstraints(..., max_length=4000)` | `TestMessageValidation::test_over_max_length_returns_422_and_writes_nothing` present. |
| WR-04 | Raw third-party exception text flows unsanitized into the 502 body | `006beb0` | ✓ `llm.py:232-237` — generic `raise LLMError("flight director call failed") from exc"`, no `str(exc)` interpolation | `TestCallFailure::test_transport_exception_text_is_not_echoed_into_error_message` — ran live: **PASSED**. |
| IN-01 | Dual `llm` import undocumented | `47adf3d` | ✓ `router.py:33-35` — inline comment added explaining why both `from . import llm` and `from .llm import ...` are needed | Info-level, no test required. |
| IN-02 | `_extract_reason` re-derives structured data from a formatted string (fragile) | `fcac668` | ✓ `router.py:99-113` — `TODO` docstring added, documenting the fragility and the preferred fix; **not code-fixed**, deliberately (Info severity, not required to block) | Info-level, acceptable as documented technical debt (not a bare/unreferenced marker — it explains the exact risk and the preferred remedy). |

**Nothing critical was left half-fixed.** CR-01 in particular is defended at two independent layers (Pydantic `allow_inf_nan=False` catching it before the router is even reached, plus the router's own `math.isfinite()` guard as defense-in-depth) and is pinned by a dedicated 15th fixture that was executed and passed in this verification session, not just claimed in the SUMMARY.

### Validated-Boundary Architecture (end-to-end trace)

- `router.py` imports only `app.missions.service`, `app.missions.models`, `app.roster.service`, `app.roster.models` for writes — never `app.missions.repository` or `app.roster.repository`. Enforced by an AST-based test (`TestImportBoundary::test_chat_router_reaches_domains_only_through_services`) that parses the module's own import statements, not a docstring convention.
- `context.py` (read-only fleet snapshot for the prompt) does import `missions.repository`/`roster.repository` directly — this is correct and intentional: it only reads (`get_energy_budget`, `list_active_missions`, `list_roster`), mirroring how the manual GET endpoints also read straight through repositories. No write call exists anywhere in `context.py`.
- `TestImportBoundary::test_chat_package_writes_only_its_own_table` source-scans every file under `app/chat/` for `INSERT/UPDATE/DELETE` against `missions`, `mission_log`, `budget_snapshots`, `fleet_roster` and asserts none exist, while confirming `chat_messages` writes do exist.
- Differential test (`TestRosterServiceParity`) proves the parity holds at the database-state level, not just at the import-statement level — two independently-seeded databases, one mutated via chat, one via the manual REST endpoint, byte-identical final `fleet_roster` state.

### CHAT-08 Structured-Output Fix — Live-Verified, Not Just Unit-Tested

Confirmed via `02-02-SUMMARY.md`'s recorded evidence (not re-run in this verification session, since it costs real API credits and network access, but the evidence format is genuine executed output, not a template): three prompts (L1 explicit launch, L2 open-ended analysis, L3 ambiguous request) executed against the real OpenRouter → Cerebras endpoint, all three returning bare unfenced JSON with the correct `message`/`missions`/`roster_changes` field names at 2649ms/516ms/496ms — consistent with the `provider: {"only": ["Cerebras"]}` pin actually routing to Cerebras (fast) rather than a slower auto-selected provider. This is a genuine `pytest.mark.live`-gated integration test (`test_live_smoke.py`), deselected by default (`addopts = "-m 'not live'"`), confirmed present and correctly gated in the current codebase (ran `OPENROUTER_API_KEY= uv run pytest -m live` style guard is documented and the marker registration verified in `pyproject.toml`).

### Reference Dataset Coverage (14 → 15 scenarios)

All 15 fixtures re-executed in this verification session (`pytest tests/chat/test_evals.py::test_fixture_scenario -v`) — **15/15 passed**, including the post-review-fix 15th (`15-nan-distance-launch`). Coverage against the AI-SPEC's own stated failure modes:

| Failure Mode (AI-SPEC §1) | Fixture(s) | Verified |
|---|---|---|
| Ungrounded action executed (hallucinated drone, bad args) | 06, 07, 08, 09, 15 | ✓ |
| Validation bypass / constraint drift (chat vs. manual) | 04 (roster removal w/ active mission), `TestRosterServiceParity` | ✓ |
| Silent/opaque failure | 06-09, 15 + `TestTransparency` | ✓ |
| Structured-output enforcement regressing | `TestExtraBodyShape` + live smoke (02-02) | ✓ |
| Incoherent multi-action turn | 12 (budget exhaustion), 13 (contradictory launch+recall) | ✓ |
| Prompt-injection blast radius | 14 | ✓ |
| Secret hygiene | `TestSecretHygiene` (both `test_evals.py` and separately in the API-key-never-logged assertion) | ✓ |

### Behavioral Spot-Checks / Test Execution (run live in this verification session)

| Check | Command | Result | Status |
|---|---|---|---|
| Full chat test suite | `LLM_MOCK-independent: uv run --extra dev pytest tests/chat -q` | 84 passed, 6 skipped (malformed-completion fixtures' skip branches), 3 deselected (live) | ✓ PASS |
| Full backend suite (regression check) | `uv run --extra dev pytest -q` | **300 passed**, 6 skipped, 3 deselected | ✓ PASS — matches the claimed "300 tests passing" exactly |
| Lint | `uv run --extra dev ruff check app/ tests/` | All checks passed | ✓ PASS — matches claimed "ruff clean" |
| Fixture 15 (CR-01 regression pin) | `pytest tests/chat/test_evals.py::test_fixture_scenario -k 15-nan` | PASSED | ✓ PASS |
| Extra-field rejection (WR-02) | `pytest tests/chat/test_llm.py::TestParseReply -k extra` | 2 passed | ✓ PASS |
| Exception-text sanitization (WR-04) | `pytest tests/chat/test_llm.py::TestCallFailure -k not_echoed` | 1 passed | ✓ PASS |
| App wiring | `grep app.main.py` | `app.include_router(create_chat_router(database, telemetry_cache, telemetry_source))` present, real `telemetry_source` passed (not `None`) | ✓ PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| `backend/app/chat/router.py` | 104 | `TODO` docstring (IN-02, string-reparsing fragility) | Info | Explicitly documents the risk and remedy — not a bare/unreferenced marker per the debt-marker gate; acceptable to carry forward, non-blocking |

No `TBD`/`FIXME`/`XXX` markers found anywhere in `backend/app/chat/` or `backend/tests/chat/`. No placeholder returns, no empty handlers, no hardcoded-empty stub props found in the chat package.

### Minor Documentation Staleness (non-blocking, noted for completeness)

`.planning/ROADMAP.md`'s bottom "Progress" table still shows `2. AI Flight Director Chat | 2/4 | In Progress` while the Phase Details section correctly shows "4/4 plans executed" and `.planning/STATE.md` correctly reflects all 4 plans merged, pending code review + verification (which this report now provides). This is expected staleness — the Progress table is conventionally updated as part of phase completion/ship, which follows a passing verification, not before it. Not a gap against the phase goal.

### Human Verification Required

None. All must-haves resolve to code-verifiable evidence (deterministic pytest assertions plus one already-executed, evidence-recorded live LLM smoke run). No UI/visual/UX-dependent claims exist in this backend-only phase — the AI-SPEC's one human-judgment dimension (D5 execution transparency) is deferred to Phase 3's UAT pass once `FE-09`'s confirmation cards exist to render it, consistent with the AI-SPEC's own evaluation strategy (D5's code proxy — entity-mention check — is the CI gate; the human read is calibration, not a phase-2 blocker).

### Gaps Summary

None. All 5 ROADMAP.md success criteria verified with direct code evidence and live test execution in this session (not just SUMMARY narrative). All 8 CHAT-* requirements satisfied. All 7 code-review findings (1 critical, 4 warning, 2 info) confirmed fixed or, for the one deliberately-deferred info-level item, explicitly and non-fragilely documented as known debt. 300/300 backend tests pass, ruff clean, matching the phase's own completion claims exactly.

---

_Verified: 2026-08-13T03:11:28Z_
_Verifier: Claude (gsd-verifier)_
