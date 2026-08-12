# Pitfalls Research

**Domain:** Real-time ops console — concurrent mission/budget accounting, SQLite under async FastAPI, LLM auto-executed structured actions, SSE/EventSource streaming, Next.js static export served by a single-port backend
**Researched:** 2026-08-12
**Confidence:** HIGH (SQLite/async, SSE, static-export serving — verified against current docs and the existing codebase); MEDIUM (LLM auto-execution risk — established pattern, no SkyFleet-specific incident yet since chat is unbuilt)

## Critical Pitfalls

### Pitfall 1: Read-then-write energy budget race condition (TOCTOU)

**What goes wrong:**
Two mission launches submitted close together (manual dispatch + LLM auto-dispatch, or two chat-driven launches) both read `remaining_kwh`, both see enough budget, both pass validation, and both write — overdrawing the shared 500 kWh budget. The same pattern applies to "drone must not already be in flight" checks: two launches for the same drone both see it idle and both succeed, creating two `en_route` mission rows for one drone.

**Why it happens:**
The natural way to write this code is `SELECT budget; if budget >= cost: INSERT mission; UPDATE budget`. Under FastAPI's async model, an `await` between the read and the write (e.g. an `await db.execute(...)` for the read, then more awaits before the write) yields control back to the event loop, so a second concurrent request's read can interleave before the first request's write commits. This is exactly the failure mode already flagged in `.planning/codebase/CONCERNS.md` as the "Race Condition in Drone Eligibility Check" (`backend/app/missions/service.py`) — the same class of bug, just at the budget-accounting layer instead of the roster layer.

**How to avoid:**
- Make the check-and-write a single atomic SQL statement or a single transaction under the existing `Database` `asyncio.Lock` (already serializes all DB ops per `backend/app/db/connection.py`) — do the budget check with `SELECT ... FOR the same lock scope` and the `INSERT`/`UPDATE` in one critical section, not two separate awaited calls with logic in between.
- Prefer a conditional UPDATE: `UPDATE operator_profile SET energy_budget_kwh = energy_budget_kwh - ? WHERE energy_budget_kwh >= ?` and check `rowcount == 0` to detect insufficient funds, rather than SELECT-then-UPDATE. This makes the database itself the source of truth for the race instead of app-level logic.
- For the "drone already in flight" check, add a real uniqueness constraint (e.g. partial unique index on `missions(drone_id) WHERE status='en_route'`) so the database rejects the second concurrent launch even if application logic races.
- Do not rely on the `asyncio.Lock` alone as documentation — write a concurrency test (two simultaneous launch requests via `asyncio.gather`) that asserts only one succeeds when budget/drone availability allows exactly one.

**Warning signs:**
- Budget goes negative or missions table has two `en_route` rows for the same `drone_id`.
- Manual code review shows an `await` (DB call, LLM call, or `asyncio.sleep`) between reading budget/status and writing it.
- Existing `_is_eligible()` pattern in `missions/service.py` already exhibits this shape — same author/pattern is likely to repeat it in the new budget code unless explicitly guarded against.

**Phase to address:**
Fleet operations / mission dispatch phase (energy-budget accounting) — before LLM chat is layered on top, since chat adds a second concurrent caller of the same launch path.

---

### Pitfall 2: SQLite lazy-init race on cold start

**What goes wrong:**
The spec requires lazy initialization: "if the SQLite file doesn't exist or tables are missing, create schema and seed." If the FastAPI app receives multiple concurrent requests immediately after container start (e.g. frontend fires several `GET /api/fleet`, `GET /api/roster`, and the SSE stream simultaneously on page load), more than one request can observe "no tables" and attempt `CREATE TABLE` / seed insertion concurrently, causing `sqlite3.OperationalError: table already exists` or duplicate seed rows (e.g. 20 fleet_roster rows instead of 10).

**Why it happens:**
"Lazy init on first request" is commonly implemented as an `if not initialized: await init_db()` check without a lock, and FastAPI's async model means the first `await` inside `init_db()` yields control before initialization completes, letting a second concurrent request start its own init.

**How to avoid:**
- Run schema creation and seeding once, synchronously, during FastAPI's `lifespan`/startup event — not lazily on first request. This removes the race entirely and matches normal FastAPI practice; "lazy" only needs to mean "no manual migration step," not "triggered by request handling."
- If lazy-on-request is kept for some reason, guard it with the same `asyncio.Lock` already used for DB writes, and use `CREATE TABLE IF NOT EXISTS` plus `INSERT OR IGNORE`/upsert-style seeding so a second racer is a no-op rather than an error.
- Use SQLite WAL mode (already configured per `connection.py`) and set `PRAGMA busy_timeout` explicitly (e.g. 5000ms) so any residual lock contention during init retries instead of raising `database is locked` immediately.

**Warning signs:**
- Duplicate rows in `fleet_roster` or a second `operator_profile` row on some container starts but not others (non-deterministic — a signature of a race).
- `docker run` logs show `OperationalError: table already exists` only occasionally, or only when the frontend's initial page load fires several requests in parallel.

**Phase to address:**
Database layer phase (SQLite schema + lazy init) — must be resolved before any phase adds concurrent callers (fleet ops, chat, frontend polling).

---

### Pitfall 3: LLM auto-executes a hallucinated or malformed mission action with no confirmation gate

**What goes wrong:**
PLAN.md deliberately auto-executes LLM-issued `missions`/`roster_changes` with no confirmation dialog. Structured-output JSON from an LLM can still contain a `drone_id` that doesn't exist in the roster, a `zone` string invented rather than from the fleet's actual delivery zones, a `distance_km` that is nonsensical (negative, absurdly large, mismatched with the stated zone), or an action array with duplicate/conflicting entries (e.g. launch and recall for the same drone in one response). If these are executed against the same code path as manual dispatch without the same validation, the budget or mission state can be corrupted by content that never should have been treated as valid.

**Why it happens:**
Structured output constrains JSON *shape* (the schema), not *semantic correctness* — the model can still emit a syntactically valid object with a wrong or invented value. Teams new to this pattern often trust "it matched the schema" as sufficient validation and skip re-validating LLM-issued actions through the same business-rule checks (budget sufficiency, drone existence, drone-not-already-in-flight) applied to manual/API-driven actions.

**How to avoid:**
- Route every LLM-issued mission/roster action through the exact same validation and execution function used by the manual `POST /api/fleet/missions` / `DELETE .../{drone_id}` endpoints — never a separate "trusted" path for chat-originated actions. PLAN.md already states this ("goes through the same validation as manual dispatch"); the pitfall is a future implementer adding a shortcut for convenience.
- Validate `drone_id` against the actual roster (reject unknown IDs), reject non-positive `distance_km`, and cap `energy_cost_kwh`/`distance_km` to sane bounds before attempting execution.
- If the LLM response includes multiple actions, execute them sequentially through the shared budget-checking path (not as a batch assumed to be pre-validated) so a later action in the same response can correctly fail if an earlier one in the same response already consumed the budget.
- On validation failure, do not silently drop the action — return the specific error in the chat response so the model/operator sees why it didn't execute (PLAN.md already specifies this).
- Add a system-prompt constraint that `zone` values must come from a fixed enum/list the backend actually recognizes, and validate against that enum server-side regardless of what the prompt says (never trust the prompt as the enforcement mechanism).

**Warning signs:**
- Mission rows appear with `drone_id` values that never existed in the roster, or `zone` values that don't match any known delivery zone.
- Budget goes negative after a chat session that issued multiple mission actions in one response.
- Chat log shows an action was "executed" per the LLM's own claim in `message` text but no corresponding row exists in `missions`/`mission_log` (the model narrating success without validation actually running).

**Phase to address:**
LLM chat integration phase — the validation-reuse requirement should be a stated acceptance criterion, verified by a test that sends a chat-mocked response with an invalid `drone_id`/negative `distance_km` and asserts it is rejected with an error surfaced in the chat response, not silently executed or silently dropped.

---

### Pitfall 4: LLM response is malformed, truncated, or fails schema validation and the whole chat turn crashes

**What goes wrong:**
LLM function-calling failure modes commonly include invalid JSON, missing required fields, wrong types (string where a number was expected), or a response that omits the required `message` field entirely. If the backend does a naive `json.loads()` + direct field access, a malformed response either raises an unhandled exception (500 error, no chat reply shown) or silently executes a `None`/garbage mission.

**Why it happens:**
Even with OpenRouter/Cerebras "structured output" support, providers vary in how strictly they enforce schema compliance, and network/inference issues can return partial or empty completions. Teams often only test the happy path during development (mocked or hand-tested prompts) and don't exercise adversarial/malformed responses before shipping.

**How to avoid:**
- Parse the LLM response through a strict schema validator (e.g. Pydantic model matching the documented JSON schema) with `try/except` around parsing; on failure, return a graceful fallback chat message ("I couldn't process that — could you rephrase?") instead of a 500, and log the raw response for debugging.
- Never execute `missions`/`roster_changes` from a response that failed schema validation, even partially — treat parse failure as "no actions," not "best-effort actions."
- Persist the raw LLM response (or at least the failure) to `chat_messages`/logs so failures are diagnosable without needing to reproduce them live.
- Exercise this path explicitly in `LLM_MOCK=true` tests: include at least one mock scenario that returns malformed/incomplete JSON and assert the endpoint still returns a valid `200` chat response rather than crashing.

**Warning signs:**
- Chat endpoint returns 500 errors intermittently, correlated with unusual operator phrasing or longer conversations (more context = more chance of a truncated/malformed completion).
- No test coverage exists for malformed LLM responses — the "Missing Critical Features" section of `CONCERNS.md` already notes chat is unimplemented and has zero test coverage today, so this gap will exist unless explicitly planned for.

**Phase to address:**
LLM chat integration phase — schema-validation-with-graceful-fallback should be a named acceptance criterion, not an incidental side effect of "happy path works."

---

### Pitfall 5: EventSource silently multiplies connections or misses updates across reconnects

**What goes wrong:**
Two related SSE failure modes: (1) if the frontend re-creates an `EventSource` object on every component re-render (common in React when the `new EventSource(url)` call sits in a render path or a `useEffect` without a stable dependency array / cleanup), multiple simultaneous connections to `/api/stream/telemetry` accumulate, each pushing full-fleet updates — multiplying server load and causing duplicate/out-of-order UI updates. (2) On an actual network drop, `EventSource`'s built-in auto-reconnect fires, but if the backend doesn't send `id:` fields and doesn't honor `Last-Event-ID` on reconnect, the client has no way to know it missed telemetry ticks during the outage — it just resumes forward from whatever the server currently has, silently losing data (acceptable for telemetry, but worth an explicit decision).

**Why it happens:**
React's effect lifecycle plus `EventSource`'s implicit retry behavior interact non-obviously: a missing `return () => es.close()` cleanup in a `useEffect`, or an effect dependency that changes on every render, both cause connection leaks. Separately, `CONCERNS.md` already flags that late subscribers get no initial snapshot — the same "no state on connect" gap also applies to reconnects after a drop, compounding the UX issue ("Waiting for telemetry..." reappearing on every reconnect).

**How to avoid:**
- Create the `EventSource` exactly once per mount, inside a `useEffect` with an empty dependency array (or a ref-guarded singleton), and always call `.close()` in the cleanup function.
- On the backend, send a full-snapshot event immediately when a client connects (already recommended in `CONCERNS.md`) — this also naturally covers the reconnect case since `EventSource` reconnecting is indistinguishable from a fresh connect from the server's perspective unless `Last-Event-ID` is used.
- Surface the existing connection-status indicator (green/yellow/red, already in PLAN.md's design) as the visible signal for reconnect state — wire it to `EventSource.onerror`/`onopen`, not just a one-time "connected" flag at mount.
- Test reconnection explicitly: kill the backend process (or block the port) while an E2E test is watching an `EventSource`, verify the indicator turns red/yellow, then unblock and verify it turns green and telemetry resumes — this is already listed as an untested E2E scenario in `CONCERNS.md`.

**Warning signs:**
- Battery-flash animations fire twice per tick, or sparklines show duplicate/jittery points — a symptom of multiple open `EventSource` connections to the same endpoint.
- Browser devtools Network tab shows more than one pending `eventsource` request to `/api/stream/telemetry` from a single tab.
- Connection indicator never changes color during a manual network-drop test.

**Phase to address:**
Frontend phase (SSE consumption) for the connection-lifecycle bug; backend fleet/telemetry-adjacent work for the snapshot-on-connect fix (small, can ride along with roster/fleet endpoints since it touches `telemetry/stream.py`).

---

### Pitfall 6: Next.js static export served by FastAPI breaks client-side routes and API/static path collisions

**What goes wrong:**
`output: 'export'` produces a directory of pre-rendered HTML files (e.g. `out/index.html`, `out/some-route.html` or `out/some-route/index.html` depending on `trailingSlash`). If FastAPI's static-file mount doesn't account for this, two things commonly break: (1) a hard refresh or direct navigation to any non-root client route 404s, because FastAPI's `StaticFiles` serves exact file paths and doesn't automatically fall back to `index.html` for SPA-style routes; (2) if API routes (`/api/*`) and the static mount are registered in the wrong order, or the static mount is a catch-all (`/{path:path}`) registered before the API router, static serving can shadow `/api/*` and return HTML instead of JSON (or vice versa, `/api/*` could shadow legitimately named static assets if a route were ever named `api`).
Additionally, `output: 'export'` disables Next.js Image Optimization, dynamic `middleware.ts`, and any API routes defined inside the Next app itself — a implementer used to a normal Next.js dev workflow can accidentally use one of these and only discover the failure at `npm run build` time (build fails or silently produces a broken export), not at dev time.

**Why it happens:**
Static export is a fundamentally different serving model than `next dev`/`next start` (no Next.js server, no server-side routing fallback) — features that "just work" in dev mode (route params served by the Next server, image optimization, middleware) require an actual Next.js server process and are incompatible with static export. This mismatch surfaces late (at build or at first production-like test) unless it's explicitly tested earlier.

**How to avoid:**
- Register the FastAPI API router (`/api/*`) before mounting static files, and use a catch-all static handler that falls back to `out/index.html` for any path that doesn't match a real file — this is the standard SPA-on-a-generic-server pattern and is required for any client-side route (e.g. a drone-detail deep link, if ever added) to survive a hard refresh.
- Since this app has a single dashboard route (per PLAN.md, no listed sub-routes), keep routing simple — serve `index.html` for `/` and treat `/api/*` as fully reserved; still add the `test -f static/index.html` build-verification step already recommended in `CONCERNS.md` ("Docker Build Doesn't Verify Frontend Output Exists") so a broken/empty export fails the build loudly instead of shipping a blank screen.
- Decide `trailingSlash` explicitly (rather than leaving default) and make sure FastAPI's static mount matches whichever file-naming convention (`route.html` vs `route/index.html`) the export actually produces.
- Do not use Next.js Image (`next/image` optimization), `middleware.ts`, or Next API routes anywhere in the frontend — confirm this constraint early (frontend phase kickoff), since discovering it at Docker-build time wastes a full build cycle.

**Warning signs:**
- `npm run build` succeeds but `out/` is missing expected files, or the Docker build's `COPY` step copies nothing (silent, per existing `CONCERNS.md` finding) and the container serves a blank page.
- Hard-refreshing any non-root URL in the running container returns FastAPI's default 404 instead of the app shell.
- `/api/*` calls return HTML (the SPA shell) instead of JSON — a sign the static catch-all is intercepting API paths.

**Phase to address:**
Docker packaging phase (multi-stage build + single-port serving) — should include the build-verification step and an explicit route-fallback test as acceptance criteria, not just "container starts."

---

### Pitfall 7: Budget/mission state drifts from what the UI shows because updates aren't atomic with the read path

**What goes wrong:**
The header shows "remaining energy budget (updating live)" and the missions table shows current state. If the budget figure is computed by summing `mission_log`/`missions` on every read rather than being stored and updated atomically alongside each launch/recall, concurrent launches (manual + LLM-driven) can produce a UI that briefly shows a budget inconsistent with what was actually committed, or a missions table that doesn't match the header's active-mission count — especially since `budget_snapshots` are only recorded every 30s plus immediately after launch/recall per PLAN.md, creating a window where the live header figure and the historical chart disagree.

**Why it happens:**
It's tempting to treat `operator_profile.energy_budget_kwh` as the single live number and `budget_snapshots` as "just history," but if the two update paths (the live decrement on launch vs. the periodic snapshot insert) aren't both wrapped in the same transaction/lock discipline as Pitfall 1's fix, they can observe different states under concurrency.

**How to avoid:**
- Treat `operator_profile.energy_budget_kwh` as the single source of truth; `budget_snapshots` rows are always derived from it, written in the same transaction/lock scope as the mutation that changed it (immediately after launch/recall) rather than computed independently later.
- Return the updated budget value directly in the launch/recall API response (not just a 200 OK) so the frontend can update optimistically from the mutation response rather than waiting for a separate poll/snapshot — reduces the window where UI and DB can visibly disagree.

**Warning signs:**
- Energy-budget chart's last point doesn't match the header's live number after a launch.
- Two browser tabs open simultaneously show different budget values for more than a second or two after one tab launches a mission.

**Phase to address:**
Fleet operations phase (mission energy-budget accounting) — same phase as Pitfall 1, since both stem from the same atomicity discipline.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|------------------|
| Single global `asyncio.Lock` serializing all DB ops (already in place) | Simple, guarantees atomicity without a real transaction API | Throughput ceiling (~10-20 writes/sec per existing `CONCERNS.md` estimate); every request waits on every other | Acceptable for this project's scale (single operator, 10 drones) — do not "fix" by removing the lock without adding real transactions |
| Separate "trusted" execution path for LLM-issued actions vs. manual dispatch | Faster to build, fewer shared dependencies to wire up | Two divergent validation code paths that will drift and let bad LLM actions through (see Pitfall 3) | Never acceptable — always share the validation/execution function |
| Lazy DB init triggered by first request handler instead of app startup | Marginally simpler mental model ("nothing runs until something asks for it") | Race condition on cold start under concurrent first requests (Pitfall 2) | Only acceptable if wrapped in the same lock used for writes; prefer startup-event init instead |
| Skipping malformed-LLM-response tests because `LLM_MOCK` only covers happy-path scenarios | Faster to ship chat feature | Production 500s or silently-executed garbage actions the first time the real model misbehaves (Pitfall 4) | Never acceptable for this feature — mock mode should include at least one adversarial case |
| Polling `/api/fleet` from the frontend instead of trusting SSE + mutation responses for budget updates | Simpler frontend state management | Extra load, and the polled value can lag behind or briefly contradict the SSE-driven view | Acceptable for missions table (low-frequency) but not for the live budget header — use the mutation response directly there |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|------------------|-------------------|
| LiteLLM → OpenRouter → Cerebras (`gpt-oss-120b`) structured outputs | Trusting "matches schema" as full validation; not handling provider-side truncation/timeout | Re-validate every field's business meaning (Pitfall 3), wrap parsing in try/except with graceful fallback (Pitfall 4), and set an explicit request timeout so a slow/hung Cerebras call doesn't hang the whole chat request indefinitely |
| `EventSource` (native browser API) | Recreating the connection on every re-render; no `onerror` handling wired to the UI indicator | Single stable connection per mount with cleanup; wire `onopen`/`onerror` to the existing green/yellow/red status dot |
| Next.js static export → FastAPI `StaticFiles` | Assuming Next's dev-mode routing behavior (server fallback, image optimization) carries over to static export | Explicit catch-all fallback to `index.html`, verified build-output check, no `next/image` optimization or middleware anywhere in the frontend |
| SQLite (`aiosqlite` or equivalent) under FastAPI async | Assuming `async def` automatically means safe concurrent writes | SQLite is single-writer regardless of async framework; the existing lock-serialization approach is required, not optional — don't bypass it "for performance" without moving to a real multi-writer DB first |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Global DB lock serializing every request | Latency creeps up under load; feels fine in manual testing, degrades in E2E test suite with parallel requests | Keep transactions short (no LLM calls or slow work while holding the write lock); measure with a concurrency-focused test, not just sequential manual testing | ~100+ concurrent clients or high mission-launch frequency (already documented in `CONCERNS.md`) |
| SSE broadcasting full fleet state to every client every tick (already noted in `CONCERNS.md`) | Bandwidth grows with client count × drone count; not visible with 1 operator tab | Acceptable at this project's scale (single operator); don't add per-drone filtering unless roster/operator count actually grows | Documented existing limit: becomes visible at 100+ simultaneous clients or 1000+ drones |
| Computing budget/mission aggregates by scanning `mission_log` on every API read instead of maintaining `operator_profile.energy_budget_kwh` as the live counter | Fleet/budget endpoint latency grows with mission history size over a long-running demo session | Keep `energy_budget_kwh` as an incrementally maintained counter (Pitfall 7), only use `mission_log` for historical/audit views | Long-running deployments (weeks) with many mission launches accumulated in `mission_log` |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| LLM auto-executes mutations with zero confirmation and zero authentication in front of the app (per PLAN.md's explicit design + `CONCERNS.md`'s "Missing Authentication" finding) | Anyone with network access to port 8000 can drain the budget or spam mission launches via the chat endpoint, no different from the REST endpoints but now reachable via natural language / prompt injection if chat history or fleet-context text is ever attacker-influenced | Confirm this app stays on trusted/local networks only (already the documented mitigation); do not add any feature that ingests untrusted free text into the LLM context (e.g. no drone-supplied "notes" field flowing into the chat prompt) without treating it as untrusted input |
| Logging LLM request/response bodies at DEBUG for troubleshooting (flagged generically in `CONCERNS.md`) | `OPENROUTER_API_KEY` or full prompt/response bodies (which could include fleet operational data) end up in container logs | Explicitly scrub Authorization headers from any httpx/LiteLLM debug logging; keep default log level at INFO in production images |
| Treating LLM-provided `zone` strings as safe to interpolate directly into anything downstream (SQL, shell, file paths) | Even though current schema treats `zone` as a plain text column with parameterized queries, a future feature that generates reports/exports from `zone` text without escaping could be injectable | Always use parameterized queries for LLM-sourced field values (should already be true given SQLite driver usage) and validate `zone` against a known enum server-side (Pitfall 3) rather than accepting arbitrary text |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| No snapshot on SSE (re)connect (existing `CONCERNS.md` finding, also Pitfall 5) | Dispatcher sees "Waiting for telemetry..." on every page load and every reconnect, even though the server has known-good recent data | Send a full-snapshot event immediately on connect/reconnect from the cached latest reading per drone |
| LLM chat auto-executes with no confirmation and no undo | A misunderstood or ambiguous operator request ("recall the low ones") could launch/recall drones the operator didn't intend, with no dialog to catch it before it happens (deliberate per PLAN.md, but still a real UX risk) | Make the `message` response always narrate exactly what was executed (drone IDs, zones, costs) so the operator can immediately see and manually reverse (recall/re-launch) if the AI misunderstood — treat the chat's own summary as the "confirmation," shown after the fact rather than before |
| Budget shown as decreasing but missions table not yet updated (race between two data sources updating at different times) | Dispatcher briefly sees inconsistent numbers and may distrust the UI | Update budget optimistically from the mutation response, not from a separate poll (Pitfall 7) |
| Chat gives no visible feedback while waiting for Cerebras (PLAN.md notes "a loading indicator is sufficient" since no token streaming) | If the loading indicator is missing or the request silently hangs on a slow/timed-out LLM call, the operator has no idea whether their message was received | Enforce an explicit request timeout on the LiteLLM call and show a clear "flight director is thinking" state tied to the actual in-flight request, with a timeout-triggered error message if it takes too long |

## "Looks Done But Isn't" Checklist

- [ ] **Mission launch/recall endpoints:** Often missing the atomic check-and-write guarantee — verify with a concurrency test (`asyncio.gather` of two simultaneous launches) that only one succeeds when budget/drone-availability allows exactly one, not just sequential manual testing.
- [ ] **SQLite lazy init:** Often "works" in single-request manual testing but races under concurrent cold-start requests — verify by hitting several endpoints in parallel immediately after a fresh `docker run` with no existing `database/skyfleet.db`.
- [ ] **LLM chat mission dispatch:** Often only tested with well-formed mock responses — verify with at least one `LLM_MOCK` scenario returning an invalid `drone_id`, negative `distance_km`, and malformed JSON, asserting graceful rejection not a crash or silent bad-write.
- [ ] **SSE telemetry stream:** Often only tested as "connects and shows data" — verify reconnection behavior explicitly (kill/restart the backend or block the port mid-session) and confirm the connection-status indicator reflects it and a snapshot arrives on reconnect.
- [ ] **Docker single-port serving:** Often only tested by loading `/` once — verify a hard refresh works, `/api/*` isn't shadowed by the static catch-all, and the build fails loudly (not silently) if `frontend/out/` is missing or empty.
- [ ] **Energy-budget chart vs. live header:** Often built against two different data sources — verify they agree immediately after a launch/recall, not just eventually after the next 30s snapshot.
- [ ] **Roster removal during active operations:** Often only tested with a static 10-drone roster (as `CONCERNS.md` already notes for eligibility checks) — verify removing a drone that has an active mission, or removing a drone mid-auto-assignment, doesn't crash or corrupt state.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| Budget overdrawn from a race condition | LOW | Since this is a demo with no real money, reset `operator_profile.energy_budget_kwh` to the default (500.0) via a manual `UPDATE` or a documented reset script; fix the underlying atomicity bug before it recurs |
| Duplicate seed data from an init race | LOW | Delete the SQLite file and restart (fresh volume) during development; in a shipped container, add a startup check that de-duplicates `fleet_roster` on the unique `(operator_id, drone_id)` constraint already specified in the schema |
| LLM executed a bad mission via hallucinated params | LOW | Manual recall via the existing `DELETE /api/fleet/missions/{drone_id}` endpoint; since launches are atomic with no partial state (per PLAN.md's design), recovery is just "recall the drone," not a multi-step rollback |
| Frontend served blank due to missing static export in Docker build | MEDIUM | Rebuild with the `test -d/-f` verification step added (already recommended in `CONCERNS.md`); no data loss since this is a build-time failure, not a runtime data issue |
| SSE stuck showing stale data after a network blip | LOW | The connection-status indicator plus a manual page refresh recovers the user; fixing the reconnect/snapshot behavior (Pitfall 5) removes the need for manual refresh going forward |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| Budget/drone-eligibility race conditions (Pitfall 1, 7) | Fleet operations / mission dispatch phase | Concurrency test: two simultaneous launch requests via `asyncio.gather`, assert exactly one succeeds when budget allows one; assert budget never goes negative |
| SQLite lazy-init race (Pitfall 2) | Database layer phase | Startup-time init (not per-request) or lock-guarded lazy init; test by firing concurrent requests immediately after deleting the DB file |
| LLM hallucinated/invalid action auto-executed (Pitfall 3) | LLM chat integration phase | Test with mocked LLM response containing an unknown `drone_id`/negative `distance_km`; assert it's rejected via the same validation path as manual dispatch, with the error surfaced in the chat reply |
| Malformed/truncated LLM response crashes chat (Pitfall 4) | LLM chat integration phase | Test with mocked malformed JSON response; assert a 200 with a graceful fallback message, not a 500 |
| EventSource connection leaks / no reconnect snapshot (Pitfall 5) | Frontend phase (SSE) + backend telemetry-stream touch-up | E2E test: block/unblock the backend mid-session, assert indicator changes and a snapshot arrives without a page reload |
| Static export + FastAPI serving gotchas (Pitfall 6) | Docker packaging phase | Build-verification step (`test -f static/index.html`) in the Dockerfile; container smoke test hitting `/`, a hard refresh path, and `/api/health` to confirm no shadowing |

## Sources

- `.planning/codebase/CONCERNS.md` (2026-08-12 codebase audit) — HIGH confidence, curated first-party source; several pitfalls above (drone-eligibility race, SSE late-subscriber gap, Docker build silent failure, SQLite write-throughput ceiling) are directly sourced from this existing analysis and extended to the new mutating-action surfaces being built.
- `planning/PLAN.md` — HIGH confidence, project's own specification; used to confirm the deliberate no-confirmation-dialog design for LLM actions and the "same validation as manual dispatch" requirement.
- [Next.js: Static Exports guide](https://nextjs.org/docs/pages/guides/static-exports) — MEDIUM/HIGH confidence, official docs; confirms `output: 'export'` limitations (no Image Optimization, no middleware, no dynamic API routes).
- [Next.js: `trailingSlash` config reference](https://nextjs.org/docs/app/api-reference/config/next-config-js/trailingSlash) — HIGH confidence, official docs; confirms file-naming behavior (`route/index.html` vs `route.html`) that a static-file server must match.
- [vercel/next.js issue #68215 — static export + trailingSlash routing bug](https://github.com/vercel/next.js/issues/68215) — MEDIUM confidence, community-reported issue; illustrates that export routing conventions have had real edge-case bugs, reinforcing the need for an explicit build-verification/smoke-test step.
- [aiosqlite issue #251 — "Database is Locked" even with timeout set](https://github.com/omnilib/aiosqlite/issues/251) — MEDIUM confidence, community-reported issue; corroborates that SQLite concurrency issues persist even with timeout/WAL configuration if the app-level locking discipline isn't also correct.
- [tenthousandmeters.com — SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) — MEDIUM confidence, well-regarded technical blog; corroborates WAL mode + busy_timeout as the standard mitigation, consistent with what's already configured in this codebase.
- MDN / general web-platform knowledge on `EventSource` reconnection and `Last-Event-ID` semantics — HIGH confidence, standard browser behavior; corroborated by FastAPI SSE tutorial search results confirming `Last-Event-ID` header handling patterns.
- [giskard.ai — Function calling in LLMs: Testing agent tool usage for AI Security](https://www.giskard.ai/knowledge/function-calling-in-llms-testing-agent-tool-usage-for-ai-security) — MEDIUM confidence, vendor knowledge-base article; corroborates the five recurring LLM function-calling failure modes (invalid JSON, hallucinated tool/param names, missing/mis-typed params, prompt injection) cited in Pitfalls 3–4.
- Roborhythms — "Fix Agent Tool Hallucinations With a 4-Section Prompt" — LOW/MEDIUM confidence, independent practitioner blog; cited only for the general observation that even well-prompted agents hallucinate parameters at a non-zero rate, reinforcing that server-side validation (not prompting alone) is the required safety net.

---
*Pitfalls research for: Real-time drone-delivery ops console (SkyFleet Ops) — database, mission/budget, LLM chat, frontend SSE, Docker packaging milestone*
*Researched: 2026-08-12*
