---
phase: 2
slug: ai-flight-director-chat
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.3.0 + pytest-asyncio >=0.24.0 |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `asyncio_mode = "auto"` |
| **Quick run command** | `cd backend && uv run --extra dev pytest tests/chat -v` |
| **Full suite command** | `cd backend && uv run --extra dev pytest -v --cov=app` |
| **Estimated runtime** | ~5 seconds (mirrors current 216-test suite at ~3s; chat adds a handful of unit/integration tests, all mocked/monkeypatched — no network I/O in the automated suite) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run --extra dev pytest tests/chat -v`
- **After every plan wave:** Run `cd backend && uv run --extra dev pytest -v --cov=app`
- **Before `/gsd-verify-work`:** Full suite must be green, plus the live CHAT-08 smoke test executed at least once with a real `OPENROUTER_API_KEY` and its raw JSON output captured as verification evidence
- **Max feedback latency:** ~5 seconds (in-process pytest run, no external services in the automated path)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0/1 | CHAT-01 | T-02-TBD | `POST /api/chat` returns `{message, missions?, roster_changes?}` | integration | `pytest tests/chat/test_router.py::test_returns_structured_response -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0/1 | CHAT-02 | T-02-TBD | Launch action delegates to `missions.service.launch_mission` with matching kwargs | unit | `pytest tests/chat/test_router.py::test_launch_delegates_to_missions_service -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0/1 | CHAT-03 | T-02-TBD | Recall action delegates to `missions.service.recall_mission` | unit | `pytest tests/chat/test_router.py::test_recall_delegates_to_missions_service -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0/1 | CHAT-04 | T-02-TBD | Roster add/remove delegates to `roster.service`, not `roster.repository` (Pitfall 1 regression guard) | unit | `pytest tests/chat/test_router.py::test_roster_change_uses_roster_service -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 0/1 | CHAT-05 | — | Recent `chat_messages` rows load into prompt history, oldest-first | unit | `pytest tests/chat/test_repository.py::test_get_recent_messages_ordering -x` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 0/1 | CHAT-06 | — | `LLM_MOCK=true` never calls `litellm.acompletion` | unit | `pytest tests/chat/test_llm.py::test_mock_mode_skips_network_call -x` | ❌ W0 | ⬜ pending |
| 02-01-07 | 01 | 0/1 | CHAT-07 | T-02-TBD | Invalid `drone_id`/negative `distance_km`/malformed JSON surfaces as chat-response error, not a crash | unit + integration | `pytest tests/chat/test_llm.py::TestParseReply -x` and `tests/chat/test_router.py::test_invalid_action_surfaces_error -x` | ❌ W0 | ⬜ pending |
| 02-01-08 | 01 | 0/1 | CHAT-08 | T-02-TBD | `extra_body` contains nested `response_format` + `provider: {"only": ["Cerebras"]}`; live smoke test parses real Cerebras output | unit + live (manual/gated) | `pytest tests/chat/test_llm.py::test_extra_body_shape -x` (unit) + manual/skippable live smoke script | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs above are placeholders pending the planner's actual wave/task numbering — the planner should reconcile this table's Task ID column against the real PLAN.md task IDs it produces, keeping the Requirement/Test/Command columns intact.*

---

## Wave 0 Requirements

- [ ] `backend/tests/chat/__init__.py`, `conftest.py` — currently empty stub directories (pycache-only); need `db`/`cache`/`stub_completion` fixtures
- [ ] `backend/tests/chat/test_llm.py`, `test_repository.py`, `test_router.py` — none exist yet
- [ ] `litellm` dependency declaration: `uv add "litellm>=1.96.0"` in `backend/pyproject.toml` + `uv sync` (package-legitimacy `checkpoint:human-verify` gate applies — see RESEARCH.md Package Legitimacy Audit)
- [ ] `backend/app/main.py` wiring: add `from app.chat import create_chat_router` and mount it via `app.include_router(...)` — this is the only main.py wiring gap; the roster-router mounting is already correct (verified directly against source, see RESEARCH.md's corrected Wave 0 Gaps note)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live OpenRouter → Cerebras call returns valid structured JSON matching `RESPONSE_SCHEMA` | CHAT-08 | Requires a real `OPENROUTER_API_KEY` network call; a monkeypatched unit test cannot catch a parameter-stripping bug inside LiteLLM's real OpenRouter adapter (the exact failure mode CHAT-08 exists to prevent) | Run the smoke test/script with `LLM_MOCK` unset and a real `OPENROUTER_API_KEY` present; capture the raw JSON response and confirm it parses against `RESPONSE_SCHEMA` with `provider` routed to Cerebras |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
