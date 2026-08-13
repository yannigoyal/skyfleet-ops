---
phase: 03-frontend-buildout
plan: 06
subsystem: ui
tags: [react, next.js, vitest, react-testing-library, chat, tdd]
status: complete

# Dependency graph
requires:
  - phase: 03-frontend-buildout
    provides: "03-05: page.tsx's main grid with FleetHeatmap and EnergyBudgetChart mounted, the placeholder chat <aside> left untouched for this plan"
  - phase: 02-ai-flight-director-chat
    provides: "POST /api/chat — executes AI-proposed missions/roster_changes through the identical missions.service/roster.service functions manual dispatch uses; returns {message, missions, roster_changes, errors}"
provides:
  - "useChat (FE-08, D-07, D-08): POST /api/chat wrapper owning turns/sending state, the in-flight single-turn lock, and the shared FleetOpsProvider.refetch() call after any turn that executed an action"
  - "ConfirmationCard + ChatMessage (FE-09, D-06): compact per-action success/failure cards and the transcript bubble that composes them, safe against raw-HTML injection and multi-byte truncation"
  - "ChatPanel (FE-08, D-05): docked, collapsible right-hand sidebar mounted in page.tsx in place of the static placeholder — the phase's final mount"
affects: []

# Actuals (#2632)
actuals:
  tokens: 8400
  tasks: 3
  commits: 6

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A hook that must call another provider's action (useChat -> useFleetOps().refetch) is itself a 'use client' hook consuming that provider's context internally, rather than requiring every caller to thread refetch through as a parameter — mirrors DispatchBar's existing direct useFleetOps() consumption"
    - "System-role transcript turns are a third ChatTurn.role alongside user/assistant specifically to distinguish 'we never reached the copilot' (transport failure) from 'the copilot told you an action failed' (an errors[] entry) — the two must never be visually or semantically merged"
    - "Zone truncation in a confirmation card uses CSS ellipsis (inline-block max-w + truncate) with a native title attribute holding the full string, never JS index/byte slicing, so a multi-byte zone name can never be split mid-character"
    - "jsdom's missing scrollIntoView is polyfilled once, globally, in vitest.setup.ts (a no-op function assigned to HTMLElement.prototype) rather than guarded defensively in component code — same precedent as the existing ResizeObserver stub; needed once ChatPanel is mounted inside page.tsx's own integration test, not only inside ChatPanel's own test file"

key-files:
  created:
    - frontend/src/types/chat.ts
    - frontend/src/lib/useChat.ts
    - frontend/src/lib/useChat.test.tsx
    - frontend/src/components/chat/ConfirmationCard.tsx
    - frontend/src/components/chat/ConfirmationCard.test.tsx
    - frontend/src/components/chat/ChatMessage.tsx
    - frontend/src/components/chat/ChatPanel.tsx
    - frontend/src/components/chat/ChatPanel.test.tsx
  modified:
    - frontend/src/app/page.tsx
    - frontend/vitest.setup.ts

key-decisions:
  - "A success badge is rendered only for an entry actually present in the backend's missions/roster_changes arrays; every errors[] string always gets its own failure card. There is no cross-referencing between the two — the backend's errors array carries no link back to a specific proposed action, so ConfirmationCard's `kind` prop is set explicitly by ChatMessage from which array an entry came, never inferred or matched by content (T-03-25, this plan's flagged prohibition)."
  - "vitest.setup.ts gained a global scrollIntoView no-op polyfill (mirroring the pre-existing ResizeObserver stub) instead of guarding the call in ChatPanel.tsx — jsdom's gap is a test-environment fact, not a production concern, and the existing precedent from 03-01/03-05 already established this file as the place to patch jsdom capability gaps."
  - "ChatPanel holds `collapsed` as local component state, not in FleetOpsProvider — it is pure view state with exactly one consumer, matching FleetOpsProvider's existing scope boundary (only cross-component shared state lives there)."

patterns-established:
  - "Any future hook needing FleetOpsProvider's shared refetch should call useFleetOps() internally (as useChat does) rather than accepting it as a parameter, keeping the shared-refetch contract enforced at the type level instead of by caller discipline."

requirements-completed: [FE-08, FE-09]

coverage:
  - id: D1
    description: "Operator types a message, sends it, and the flight director's reply appears in the scrolling transcript (FE-08)"
    requirement: "FE-08"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useChat.test.tsx#Test 1 (immediate user turn), Test 2 (assistant turn shape); frontend/src/components/chat/ChatPanel.test.tsx#Test 2 (submit calls send)"
        status: pass
    human_judgment: true
    rationale: "Live conversation against the real backend (or LLM_MOCK=true) is deferred to end-of-phase UAT per workflow.human_verify_mode=end-of-phase; jsdom tests prove the request/response/state pipeline against mocked fetch, not the live round-trip."
  - id: D2
    description: "Chat input and send control are disabled with a loading indicator visible for the whole POST /api/chat in-flight window; no second message can be queued (FE-08, D-08)"
    requirement: "FE-08"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useChat.test.tsx#Test 3 (sending true until settled, second send is a no-op); frontend/src/components/chat/ChatPanel.test.tsx#Test 3 (input/button disabled, loading indicator present, both re-enable)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The chat panel is a fixed right-hand sidebar, visible by default, with a working collapse toggle — not a modal and not left-docked (FE-08, D-05)"
    requirement: "FE-08"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ChatPanel.test.tsx#Test 4 (D-05 collapse/expand restores transcript and input), Test 5 (no role=dialog, no fixed inset-0 overlay class)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every entry in missions/roster_changes renders as a compact inline confirmation card with action verb, key parameters, and an outcome badge (FE-09, D-06)"
    requirement: "FE-09"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ConfirmationCard.test.tsx#Test 1 (launch), Test 2 (recall, no undefined/NaN), Test 3 (add/remove)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every string in errors[] renders as its own visible failure card with a red outcome badge"
    requirement: "FE-09"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ConfirmationCard.test.tsx#Test 4 (failure card, no success badge ever)"
        status: pass
    human_judgment: false
  - id: D6
    description: "ChatPanel renders correctly with zero messages on a fresh session — the documented welcome state, not a broken or blank component"
    requirement: "FE-08"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ChatPanel.test.tsx#Test 1 (exact welcome heading + body copy)"
        status: pass
    human_judgment: false
  - id: D7
    description: "Chat transcript renders LLM/operator text via JSX text interpolation only, no raw-HTML injection, no manual byte/substring truncation"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ConfirmationCard.test.tsx#Test 6 (HTML-looking + multi-byte zone renders as literal text, zero elements created)"
        status: pass
      - kind: static
        ref: "acceptance-criteria grep: no dangerouslySetInnerHTML anywhere under src/components/chat/"
        status: pass
    human_judgment: false
  - id: D8
    description: "The transcript auto-scrolls to the newest message on each new turn"
    requirement: "FE-08"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ChatPanel.test.tsx#Test 6 (overflow: scrollIntoView called after a new turn)"
        status: pass
    human_judgment: false
  - id: D9
    description: "Assistant message content wraps inside a bubble capped at ~85% of sidebar width, no truncation"
    verification:
      - kind: static
        ref: "acceptance-criteria: ChatMessage.tsx bubble className includes max-w-[85%]"
        status: pass
    human_judgment: true
    rationale: "Visual confirmation of the actual wrap/width rendering in a real browser viewport is deferred to end-of-phase UAT; the unit tests prove the className is applied, not the rendered pixel width."
  - id: D10
    description: "After any chat turn that executed a mission or roster action, the panel calls the same shared refetch from FleetOpsProvider the dispatch bar uses (D-07)"
    requirement: "FE-08"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useChat.test.tsx#Test 4 (D-07: refetch fires exactly once when missions/roster_changes non-empty, not at all when both empty)"
        status: pass
    human_judgment: false
  - id: D11
    description: "A network/transport failure on POST /api/chat renders one red inline system message, visually distinct from a failed-action card (backstop)"
    verification:
      - kind: unit
        ref: "frontend/src/lib/useChat.test.tsx#Test 5 (rejected fetch -> system turn, exact copy, no refetch), Test 6 (non-2xx handled identically, not thrown)"
        status: pass
    human_judgment: false
  - id: D12
    description: "MUST NOT render a success confirmation card for an AI-proposed action that did not actually execute (flagged prohibition)"
    verification:
      - kind: unit
        ref: "frontend/src/components/chat/ConfirmationCard.test.tsx#Test 4 (failure card never carries a success badge), Test 5 (one success + one error renders exactly two cards, neither omitted)"
        status: pass
    human_judgment: true
    rationale: "The plan flags this prohibition's verification as judgment-tier; the automated tests prove the card-selection logic is structurally sound (success only from missions/roster_changes, failure only from errors[]), but confirming this reads unambiguously to an operator during a real multi-action turn is deferred to end-of-phase UAT."
---

# Phase 03 Plan 06: AI Flight Director Chat Panel Summary

**Replaced the static "not yet implemented" placeholder sidebar with a working, tested AI flight-director chat panel — one turn at a time, every executed mission or roster change surfaced as its own inline confirmation card, and a distinct system message for transport failures so the operator never mistakes "we never reached the copilot" for "the copilot's action failed."**

## Performance

- **Duration:** ~40 min
- **Tasks:** 3 (all TDD)
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments

- `frontend/src/types/chat.ts` — `ChatMissionAction`, `ChatRosterChange`, `ChatResponse`, `ChatTurn` mirroring `backend/app/chat/router.py`'s response body verbatim, including the `system` role added client-side to distinguish transport failures from AI-reported action failures.
- `useChat` (FE-08, D-07, D-08): a `"use client"` hook owning `{turns, sending, send}`. `send()` trims and no-ops on empty/whitespace input, appends the user's turn immediately (before the response resolves), guards the whole request body behind `sending` so a second send while a request is in flight is a no-op, and on a 2xx response appends an assistant turn carrying `message`/`missions`/`roster_changes`/`errors` verbatim. Calls `useFleetOps().refetch()` — the identical shared refresh the dispatch bar uses — only when the response actually executed a mission or roster action (D-07), never on a pure Q&A turn. A rejected fetch or non-2xx status appends one distinct `system`-role turn with the exact UI-SPEC copy "Connection error — try sending your message again.", never calls refetch, and always clears `sending` in a `finally` branch.
- `frontend/src/lib/useChat.test.tsx` — 7 behaviors: immediate user turn, full assistant turn shape, the D-08 in-flight lock (including a second send while pending being a true no-op, not a queued call), the D-07 refetch-only-on-action-executed rule, the backstop transport-failure system turn, non-2xx handled identically to a rejected fetch, and empty-input rejection.
- `ConfirmationCard` (FE-09, D-06): a props-only component with two shapes — a success card for an entry actually present in `missions`/`roster_changes` (format `{VERB} {DRONE_ID} → {ZONE} ({DISTANCE}km)` for launches, verb+id only for recall/add/remove, an emerald "Dispatched"/"Recalled"/"Added"/"Removed" badge) and a failure card for an `errors[]` string (red "Failed:" badge). A success badge is structurally impossible to attach to an unexecuted action — `ConfirmationCard`'s `kind` prop is set by the caller from which array an entry came, never inferred from content matching (T-03-25). Zone truncation is CSS ellipsis on a fixed max-width with a native `title` attribute holding the full string — never index/byte arithmetic, so a multi-byte zone name can never split mid-character (T-03-24).
- `ChatMessage` — one transcript bubble per `ChatTurn`. Renders `content` as a plain JSX text child only (React's default escaping applies; no `dangerouslySetInnerHTML` anywhere under `src/components/chat/`), operator turns right-aligned on a slate surface, assistant turns left-aligned on the panel surface capped at `max-w-[85%]`, system turns as a full-width red notice. Beneath an assistant turn, renders one `ConfirmationCard` per `missions` entry, one per `roster_changes` entry, and one failure card per `errors` string.
- `frontend/src/components/chat/ConfirmationCard.test.tsx` — 8 behaviors covering launch/recall/add/remove success cards, the failure-card prohibition (never a success badge), the one-success-plus-one-error exactly-two-cards case, an HTML-looking + multi-byte zone rendering as literal text with zero elements created, long-zone truncation with a `title` attribute, and a no-actions assistant turn rendering no cards at all (via `ChatMessage`, created in the same task).
- `ChatPanel` (FE-08, D-05, D-08): a `"use client"` docked right-hand sidebar calling `useChat()`. Collapsed state is local component state (pure view state, single consumer). Header bar reuses the `py-3` spacing exception; collapse toggle and send control are hand-authored inline SVGs (stroke-based, `currentColor`) per UI-SPEC — no new icon dependency. Empty transcript renders the exact welcome copy "Flight Director standing by" / "Ask about fleet status or dispatch a mission — e.g. \"Launch FALCON-03 to Riverside\"."; a trailing sentinel `div` plus a `useEffect` keyed on `turns.length` auto-scrolls to the newest message. Input and send control both bind `disabled={sending}`; a "Thinking…" indicator renders alongside while a turn is in flight (D-08).
- `frontend/src/components/chat/ChatPanel.test.tsx` — 7 behaviors: welcome state, submit-calls-send, D-08 disable+loading-indicator+re-enable, D-05 collapse/expand round-trip, a not-a-modal layout assertion (no `role="dialog"`, no `fixed inset-0`), auto-scroll on a new turn, and inline confirmation cards rendering for an assistant turn carrying executed actions.
- `frontend/src/app/page.tsx` — deleted the placeholder `<aside>` and its "not yet implemented" copy entirely; mounted `<ChatPanel />` in its place. This was the phase's last mount: `page.tsx` now composes Header, dispatch bar, roster panel with sparklines, detail panel, heatmap, budget chart, missions table, and the chat sidebar, all inside one `FleetOpsProvider`.
- `frontend/vitest.setup.ts` — added a global `scrollIntoView` no-op polyfill (jsdom has none), mirroring the existing `ResizeObserver` stub precedent from 03-01. Needed once `ChatPanel` is mounted inside `page.tsx`'s own integration test (`page.test.tsx`), which previously had no reason to stub it.
- Full suite verification: `npm test` (81/81 passing across 14 files, including the pre-existing `page.tsx` integration test), `npx tsc --noEmit` (clean), `npm run build` (static export succeeds).

## Task Commits

Each task was committed atomically (TDD: separate RED/GREEN commits):

1. **Task 1: Chat types and useChat hook** — RED: `2fe87fa` (test) -> GREEN: `a6521a4` (feat)
2. **Task 2: ConfirmationCard and ChatMessage** — RED: `ee349c8` (test) -> GREEN: `f480b5b` (feat)
3. **Task 3: ChatPanel sidebar** — RED: `f4f8e3f` (test) -> GREEN: `fe82354` (feat, includes the vitest.setup.ts scrollIntoView polyfill fix and the page.tsx mount)

**Plan metadata:** committed alongside this SUMMARY (worktree mode — orchestrator finalizes after wave merge).

## Files Created/Modified

- `frontend/src/types/chat.ts` - New: ChatMissionAction/ChatRosterChange/ChatResponse/ChatTurn wire types
- `frontend/src/lib/useChat.ts` - New: POST /api/chat hook with D-08 in-flight lock and D-07 shared refetch
- `frontend/src/lib/useChat.test.tsx` - New: 7 behaviors
- `frontend/src/components/chat/ConfirmationCard.tsx` - New: success/failure action cards
- `frontend/src/components/chat/ConfirmationCard.test.tsx` - New: 8 behaviors (also exercises ChatMessage)
- `frontend/src/components/chat/ChatMessage.tsx` - New: one transcript bubble
- `frontend/src/components/chat/ChatPanel.tsx` - New: docked collapsible sidebar
- `frontend/src/components/chat/ChatPanel.test.tsx` - New: 7 behaviors
- `frontend/src/app/page.tsx` - Mounts `ChatPanel` in place of the placeholder aside
- `frontend/vitest.setup.ts` - Adds a global scrollIntoView polyfill for jsdom

## Decisions Made

- A success badge on `ConfirmationCard` is only ever attached to an entry actually present in the backend's `missions`/`roster_changes` arrays — `ChatMessage` sets `kind="success"` explicitly per array element and `kind="failure"` explicitly per `errors[]` string; there is no content-matching or inference step where a card's success/failure status could be guessed wrong. This is the direct implementation of the plan's flagged prohibition (T-03-25).
- `vitest.setup.ts` gained a global `scrollIntoView` no-op polyfill rather than a defensive `typeof ... === "function"` guard inside `ChatPanel.tsx` — jsdom's missing API is a test-environment gap, not a production concern (every real browser implements it), and 03-01/03-05 already established this file as the place to patch such gaps (the existing `ResizeObserver` stub).
- `ChatPanel`'s `collapsed` state lives in local component state, not `FleetOpsProvider` — it has exactly one consumer and no cross-component effect, matching the provider's existing scope boundary (`selectedDroneId` is the only other piece of "client state" it holds, and that one *is* shared across the roster panel, detail panel, heatmap, and missions table).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] jsdom has no `scrollIntoView`, breaking the pre-existing `page.tsx` integration test once `ChatPanel` was mounted**
- **Found during:** Task 3, running `npm test` (full suite) after mounting `<ChatPanel />` in `page.tsx`.
- **Issue:** `TypeError: bottomRef.current?.scrollIntoView is not a function` — jsdom does not implement `Element.scrollIntoView`. `ChatPanel.test.tsx` already stubbed it locally per the plan's own instruction, but `page.test.tsx` (from plan 03-01, unaware of `ChatPanel`) had no such stub, and now renders `ChatPanel` as part of the full page.
- **Fix:** Added a global no-op `scrollIntoView` polyfill to `frontend/vitest.setup.ts`, the same file and same pattern already used for jsdom's missing `ResizeObserver`. Simplified `ChatPanel.test.tsx`'s local stub to a plain `vi.spyOn(...).mockImplementation()` now that the property reliably exists at both the type and runtime level.
- **Files modified:** `frontend/vitest.setup.ts`, `frontend/src/components/chat/ChatPanel.test.tsx`.
- **Verification:** `npm test` passes 81/81 across all 14 files; `npx tsc --noEmit` clean (the prior branching stub produced a spurious `Property 'scrollIntoView' does not exist on type 'never'` TS error, resolved by simplifying to the direct spy).
- **Committed in:** `fe82354` (Task 3 GREEN) — found and fixed before the first full-green full-suite run.

**Total deviations:** 1 auto-fixed (Rule 3, blocking issue), found during Task 3's full-suite integration check, same scope as the file it touched (shared test infrastructure already established by 03-01/03-05, no architectural impact).

## Issues Encountered

- `npm run lint` (`next lint`) still requires interactive ESLint setup — the same pre-existing issue logged in `deferred-items.md` from plan 03-01 and re-confirmed in every subsequent plan's summary (03-02 through 03-05). Not re-fixed here per the scope-boundary rule; not re-logged as a new duplicate entry. `npx tsc --noEmit` (clean) and `npm run build` (succeeds) provide equivalent static-correctness coverage for this plan's changes.
- Fresh worktree had no `node_modules` (gitignored). Ran `npm ci` in `frontend/` to install from the committed lockfile before running tests/build — same one-time step noted in every prior Phase 3 plan's summary.

## User Setup Required

None - no external service configuration required. The manual verification step in the plan's `<verify>` block ("Run the backend with LLM_MOCK=true, open the console...") is deferred to end-of-phase UAT per `workflow.human_verify_mode=end-of-phase`, consistent with every other judgment-tier item in this phase.

## Next Phase Readiness

FE-08 and FE-09 are complete: the AI flight-director sidebar is docked, collapsible, and mounted in place of the placeholder. `page.tsx` now composes every Phase 3 surface — header, dispatch bar, roster panel with sparklines, detail panel, heatmap, budget chart, missions table, and chat — inside a single `FleetOpsProvider`, with `useChat` as the sole `POST /api/chat` caller reusing the provider's shared `refetch()`. This was Phase 3's final plan; no further frontend-buildout work is scoped. The full `npm test` / `tsc --noEmit` / `npm run build` triad is green across all 14 test files. No blockers for phase closeout, other than the standing end-of-phase manual UAT pass (LLM_MOCK=true) already deferred by every judgment-tier coverage row across plans 03-01 through 03-06.

---
*Phase: 03-frontend-buildout*
*Completed: 2026-08-13*

## Self-Check: PASSED

All eight new files verified present on disk (`frontend/src/types/chat.ts`,
`frontend/src/lib/useChat.ts`, `frontend/src/lib/useChat.test.tsx`,
`frontend/src/components/chat/ConfirmationCard.tsx`,
`frontend/src/components/chat/ConfirmationCard.test.tsx`,
`frontend/src/components/chat/ChatMessage.tsx`,
`frontend/src/components/chat/ChatPanel.tsx`,
`frontend/src/components/chat/ChatPanel.test.tsx`) plus the two modified files
(`frontend/src/app/page.tsx`, `frontend/vitest.setup.ts`) and this SUMMARY.md.
All six commits (`2fe87fa`, `a6521a4`, `ee349c8`, `f480b5b`, `f4f8e3f`,
`fe82354`) verified present in `git log`.
