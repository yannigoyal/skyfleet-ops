---
phase: 04-docker-packaging-test-suites
plan: 04
subsystem: e2e-tests
tags: [playwright, e2e, recharts, sse, llm-mock]

# Dependency graph
requires:
  - phase: 04-03
    provides: Serialized Playwright config (workers 1, fullyParallel false), tests/specs/helpers.ts shared fixtures (getFleet, getRoster, readHeaderRemainingKwh, pickIdleDrone, restoreFleetState)
provides:
  - tests/specs/visualization.spec.ts — TEST-04 scenario 4 (heatmap cells, budget chart, sparklines, structural only per D-03)
  - tests/specs/chat.spec.ts — TEST-04 scenario 5 (mocked flight-director launch/recall via chat)
  - tests/specs/sse-resilience.spec.ts — TEST-04 scenario 6 (telemetry disconnect and unaided reconnect)
  - tests/README.md rewritten to describe the seven implemented specs instead of a planned-only suite
affects: [e2e-test-infra, ship-gate]

# Actuals (#2632)
actuals:
  tokens: 3700
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural DOM/SVG assertions for chart rendering (fill-value rect counts, recharts-line-curve path presence, per-row SVG counts) instead of screenshot/pixel comparison, per D-03"
    - "Scoped Playwright route interception (route.abort() on one URL pattern, then reload to force a fresh EventSource) rather than context.setOffline(), to isolate the SSE-disconnect assertion from the two unrelated 5s polls"
    - "Reading a dynamic identifier (drone id) back off a rendered confirmation card rather than hardcoding it, so the mock's non-deterministic drone selection doesn't couple the spec to a specific drone"

key-files:
  created:
    - tests/specs/visualization.spec.ts
    - tests/specs/chat.spec.ts
    - tests/specs/sse-resilience.spec.ts
  modified:
    - tests/README.md

key-decisions:
  - "Budget-chart history is created by the spec itself (launch + immediate recall through the request fixture) rather than assumed present from earlier specs — each action writes a budget_snapshots row immediately, independent of the scheduler's 30s periodic snapshot, so the assertion never depends on execution order (T-04-20)."
  - "Heatmap cell text pairing (drone id + battery percent) is asserted via a <g> ancestor containing both matching <text> descendants, rather than two independent page-wide text existence checks, to keep the two labels tied to the same cell rather than merely both existing somewhere on the page."
  - "chat.spec.ts reads the launched drone id off the LAUNCH confirmation card's own text (regex against innerText) instead of hardcoding a FALCON id — the mock always launches whichever roster drone is first idle, which is not guaranteed to be the same drone across re-runs against a container with leftover state."
  - "sse-resilience.spec.ts does not assert the recalled/reconnected drone id or attempt a second full disconnect/reconnect cycle in this same test — the plan's acceptance criteria call for exactly one Live -> Disconnected -> Live sequence with no reload standing in for the reconnect half, which is what was implemented."

patterns-established:
  - "Fill-value-scoped SVG rect selectors (e.g. rect[fill=\"#34d399\"]) to count elements a specific renderer produces, distinguishing them from unrelated chart internals sharing the same SVG document."

requirements-completed: [TEST-04]

coverage:
  - id: D1
    description: "visualization.spec.ts asserts Fleet Heatmap and Energy Budget headers visible, heatmap rect count (by battery-band fill) equals roster length, at least one cell carries both drone id and battery percent as SVG text, budget-chart history created by the spec itself then asserted via the recharts-line-curve path, and roster-table SVG count >= roster length — no screenshot/pixel assertion anywhere"
    requirement: TEST-04
    verification:
      - kind: other
        ref: "grep checks for 'Fleet Heatmap' (1), '#34d399' (1), 'Energy Budget' (1), 'recharts-line-curve' (1), 'restoreFleetState' (2); grep -rE 'toHaveScreenshot|toMatchSnapshot' tests/specs/ (0 matches across the whole suite) — all pass"
        status: pass
      - kind: other
        ref: "cd tests && npx tsc --noEmit --skipLibCheck (exit 0, whole specs/ directory, no explicit file args)"
        status: pass
      - kind: e2e
        ref: "cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright"
        status: unrun
    human_judgment: true
    rationale: "Live harness execution could not be attempted this session — host disk had only 3.1GB free (98% used) at the time of verification, and the multi-stage image build (Node 20 + Python 3.12 base images, npm install, uv sync) matches the exact ENOSPC failure pattern already documented in 04-03-SUMMARY.md for this sandbox. Not forcing the build per this plan's environment-caused-gap guidance. Spec logic was verified by source review against the exact selectors confirmed in 04-RESEARCH.md Pattern 2, plus static grep/tsc checks, but never observed passing against a real running container."
  - id: D2
    description: "chat.spec.ts sends a launch message through the real chat input/send controls, asserts a confirmation-card reading LAUNCH/Dispatched, asserts the assistant reply carries the mock's [mock] prefix, asserts active_mission_count +1, reads the drone id off the card, sends a recall message, asserts a RECALL/Recalled card, and asserts active_mission_count returns to its starting value"
    requirement: TEST-04
    verification:
      - kind: other
        ref: "grep checks for 'confirmation-card' (2), 'Ask the flight director' (1), 'Send message' (1), 'LAUNCH' (2), 'Dispatched' (1), 'RECALL' (1), 'active_mission_count' (3), 'restoreFleetState' (2) — all pass"
        status: pass
      - kind: other
        ref: "cd tests && npx tsc --noEmit --skipLibCheck (exit 0)"
        status: pass
      - kind: e2e
        ref: "cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright"
        status: unrun
    human_judgment: true
    rationale: "Same live-run gap as D1 (host disk pressure, no live container available this session)."
  - id: D3
    description: "sse-resilience.spec.ts asserts Live (exact text), then breaks the stream via a route.abort() scoped to api/stream/telemetry followed by a reload, asserts Disconnected, then unroutes and asserts Live again with no reload between unroute and the final assertion"
    requirement: TEST-04
    verification:
      - kind: other
        ref: "grep checks for 'api/stream/telemetry' (1), 'unroute' (1), 'Disconnected' (1); ls tests/specs/ lists all seven files (chat, fresh-start, health, helpers, missions, roster, sse-resilience, visualization); grep -rEn 'test\\.(skip|fixme|only)' tests/specs/ returns clean — all pass"
        status: pass
      - kind: other
        ref: "cd tests && npx tsc --noEmit --skipLibCheck (exit 0)"
        status: pass
      - kind: e2e
        ref: "cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright, twice in a row"
        status: unrun
    human_judgment: true
    rationale: "Same live-run gap as D1/D2. This is also the scenario carrying this plan's flagged prohibition (T-04-16) — no reload stands in for the reconnect assertion in the source, but confirming that in practice (the browser's native EventSource retry actually flipping the indicator back to Live) requires the same live container this session could not build."
  - id: D4
    description: "tests/README.md accurately describes the suite as implemented (seven spec files, scenario each covers) instead of 'Specification only', and documents the host-port conflict with the dev container plus the single-worker execution model"
    requirement: TEST-04
    verification:
      - kind: other
        ref: "grep -c 'sse-resilience' tests/README.md (1); source review confirms all seven files named with scenario coverage, host-port note ('stop any dev container first... publishes the same host port'), and single-worker rationale ('workers: 1... share one mutable fleet state')"
        status: pass
    human_judgment: false
  - id: D5
    description: "The suite passes twice in a row without recreating the app container between runs (idempotency), and every spec's restoreFleetState cleanup is registered in afterEach so no spec leaves state behind for the next"
    requirement: TEST-04
    verification:
      - kind: other
        ref: "source review — visualization.spec.ts, chat.spec.ts each register launchedDroneId + afterEach restoreFleetState; sse-resilience.spec.ts mutates no persistent fleet state (route interception only, unrouted before the test ends) and needs no cleanup"
        status: pass
      - kind: e2e
        ref: "cd tests && docker compose -f docker-compose.test.yml up --build ... (run twice consecutively)"
        status: unrun
    human_judgment: true
    rationale: "Same live-run gap as D1-D3 — idempotency across two consecutive runs can only be confirmed by actually running the suite twice against a live container."

# Metrics
duration: ~45min
completed: 2026-08-14
status: complete
---

# Phase 04 Plan 04: Visualization, Mocked Chat, and SSE Resilience E2E Specs Summary

**Wrote the last three TEST-04 Playwright specs (heatmap/budget-chart/sparkline structural assertions, mocked flight-director launch/recall via chat, and telemetry-stream disconnect/unaided-reconnect) and rewrote tests/README.md from "Specification only" to describe the seven implemented specs — with live docker-compose harness execution blocked by confirmed host disk pressure (3.1GB free) after static verification (grep, tsc, source review against exact component/backend selectors) all passed.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3 completed
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- `tests/specs/visualization.spec.ts` covers TEST-04 scenario 4 — heatmap cells counted by the three battery-band SVG fill values against the live roster length (not a bare `rect` count, which would drift with the line chart's and sparklines' own SVG internals), at least one cell asserted to carry both a drone id and a battery percentage as SVG text (the colour-blind-safe non-colour cue), the budget chart's own history created by launching and immediately recalling a mission through the `request` fixture (so the assertion never depends on what earlier specs left behind) and then asserted via the `recharts-line-curve` path with a 15s timeout to absorb the chart's independent 5s poll, and the roster table's per-row sparkline SVG count checked against the roster length
- `tests/specs/chat.spec.ts` covers TEST-04 scenario 5 — a "launch" message through the real chat input (`Ask the flight director...` placeholder) and send button (`Send message` aria-label) produces a `confirmation-card` reading `LAUNCH`/`Dispatched`, the assistant reply carries the mock's `[mock]` bracketed prefix (so a harness that ever loses `LLM_MOCK=true` fails loudly instead of silently making a real, billable, non-deterministic OpenRouter call), and `active_mission_count` increases by one; the launched drone id is read back off the confirmation card's own text rather than hardcoded, a "recall" message then produces a `RECALL`/`Recalled` card, and the mission count returns to its starting value
- `tests/specs/sse-resilience.spec.ts` covers TEST-04 scenario 6 — asserts `Live` with exact text match, breaks the stream via `context.route()` scoped to `**/api/stream/telemetry` alone (not a blanket `setOffline()`, which would also break the two unrelated 5s polls) followed by a reload (route interception only affects new requests, not an already-open `EventSource`), asserts `Disconnected`, then `unroute()`s and asserts the return to `Live` with **no reload** in between — this is the literal implementation of this plan's flagged prohibition (T-04-16): the claim under test is that the running client recovers on its own through the native `EventSource` retry plus the server's `retry: 1000` directive, not that a fresh page load can connect
- `tests/README.md` rewritten: the "Specification only" status section is gone, replaced with a table naming all seven spec files and the scenario each covers, plus two operational facts (the dev container must be stopped first because the test compose publishes the same host port, and the suite runs single-worker because all seven specs share one app container's mutable fleet state)

## Task Commits

Each task was committed atomically:

1. **Task 1: Visualization rendering — heatmap cells, budget line, and sparklines, structurally asserted** - `7e19d5e` (feat)
2. **Task 2: Mocked flight director — launch and recall through chat with inline confirmations** - `d8f6ad1` (feat)
3. **Task 3: Telemetry stream resilience — disconnect, unaided reconnect, and an honest suite README** - `8bf86c5` (feat)

## Files Created/Modified

- `tests/specs/visualization.spec.ts` (new) — TEST-04 scenario 4
- `tests/specs/chat.spec.ts` (new) — TEST-04 scenario 5
- `tests/specs/sse-resilience.spec.ts` (new) — TEST-04 scenario 6
- `tests/README.md` — status section, spec table, host-port and single-worker documentation

## Decisions Made

- Budget-chart history is created by the visualization spec itself (launch + immediate recall through the `request` fixture) rather than assumed present, since it's a separate write path (immediate on launch/recall, not just the scheduler's 30s periodic snapshot) and the spec must not depend on execution order (T-04-20 mitigation, already flagged in the plan's threat register).
- Heatmap cell-label pairing is asserted by locating a `<g>` ancestor containing both a drone-id-matching `<text>` descendant and a percent-suffixed `<text>` descendant, rather than two independent page-wide existence checks — this ties the two labels to the same cell rather than merely confirming both exist somewhere on the page.
- `chat.spec.ts` reads the launched drone id off the LAUNCH confirmation card's own rendered text (regex against `innerText`) instead of hardcoding a FALCON id, since the mock always launches whichever roster drone is first idle — not guaranteed to be the same drone across re-runs against a container with leftover state, per the plan's explicit guidance.
- `sse-resilience.spec.ts` implements exactly one `Live -> Disconnected -> Live` sequence with the primary route-abort-then-reload mechanism from 04-RESEARCH.md Pattern 4 (not the `context.setOffline()` fallback) — the primary mechanism's live behavior could not be observed this session (see Deviations), so if a follow-up session finds route interception does not reliably flip the indicator, the offline fallback is the documented next step.

## Deviations from Plan

### Verification Gap (environment-caused, not a code defect)

**1. Live docker-compose harness execution could not be attempted this session**
- **Found during:** Pre-flight check before Task 1's live-harness `<verify>` step
- **Issue:** `df -h /` showed the host filesystem at 98% capacity with only 3.1GB free. The Docker socket itself was reachable this session (unlike 04-03's hung-socket finding — `docker --context default ps` and `docker compose -f docker-compose.test.yml config --services` both succeeded immediately), but the multi-stage image build this plan's `<verify>` requires (Node 20-slim + Python 3.12-slim base image layers, `npm install`, `uv sync`, plus the already-cached 2.83GB Playwright browser image) matches the exact resource-exhaustion failure pattern 04-03-SUMMARY.md documented in this same sandbox (session tmpfs/ENOSPC during `docker compose up --build`). Attempting the build risked repeating that failure and potentially filling the disk further, breaking other tooling in this session.
- **Resolution:** Did not force the build. All verification not requiring a live running container passed: every `grep`-based acceptance criterion (heatmap/budget-chart/chat/sse selectors, no `test.skip/fixme/only`, no screenshot assertions anywhere in `tests/specs/`), `cd tests && npx tsc --noEmit --skipLibCheck` (exit 0, whole `specs/` directory via `tsconfig.json`'s `include`, no explicit file args — matching the working invocation 04-03-SUMMARY.md established), and `docker compose -f docker-compose.test.yml config --services` (config-only, no build). Spec logic was additionally verified by direct source review against the exact selectors, CSS classes, and mock keyword contract confirmed in 04-RESEARCH.md's Pattern 2/3/4 tables (`FleetHeatmap.tsx`, `EnergyBudgetChart.tsx`, `DroneSparkline.tsx`, `ChatPanel.tsx`, `ConfirmationCard.tsx`, `ChatMessage.tsx`, `useTelemetryStream.ts`, `ConnectionDot.tsx`, `backend/app/chat/llm.py`'s `mock_reply()`), all read in full this session.
- **Files affected:** None — this is a verification-only gap. All three task commits (`7e19d5e`, `d8f6ad1`, `8bf86c5`) landed successfully with complete, reviewed code.
- **Impact on plan:** No task's code is incomplete. The live end-to-end pass (both specs green individually and the whole suite passing twice in a row without recreating the app container) and this plan's flagged prohibition's live behavior (does the route-abort-then-reload mechanism actually flip the `ConnectionDot` in a real browser, per 04-RESEARCH.md's Assumption A2) are recorded as `status: unrun` in this SUMMARY's `coverage:` block and should be re-run from a session with unconstrained disk space before `/gsd-ship`.

---

**Total deviations:** 0 auto-fixed; 1 environment-caused verification gap (host disk at 98% capacity, 3.1GB free) spanning the live end-to-end harness run for all three of this plan's specs, fully documented rather than silently skipped, matching the same category of gap already recorded in 04-01-SUMMARY.md and 04-03-SUMMARY.md for this sandbox.

## Known Stubs

None. No stub data, empty placeholders, or unwired UI paths were introduced by this plan — it adds test code and documentation only, no application code.

## Issues Encountered

- Host disk at 98% capacity (3.1GB free) at verification time — consistent with, and likely the same underlying cause as, 04-03-SUMMARY.md's documented session-tmpfs-exhaustion finding during a live `docker compose up --build`. Not re-attempted this session to avoid repeating that failure or further reducing available disk space.
- `cd tests && npx tsc --noEmit --skipLibCheck` required `node_modules/` to exist locally (not present in this fresh worktree checkout); `npm install` inside `tests/` succeeded without incident and installed the `typescript` devDependency already declared in `tests/package.json` by 04-03. `node_modules/` remains gitignored and was not committed.

## User Setup Required

None for the code itself. To close the `unrun` verification items in this SUMMARY's `coverage:` block before `/gsd-ship`:
1. From a shell with unconstrained disk space (this sandbox's host filesystem was at 98% capacity, 3.1GB free, at verification time), run: `./scripts/stop_mac.sh` (or equivalent), then `cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright`, twice in a row without recreating the `app` container between runs.
2. Open `tests/playwright-report/index.html` after the run and confirm all seven specs pass, with particular attention to `sse-resilience.spec.ts`'s reconnect assertion (per its `human-check`: stop the container, confirm the indicator turns red and reads `Disconnected`; start it again and confirm it returns to `Live` on its own without touching the browser) and `visualization.spec.ts`'s heatmap/budget-chart/sparkline rendering (per its `human-check`: one coloured rectangle per drone with legible text, a budget line that steps down on launch, a small trend line in every roster row).
3. If `sse-resilience.spec.ts`'s route-abort-then-reload mechanism proves unable to flip the connection indicator to `Disconnected` in practice, 04-RESEARCH.md's documented fallback is `context.setOffline(true/false)` — swap it in and note the change here per this plan's explicit instruction, rather than silently reworking the spec.

## Next Phase Readiness

- All six TEST-04 scenarios plus the pre-existing health check now exist as spec files under `tests/specs/` (`health`, `fresh-start`, `roster`, `missions`, `visualization`, `chat`, `sse-resilience`) — TEST-04's spec-file completeness criterion is met at the source level.
- `tests/README.md` accurately reflects the suite's implemented state.
- This is the final plan in Phase 4's wave sequence per the phase's `<verification>` block; the phase-level gate (full E2E suite green twice in a row, backend/frontend unit suites green) still needs a live Docker run from an environment with adequate disk space — recommend the orchestrator or a follow-up session close this out, alongside 04-03's carried-forward `unrun` items (TEST-05's built-image browser-runtime-absence probe, and the same full E2E suite run), before considering Phase 4 fully closed.

---
*Phase: 04-docker-packaging-test-suites*
*Completed: 2026-08-14*

## Self-Check: PASSED

- FOUND: tests/specs/visualization.spec.ts
- FOUND: tests/specs/chat.spec.ts
- FOUND: tests/specs/sse-resilience.spec.ts
- FOUND: .planning/phases/04-docker-packaging-test-suites/04-04-SUMMARY.md
- FOUND commit: 7e19d5e
- FOUND commit: d8f6ad1
- FOUND commit: 8bf86c5
