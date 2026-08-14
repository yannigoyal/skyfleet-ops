---
status: resolved
trigger: "Mock chat mode (LLM_MOCK=true) dispatches the wrong drone: mock_reply() in backend/app/chat/llm.py only keyword-matches \"launch\"/\"recall\" and always substitutes idle[0]/active[0] instead of the drone_id the user actually named in their message. Fix so mock mode extracts and uses the requested drone_id when present in the message, falling back to current behavior only if no drone_id is recognized."
created: 2026-08-14
updated: 2026-08-14
---

## Symptoms

expected: When the operator's chat message names a specific drone (e.g., "launch FALCON-03 to Riverside"), the dispatched/recalled mission's `drone_id` in the response matches the drone the operator named.
actual: The dispatched drone does not match the requested one. User reported: requested FALCON-03, response dispatched FALCON-02; requested FALCON-05, response dispatched FALCON-03.
errors: None — no exception, no error message; the request succeeds and the budget updates, just for the wrong drone.
timeline: Discovered during manual UAT-style testing of the AI chat dispatch flow ("Test 8"), LLM_MOCK=true.
reproduction: With LLM_MOCK=true, send a chat message containing "launch" plus a specific drone id that is NOT the roster's first idle drone (or "recall" plus a drone id that is NOT the first active mission). The response substitutes idle[0]/active[0] instead.

## Prior investigation (already completed by orchestrator before this session — treat as established evidence, not a hypothesis to re-verify from scratch)

Root cause already located via direct code read:

- File: `backend/app/chat/llm.py`, function `mock_reply`, lines 149-186.
- `mock_reply` does pure substring keyword matching (`"launch" in text`, `"recall" in text`) and never extracts/parses the drone id token from the user's message.
- Launch branch (lines 173-181): always returns `MissionAction(drone_id=idle[0], action="launch", ...)` — `idle[0]` is the first roster drone not in `active`, in roster order. The drone the user actually typed is ignored.
- Recall branch (line 167 area): always returns `active[0]["drone_id"]` — the first entry in `fleet_context["active_missions"]`, regardless of which drone the user named.
- Confirmed NOT a frontend bug: `frontend/src/lib/useChat.ts`, `frontend/src/components/chat/ChatMessage.tsx`, and `ConfirmationCard.tsx` all render `entry.drone_id` straight from the backend response with no index remapping.
- Confirmed NOT caught by existing tests: `backend/tests/chat/fixtures/*.json` bypass `mock_reply` entirely — they stub `completion` directly with `mock_mode_enabled` forced `False`, so nothing pins `mock_reply`'s own drone-selection logic to the drone named in the input message.
- Real (non-mock) LLM path (lines 204-239) has no such hardcoded fallback — the model itself must read the drone id out of the message text via the structured-output schema.

## Current Focus

hypothesis: Confirmed (not a hypothesis to test — already root-caused by direct code inspection). `mock_reply()` needs to extract a drone_id from `user_message` (matching against the roster's known drone ids, e.g. `FALCON-\d\d` pattern or exact roster-id substring match) and use it when present, falling back to the current idle[0]/active[0] behavior only when no drone id is recognized in the message.
test: Add a test that sends "Launch FALCON-05 to Riverside" through `mock_reply` with a fleet_context where FALCON-05 is idle but not first in roster order, and assert the response's `missions[0].drone_id == "FALCON-05"`. Also add a recall-path equivalent test and a fallback test (no drone id in message) confirming the existing idle[0]/active[0] behavior is preserved.
expecting: The fix should extract the requested drone id via a case-insensitive scan of `user_message` against the roster's known drone ids (from `fleet_context["roster"]` or `fleet_context["active_missions"]`), preferring an exact match over the keyword-only fallback.
next_action: DONE. Human verification returned "confirmed fixed" (4/4 independent checks passed against a live backend with LLM_MOCK=true, via curl rather than the Playwright path). Session archived to .planning/debug/resolved/, prevention entry written to .planning/debug/knowledge-base.md, fix and docs committed.
bug_class: Bohrbug — fully deterministic. `mock_reply` is a pure function of (fleet_context, user_message); the same inputs always select the same wrong drone. No timing, concurrency, or environment sensitivity. Route = deterministic reproduction + direct code read (already done); SBFL skipped (no failing test existed to build a spectrum from — the gap IS the bug's second cause).
reasoning_checkpoint:
  hypothesis: "`mock_reply()` selects the dispatched drone positionally (idle[0] for launch, active[0] for recall) and never reads any drone id out of `user_message`, so any message naming a drone other than the first idle / first active one dispatches the wrong drone."
  confirming_evidence:
    - "Direct read of backend/app/chat/llm.py:157-186 (live code, re-verified this session): `text = user_message.lower()` is used ONLY for the substring tests `\"recall\" in text` and `\"launch\" in text`. No other read of `user_message` exists in the function body."
    - "Launch branch line 181 hardcodes `drone_id=idle[0]`; recall branch line 167 hardcodes `active[0][\"drone_id\"]`. Neither expression references `user_message` or `text`."
    - "`idle` is built at line 175 in roster order (`for drone in roster if ... not in busy`), which matches the reported symptom exactly: FALCON-03 requested -> FALCON-02 dispatched is the first idle roster drone when FALCON-01 is already busy."
    - "backend/app/chat/router.py:129 calls generate_reply, which at llm.py:213-214 short-circuits to mock_reply whenever LLM_MOCK=true — so under the reported LLM_MOCK=true conditions this function IS the whole decision path."
    - "Router lines 146-151 execute reply.missions verbatim through missions_service, so mock_reply's drone choice is dispatched as-is with no downstream correction."
  falsification_test: "Call mock_reply directly with a roster where FALCON-05 is idle but NOT first, and user_message='Launch FALCON-05 to Riverside'. If the returned missions[0].drone_id == 'FALCON-05', the hypothesis is wrong. Observed: returns the first idle drone instead."
  fix_rationale: "Extract the operator-named drone id from user_message by matching against the drone ids already present in fleet_context (roster + active_missions), and use it as the dispatch target when found. This addresses the root cause — the absence of any read of the message's drone id — rather than the symptom (a particular wrong id). The positional idle[0]/active[0] selection is retained strictly as the no-drone-named fallback, which is the behavior the E2E spec depends on."
  blind_spots:
    - "Ambiguous prefix ids (a roster containing both FALCON-1 and FALCON-10) — mitigated by matching longest id first; covered by a regression test."
    - "Off-roster ids the operator invents (e.g. 'launch FALCON-99') still fall back to idle[0]. Deliberately out of scope: matching arbitrary hyphen-digit tokens would misfire on zone names like 'Riverside-5'. Documented in the docstring as a known mock limitation."
    - "Messages naming two drones ('move FALCON-02 and FALCON-05') — first match wins; the mock is a single-action stand-in, not a parser."
  candidate_causes:
    - "code: mock_reply ignores user_message when selecting the drone (CONFIRMED — this is the defect)"
    - "code/test-gap: no test binds mock_reply's drone selection to the drone named in the input; backend/tests/chat/test_llm.py::TestMockMode asserts only isinstance + that acompletion was untouched, and tests/chat/test_router.py:98 monkeypatches mock_reply away entirely, so the real function's selection logic is unpinned (CONFIRMED — second contributing cause)"
    - "config: LLM_MOCK=true routes the request to mock_reply at all (CONFIRMED as a necessary precondition — the real LLM path at llm.py:204-239 has no positional fallback and is unaffected)"
    - "environment: process env / container differences — ELIMINATED, mock_reply is pure and env-independent apart from the LLM_MOCK gate"
    - "data: roster ordering from the DB — ELIMINATED as a cause; roster order only determines WHICH wrong drone is picked, not that a wrong drone is picked. Reordering the roster cannot fix it."
  and_gate: "yes — two conditions must hold simultaneously for the operator to see this. (1) LLM_MOCK=true routes to mock_reply (config), AND (2) mock_reply selects positionally (code). Neither alone is sufficient: with LLM_MOCK unset the real model reads the drone id from the message text, and the positional code is unreachable. A third, separate cause explains why it survived to UAT: the test suite never exercised mock_reply's own selection logic (test-gap). The fix must therefore land in BOTH the function and the test suite — patching only the function would leave the gate that missed it still open."
tdd_checkpoint:
  test_file: "backend/tests/chat/test_llm.py"
  status: "pending — writing red test next"

## Evidence

- timestamp: 2026-08-14 (pre-session)
  finding: "`mock_reply` (backend/app/chat/llm.py:149-186) unconditionally substitutes idle[0]/active[0] for launch/recall, ignoring any drone id in the user's message. Confirmed via direct read of llm.py, useChat.ts, ChatMessage.tsx, ConfirmationCard.tsx, and backend/tests/chat/fixtures/README.md."

- timestamp: 2026-08-14 (this session)
  checked: "Knowledge base lookup — .planning/debug/knowledge-base.md"
  found: "File does not exist; only two unrelated resolved-adjacent sessions in .planning/debug/ (e2e-harness-port-conflict, start-script-browser-race). No prior pattern to match against."
  implication: "No known-pattern shortcut available. This session should create the knowledge base on archive."

- timestamp: 2026-08-14 (this session)
  checked: "Re-verified the prior root cause against live code at backend/app/chat/llm.py:149-186"
  found: "Live code matches the prior finding exactly, line for line. Additionally traced the consumption path: llm.py:213-214 routes to mock_reply whenever LLM_MOCK=true, and chat/router.py:146-151 executes reply.missions verbatim through missions_service with no downstream drone correction."
  implication: "mock_reply is the sole decision point for the reported symptom. Confirmed, not merely inherited."

- timestamp: 2026-08-14 (this session)
  checked: "Blast radius of changing mock_reply's contract — grepped every LLM_MOCK / mock_reply consumer"
  found: "tests/specs/chat.spec.ts sends only keyword-only prompts ('Launch a drone', 'Recall the drone'), reads the drone id back off the confirmation card rather than hardcoding it, and asserts the '[mock]' message prefix. tests/chat/test_router.py:98 monkeypatches mock_reply away. tests/chat/test_evals.py forces mock_mode_enabled False."
  implication: "The positional default must be preserved as the no-drone-named fallback or the E2E spec breaks; nothing depends on positional selection when a drone IS named. Fix is safe, and the fallback needs its own regression tests."

- timestamp: 2026-08-14 (this session)
  checked: "chat/router.py error handling for an ineligible named drone (_execute_mission, lines 50-83)"
  found: "MissionError is caught per action and surfaced in the response's `errors` array ('Could not launch X: drone_already_en_route.'); only successful actions are echoed in `missions`."
  implication: "Passing a named-but-ineligible drone through is safe and produces an honest operator-visible error — strictly better than silently substituting an eligible drone, which is the same wrong-drone failure class."

- timestamp: 2026-08-14 (this session)
  checked: "RED baseline — ran the new TestMockReplyDroneSelection against unfixed code"
  found: "5 failed / 5 passed. Failures were exactly the named-drone assertions (e.g. 'assert FALCON-01 == FALCON-02'); the 5 passes were the fallback-preservation tests, proving the fallback is genuinely the current behavior and not an artifact of the fix."
  implication: "The bug is deterministically reproducible in a test, and the tests discriminate the defect from the behavior that must be preserved."

- timestamp: 2026-08-14 (this session)
  checked: "Mutation testing at the fix site (4 mutants, automated apply/run/restore)"
  found: "4/4 killed — M1 drop longest-first ordering, M2 drop case-insensitivity, M3 ignore named drone on launch, M4 ignore named drone on recall. Zero survivors; source restored and verified byte-identical."
  implication: "The regression tests genuinely constrain the new logic; they are not vacuous assertions that would pass against a broken implementation."

- timestamp: 2026-08-14 (this session)
  checked: "Revert test — git stash of backend/app/chat/llm.py only, tests left in place"
  found: "8 tests failed against HEAD's unfixed llm.py, including both new API-level tests through POST /api/chat. Fix restored; diff against a pre-revert copy confirmed byte-identical."
  implication: "The fix, and not some incidental environmental change, is what makes the tests pass."

- timestamp: 2026-08-14 (this session)
  checked: "HUMAN VERIFICATION — operator ran the backend locally with LLM_MOCK=true (deliberately NOT the Playwright/Docker path, so the fix is confirmed independently of the harness that self-verification used) and hit POST /api/chat directly via curl."
  found: >
    4/4 checks passed.
    (1) "Launch FALCON-07 to Riverside, 4.2 km" -> dispatched FALCON-07, not FALCON-01
    (the pre-fix positional default) — the exact reported symptom, gone.
    (2) "Recall FALCON-07" -> recalled FALCON-07.
    (3) With FALCON-09 and FALCON-03 both en route, "Recall FALCON-03" -> recalled
    FALCON-03 specifically, not active[0] (FALCON-09) — confirms the recall branch
    reads the named drone rather than mission ordering.
    (4) "Launch a drone to the north side" (no drone named) -> fell back to the first
    idle drone FALCON-01, so the keyword-only fallback tests/specs/chat.spec.ts depends
    on is intact.
  implication: "Fix confirmed end to end in the operator's own environment, through a different entry path than any self-verification signal used. Original symptom resolved and the preserved fallback behavior independently exercised. Session moves to resolved."

## Eliminated

- hypothesis: "Frontend index-based lookup bug (stale state or array index mismatch in chat rendering)"
  reason: "ChatMessage.tsx uses array index only for React `key`, never for data selection; ConfirmationCard.tsx renders `entry.drone_id` directly from the response object passed through unmodified from useChat.ts."

## Resolution

root_cause: >
  Two contributing causes (AND-gate fired).
  (1) CODE — `mock_reply()` in backend/app/chat/llm.py selected the dispatch target
  positionally and never read a drone id out of `user_message`: the launch branch
  hardcoded `idle[0]` (first roster drone not en route, in roster order) and the
  recall branch hardcoded `active[0]["drone_id"]`. `user_message` was consumed only
  as a lowercased haystack for the substring tests `"launch" in text` / `"recall" in
  text`. Under LLM_MOCK=true this function is the entire decision path
  (llm.py:213-214), and chat/router.py:146-151 executes its output verbatim, so the
  wrong drone launched with no error — matching the report exactly (asked FALCON-03,
  got FALCON-02 = first idle when FALCON-01 was busy).
  (2) TEST-GAP — nothing pinned that selection to the named drone. The only mock-mode
  unit test (test_llm.py::TestMockMode) asserted just `isinstance` + that acompletion
  was untouched; tests/chat/test_router.py:98 monkeypatched `mock_reply` away
  entirely; and the eval fixtures force `mock_mode_enabled` to False, bypassing it.
  The real (non-mock) LLM path was never affected — the model reads the drone id from
  the message text via the structured-output schema.
fix: >
  Added `_named_drone_id(fleet_context, text)` to backend/app/chat/llm.py: it matches
  the message against the drone ids the fleet already knows (roster + active_missions),
  case-insensitively, longest id first so "FALCON-10" is never read as the "FALCON-1"
  that prefixes it. `mock_reply` now dispatches that named drone for both launch and
  recall, falling back to the previous positional default ONLY when the message names
  no known drone — preserving the keyword-only behavior tests/specs/chat.spec.ts
  depends on ("Launch a drone" / "Recall the drone", the "[mock]" message prefix, zone
  Riverside at 4.0 km). A named-but-ineligible drone (already en route / not flying) is
  passed through deliberately so the service layer returns a real error the operator can
  read, instead of silently substituting a different drone — the same failure class.
  Scope note: ids the fleet has never heard of (e.g. "FALCON-99") still fall back to the
  positional default; matching bare hyphen-digit tokens would misfire on zone names like
  "Riverside-5", and the roster puts no format constraint on drone ids. Documented in the
  function docstring as a known mock limitation.
verification:
  oracle_type: specified — the expected drone id is stated by the operator's own message; the assertion is equality against that id, not a crash check.
  signal_1_regression_test_red_then_green: PASS — 6 unit + 2 API tests failed against the unfixed code, all pass after the fix.
  signal_2_revert_restores_bug: PASS — `git stash push` of llm.py alone (tests untouched) reproduced 8 failures including both API-level tests; fix restored and byte-compared to confirm integrity.
  signal_3_diff_is_not_deletion_only: PASS — 57 lines changed in llm.py, additive (new helper + fallback logic); no guard, validation, or assertion removed.
  signal_4_mutation_at_fix_site: PASS — 4/4 mutants killed. M1 drop longest-first ordering, M2 drop case-insensitive match, M3 ignore named drone on launch, M4 ignore named drone on recall. Zero survivors.
  signal_5_no_collateral_regression: PASS — full backend suite 314 passed / 6 skipped / 3 deselected. `ruff check` clean on all three changed files (the one repo-wide lint error is in the untracked, unrelated backend/app/demo/mission_demo.py).
  coverage: app/chat/llm.py 98% (the 2 uncovered lines, 130/132, are pre-existing null-coercion branches in parse_reply, untouched by this fix).
  boundary_neighbors_tested: FALCON-1 vs FALCON-10 prefix ambiguity; lowercase input returning canonical roster casing; named drone already en route; named drone with nothing en route; empty roster; drone named with no action keyword; both no-drone-named fallbacks; "[mock]" prefix preserved on all three reply shapes.
  not_self_verifiable: the Playwright E2E suite (tests/specs/chat.spec.ts) needs Docker + the Playwright container, unavailable here. Its contract is pinned by unit tests, but a live run through the browser UI is the human-verify step.
  guardrail_verdict: accepted
  human_verified: >
    CONFIRMED 2026-08-14. Operator ran the backend locally with LLM_MOCK=true and hit
    POST /api/chat via curl — a different entry path from every self-verification signal.
    Named-drone launch (FALCON-07), named-drone recall (FALCON-07), named recall with a
    competing earlier active mission (FALCON-03 chosen over active[0] FALCON-09), and the
    no-drone-named fallback (FALCON-01) all behaved correctly. The `not_self_verifiable`
    gap above is closed by checks 1-4; the Playwright suite itself remains unrun here.
files_changed:
  - backend/app/chat/llm.py — added `_named_drone_id`; `mock_reply` now dispatches the named drone, positional selection demoted to fallback; docstring rewritten to state the new contract and its limits.
  - backend/tests/chat/test_llm.py — added `TestMockReplyDroneSelection` (12 tests) plus a `_fleet_context` builder.
  - backend/tests/chat/test_router.py — added 2 API-level regression tests reproducing the reported UAT flow end to end through POST /api/chat.
