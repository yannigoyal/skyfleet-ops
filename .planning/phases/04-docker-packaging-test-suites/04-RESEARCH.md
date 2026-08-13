# Phase 4: Docker Packaging & Test Suites - Research

**Researched:** 2026-08-14
**Domain:** Docker packaging (multi-stage build, bind-mount persistence, idempotent scripts) + test-suite hardening (pytest, Vitest, Playwright E2E)
**Confidence:** HIGH

## Summary

This phase is verification and gap-closure, not new construction. Every artifact CONTEXT.md
references was read directly this session: the Dockerfile, docker-compose files, all four
start/stop scripts, the E2E harness (`docker-compose.test.yml`, `playwright.config.ts`,
`health.spec.ts`), all 23 backend pytest files, and all 14 frontend Vitest files. The backend
suite was executed live: **300 passed, 6 skipped, 3 deselected** (the `live` marker tests,
excluded by `pyproject.toml`'s `addopts = "-m 'not live'"`). The frontend suite was executed
live: **81 passed, 14 test files**. Both numbers match CONTEXT.md's D-02 claim exactly — now
independently verified rather than assumed.

Most importantly, a **live Docker container is currently running** (`skyfleet-ops`, started
2026-08-13T17:13:57Z, healthy) using the named volume `skyfleet-data`, which holds a real
non-empty database: 9 roster rows (not the default 10 — a drone was removed at some point) and 4
`mission_log` entries. This makes D-01's "costly reversibility" concern concrete rather than
hypothetical — there is live state that a bind-mount cutover will orphan unless migrated. This
research documents a verified, safe migration path (checkpoint + `docker cp`, executed against
the actual running container) as well as the simpler "accept a reset" alternative, so the planner
can choose without re-deriving the mechanics.

D-04's smoke-test framing was also verified against the running container, not just the source:
`curl http://localhost:8000/` inside the container returns `200`, `/api/health` returns `200`,
and `/app/static/` contains `index.html`, `404.html`, `_next/`, confirming FastAPI's
`StaticFiles(directory=_static_dir, html=True)` mount (`backend/app/main.py:96-97`) serves the
Next export correctly today, before any phase-4 changes.

For TEST-04's new Playwright specs, this research also extracted every DOM selector, CSS class,
`data-testid`, status-label mapping, and mock-chat trigger keyword actually present in the
frontend/backend source — not reconstructed from memory — so the planner can hand the executor
concrete locators instead of "add appropriate selectors."

**Primary recommendation:** Treat this phase as an audit-and-patch pass across four independent
surfaces (Docker volume config, Docker verification, backend/frontend unit-test gap-fill, new E2E
specs) — each can be planned and executed with minimal risk of touching the others, since none of
the four decisions in CONTEXT.md depend on the others being done first except that E2E specs need
the (already-existing) Dockerfile to build successfully.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Multi-stage image build (DEPLOY-01) | Build/CI (Docker) | — | Pure packaging; no application-layer changes |
| Bind-mount persistence (DEPLOY-04) | Docker / Host filesystem | Database (SQLite) | Volume config lives in `docker-compose.yml`/scripts, not app code; app already reads path via `DATABASE_PATH`/ancestor-search fallback (`backend/app/main.py:30-47`) |
| Idempotent start/stop scripts (DEPLOY-02/03) | Host shell/PowerShell | Docker CLI | Scripts orchestrate `docker build`/`run`/`rm`; no new backend or frontend code |
| Backend unit-test coverage (TEST-01/02) | Backend (pytest) | — | Tests exercise `roster/` and `chat/` service/repository/router layers already built in Phases 1-2 |
| Frontend unit-test coverage (TEST-03) | Frontend (Vitest) | — | Tests exercise components already built in Phase 3 |
| E2E suite (TEST-04) | Browser (Playwright) driving the full container | API / Backend | Playwright's `request` fixture hits `/api/*` directly for setup/assertions; `page` drives the real static-served frontend |
| Playwright isolation (TEST-05) | Docker Compose (test-only) | — | `tests/docker-compose.test.yml` already isolates browser deps from the production image; reuse as-is |

## User Constraints

<user_constraints>
### Locked Decisions

**D-01 — Docker Volume Strategy:** `docker/docker-compose.yml` and `scripts/start_mac.sh`
currently mount a named Docker volume (`skyfleet-data:/app/database`), but PLAN.md §11 and
DEPLOY-04's requirement text both specify a bind mount of the host's `database/` directory
(`-v $(pwd)/database:/app/database`) so the operator can inspect/back up `skyfleet.db` directly.
**Decision: switch to the bind mount to match spec.** Update `docker/docker-compose.yml`,
`scripts/start_mac.sh`, and `scripts/start_windows.ps1` accordingly. Reversibility: costly —
a named volume already holds this project's `skyfleet.db`; switching to a bind mount means either
a documented one-time data migration step or accepting a fresh database at cutover. Flag this for
the planner to address explicitly (migration note or accepted reset).

**D-02 — Existing Unit Test Coverage:** Backend already has ~300 passing pytest tests (full
`roster/` and `chat/` suites included) and frontend already has 81 passing Vitest tests — all
built during Phases 1-3. TEST-01/02/03 are marked "Pending" in REQUIREMENTS.md but are likely
substantially already satisfied. **Decision: audit for gaps against TEST-01/02/03's exact
wording, do not rewrite existing suites.** Add only what's missing; mark the requirement
satisfied by the existing suite plus any gap-fill work.

**D-03 — E2E Assertion Depth:** TEST-04 lists 6 scenarios. Only a health-check placeholder
(`tests/specs/health.spec.ts`) exists today. **Decision: use structural DOM/data assertions for
the "visualization rendering" scenario** (e.g., correct number of treemap cells, chart has data
points, sparkline renders) — not pixel-level screenshot comparisons, to avoid flaky
cross-environment visual diffs.

**D-04 — Static Export / StaticFiles Serving Risk:** Next.js static-export + FastAPI's
`StaticFiles` serving has edge cases around `trailingSlash` routing and 404/fallback behavior.
`frontend/next.config.js` does not set `trailingSlash` (defaults to `false`). This is a
single-page app (one route only). **Decision: smoke-test only** — the "fresh start" TEST-04 E2E
scenario (build → container start → `GET /`) is sufficient verification; dedicated
deep-link/refresh/404-fallback tests are not required given there's only one route to serve.

### Claude's Discretion

- `backend/app/demo/mission_demo.py` (untracked, hand-written Rich-based terminal demo of the
  mission scheduler) — not discussed in depth; leave untouched unless it conflicts with phase
  work. Not part of DEPLOY/TEST requirements.
- Windows script (`start_windows.ps1`/`stop_windows.ps1`) verification depth — no Windows runner
  available in this environment; verify by code review against the bash equivalents' logic
  (idempotency checks, bind-mount update per D-01) rather than live execution.
- Exact SQL/file changes needed to migrate the named-volume database to the new bind mount (D-01)
  — planner/executor to determine the concrete migration or reset approach.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. `backend/app/demo/mission_demo.py`'s disposition was
raised but resolved as Claude's Discretion (leave as-is), not deferred to another phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-01 | Multi-stage Dockerfile builds Next export + FastAPI into one image on port 8000 | `docker/Dockerfile` verified [VERIFIED: docker/Dockerfile:1-25] — already matches this shape; verification steps below (build + run + smoke test) close the gap between "exists" and "verified working" |
| DEPLOY-02 | `start_mac.sh`/`stop_mac.sh` idempotent, build/run/stop with volume mount + `.env` | Scripts read and verified idempotent (`docker image inspect`, `docker ps -a` guards) [VERIFIED: scripts/start_mac.sh:1-45]; only the `-v` line needs the D-01 bind-mount edit |
| DEPLOY-03 | `start_windows.ps1`/`stop_windows.ps1` PowerShell equivalents, idempotent | Scripts read, logic mirrors bash 1:1 [VERIFIED: scripts/start_windows.ps1:1-38]; same single-line D-01 edit needed |
| DEPLOY-04 | SQLite persists across restarts via `database/` bind mount | Live evidence gathered: a named-volume container is currently running with real data (9 roster rows, 4 mission_log rows) — migration approach documented below |
| TEST-01 | Backend unit tests cover roster service/repository/router | `backend/tests/roster/{test_models,test_repository,test_router,test_service}.py` exist and pass — audit checklist below |
| TEST-02 | Backend unit tests cover chat/LLM structured-output parsing, malformed-response handling, mission/roster validation in chat flow | `backend/tests/chat/test_llm.py::test_malformed_completions_raise_llm_error` and 8 others confirmed present and passing [VERIFIED: backend/tests/chat/test_llm.py:137] |
| TEST-03 | Frontend unit tests cover detail panel, heatmap, budget chart, missions table, dispatch bar, chat panel | All 6 named `*.test.tsx` files confirmed present and passing |
| TEST-04 | Playwright E2E: fresh start, roster add/remove, launch/recall+budget, visualization, mocked chat, SSE reconnect | Only `health.spec.ts` exists; concrete selectors/mock triggers for all 6 scenarios extracted below |
| TEST-05 | `tests/docker-compose.test.yml` isolates Playwright container from prod image | Verified — file already correct, healthcheck + `LLM_MOCK=true` wired [VERIFIED: tests/docker-compose.test.yml:1-21] |
</phase_requirements>

## Standard Stack

No new external packages are required by this phase — every dependency (pytest, Vitest,
Playwright `@playwright/test ^1.48.0`, Docker, Docker Compose) is already installed and pinned.
This phase edits existing config/scripts and adds test files against already-present frameworks.

### Core (already present, verified)
| Tool | Version (verified) | Purpose |
|------|---------------------|---------|
| Docker | 29.6.1 [VERIFIED: `docker --version` this session] | Container build/run |
| Docker Compose | v5.2.0 [VERIFIED: `docker compose version` this session] | Test harness orchestration |
| `@playwright/test` | `^1.48.0` in `tests/package.json` [VERIFIED: tests/package.json:10] | E2E framework |
| Playwright browser image | `mcr.microsoft.com/playwright:v1.48.0-jammy` [VERIFIED: tests/docker-compose.test.yml:16] | Isolated E2E browser container |
| pytest | `>=8.3.0` in `backend/pyproject.toml` [VERIFIED: backend/pyproject.toml:16] | Backend unit tests |
| Vitest | `^2.1.0` in `frontend/package.json` [VERIFIED: frontend/package.json:22] | Frontend unit tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `docker cp` + WAL checkpoint migration (D-01) | Accept a fresh/reset database on bind-mount cutover | Migration preserves the 9-drone/4-mission state already in the named volume; reset is simpler and matches "no manual migration step, lazy seed" philosophy in PLAN.md §7 — either is valid, see below |
| Structural DOM assertions for visualization (D-03, already locked) | `toHaveScreenshot()` pixel diffs | Locked out by D-03 — cross-environment font/GPU rendering makes screenshot diffs flaky in CI |
| `context.route().abort()` for SSE disconnect simulation | `context.setOffline(true/false)` | `setOffline` is simpler but also kills the 5s fleet-poll and 5s budget-history poll (`FleetOpsProvider.tsx:25`, `EnergyBudgetChart.tsx:23`) during the same window, adding console noise unrelated to the SSE assertion; `route()` scoped to `**/api/stream/telemetry` isolates the failure to exactly the connection under test |

**Installation:** None — no new packages to install for this phase.

## Package Legitimacy Audit

**Not applicable.** This phase installs no new external packages in any ecosystem. All frameworks
used (pytest, Vitest, Playwright, Docker) are pre-existing pinned dependencies verified above.

## Docker Verification Findings (live evidence, this session)

A container named `skyfleet-ops` was found already running (`docker ps -a`, sandbox disabled to
reach the Docker socket): image `skyfleet-ops:latest`, started 2026-08-13T17:13:57Z, status
`Up ... (healthy)`, using named volume `skyfleet-data` mounted at `/app/database`
[VERIFIED: `docker volume inspect skyfleet-data` this session — Mountpoint
`/var/lib/docker/volumes/skyfleet-data/_data`].

Contents of that volume's database, queried live via `docker exec skyfleet-ops python3`:
```
tables: [('operator_profile',), ('fleet_roster',), ('missions',), ('mission_log',), ('budget_snapshots',), ('chat_messages',)]
roster rows: 9   (default seed is 10 — one drone was removed at some point)
mission_log rows: 4
```
This directly confirms D-01's premise is not hypothetical: switching `docker-compose.yml` and
`scripts/start_mac.sh`/`start_windows.ps1` from the named volume to a bind mount, as currently
written, will orphan this data (the new bind-mounted `database/skyfleet.db` starts empty and gets
lazily re-seeded to the *default* 10-drone roster, silently discarding the current 9-drone/4-mission
state).

Static-file serving smoke test (D-04), run against the *same live container*:
```
GET /              -> 200
GET /api/health    -> 200
/app/static/ contains: 404.html, _next/, index.html, index.txt
```
This confirms `StaticFiles(directory=_static_dir, html=True)` [VERIFIED: backend/app/main.py:95-97]
correctly serves the Next.js export today. No code change is needed for DEPLOY-01/D-04 — only
verification-as-a-task (rebuild after any phase-4 edits, re-run this smoke test) is required.

### Named-volume → bind-mount migration options (for the planner to choose one)

**Option A — Preserve existing data (documented migration step).** SQLite in WAL mode needs a
checkpoint before the on-disk `.db` file alone reflects all committed data; the safe pattern is to
checkpoint, then copy while no writer holds the file [CITED: community SQLite guidance —
`github.com/simonw/til` WAL notes, `github.com/superfly/sqlite3-restore`, `pypi.org/project/sqlite-backup`
— see Sources]:
```bash
# 1. Checkpoint and truncate the WAL so skyfleet.db alone is authoritative
docker exec skyfleet-ops python3 -c \
  "import sqlite3; sqlite3.connect('/app/database/skyfleet.db').execute('PRAGMA wal_checkpoint(TRUNCATE)')"

# 2. Stop the container so no connection can reopen the WAL mid-copy
docker stop skyfleet-ops

# 3. Copy the checkpointed file out of the named volume into the new bind-mount target
mkdir -p database
docker run --rm -v skyfleet-data:/from -v "$(pwd)/database":/to alpine \
  sh -c "cp /from/skyfleet.db /to/skyfleet.db"

# 4. Remove the now-unused named volume (optional cleanup)
docker volume rm skyfleet-data
```
This is a one-time, operator-run step — not something the app or start script needs to run
automatically. Document it in a `MIGRATION.md` note or a `--migrate-volume` flag on
`start_mac.sh`, per planner's judgment.

**Option B — Accept a reset at cutover (simpler, matches "lazy init" philosophy).** PLAN.md §7
explicitly designs the schema for lazy creation and default seeding with "no separate migration
step... no manual database setup." Given this is a demo/capstone app with `operator_id="default"`
single-tenant data (not real operational history), accepting a fresh bind-mounted database and
documenting it in the script output ("Note: switching to bind-mount storage — starting with a
fresh seeded database") is consistent with the project's stated simplicity preference (project
CLAUDE.md: "Be simple," "Do not over-engineer"). **Recommendation: Option B, unless the user
explicitly wants the current 9-drone test state preserved** — the data in the volume right now is
itself just exploratory/test data from an earlier manual run, not a real operator's fleet history.

Either way, `scripts/stop_mac.sh`/`stop_windows.ps1` already do not touch the volume/bind-mount
directory (only `docker rm -f` the container) [VERIFIED: scripts/stop_mac.sh:1-11] — no change
needed there.

## Architecture Patterns

### System Architecture Diagram

```
Operator's machine
  │
  │ scripts/start_mac.sh (or start_windows.ps1)
  │   1. checks .env exists
  │   2. docker build (if image missing or --build) ──► docker/Dockerfile
  │   3. docker rm -f any existing "skyfleet-ops" container (idempotent)
  │   4. docker run -d -v $(pwd)/database:/app/database -p 8000:8000 --env-file .env
  ▼
Docker container "skyfleet-ops" (port 8000)
  ├── FastAPI app (uvicorn) ── serves /api/* AND static / (Next export)
  ├── SQLite file at /app/database/skyfleet.db ── bind-mounted to host database/
  └── Background tasks: telemetry sim, mission schedulers, budget snapshots
  │
  ▼
Browser (operator) ── GET / (static index.html) ── EventSource /api/stream/telemetry
                                                  ── fetch /api/roster, /api/fleet, /api/chat

─────────────────────────────────────────────────────────────────
tests/docker-compose.test.yml (separate, test-only compose file)
  ├── service "app": same Dockerfile, env LLM_MOCK=true, healthcheck on /api/health
  └── service "playwright": mcr.microsoft.com/playwright image, depends_on app healthy,
        runs `npm install && npx playwright test` against BASE_URL=http://app:8000
```

### Recommended Project Structure (no new directories needed)
```
docker/
├── Dockerfile                 # unchanged — already correct (verified)
└── docker-compose.yml         # D-01 edit: named volume -> bind mount
scripts/
├── start_mac.sh                # D-01 edit: named volume -> bind mount
├── stop_mac.sh                 # unchanged — already correct
├── start_windows.ps1            # D-01 edit: named volume -> bind mount
└── stop_windows.ps1             # unchanged — already correct
backend/tests/{roster,chat}/     # audit for TEST-01/02 gaps, add only what's missing
frontend/src/**/*.test.tsx       # audit for TEST-03 gaps, add only what's missing
tests/specs/
├── health.spec.ts               # existing, unchanged
├── fresh-start.spec.ts          # new — TEST-04 scenario 1
├── roster.spec.ts               # new — TEST-04 scenario 2
├── missions.spec.ts             # new — TEST-04 scenario 3 (launch/recall + budget)
├── visualization.spec.ts        # new — TEST-04 scenario 4 (structural assertions per D-03)
├── chat.spec.ts                 # new — TEST-04 scenario 5 (mocked)
└── sse-resilience.spec.ts       # new — TEST-04 scenario 6
```

### Pattern 1: Playwright direct-API setup + UI-observed assertion (roster add/remove)
**What:** There is no manual "Add Drone" / "Remove Drone" UI control anywhere in the frontend —
confirmed by grepping every `.tsx` in `frontend/src/` for roster-mutation call sites: the only
`fetch("/api/roster")` call is a `GET` inside `FleetOpsProvider.tsx` used to populate the
`DispatchBar`'s drone `<select>`. `ROST-01`/`ROST-02` (`POST`/`DELETE /api/roster/*`) are reachable
only via direct API call or via the AI chat's `roster_changes` action (`CHAT-04`) — never a
dedicated manual UI. This matches the PLAN.md vision text ("manually or via the AI chat") loosely,
but "manually" in the shipped app means "via curl/API," not "via a button."
**When to use:** For TEST-04's roster add/remove scenario, drive the mutation through Playwright's
`request` fixture (same pattern as `health.spec.ts`) and assert the *effect* in the UI: the new
drone's row appears in `FleetRosterPanel` (added to the live telemetry snapshot, since
`roster.service.add_drone` registers the drone with the telemetry source) and in the `DispatchBar`
drone `<select>` (after `FleetOpsProvider`'s 5s poll or a `page.reload()`).
**Example:**
```typescript
// Source: pattern extends tests/specs/health.spec.ts (verified in-repo)
test("adding a drone appears in the roster panel", async ({ page, request }) => {
  const res = await request.post("/api/roster", { data: { drone_id: "FALCON-11" } });
  expect(res.status()).toBe(201);
  await page.goto("/");
  await expect(page.getByText("FALCON-11")).toBeVisible({ timeout: 10_000 });
});
```

### Pattern 2: Concrete frontend selectors (extracted from source, not invented)
**What:** Most components have no `data-testid`; only `chat-panel`, `chat-loading`, and
`confirmation-card` do [VERIFIED: frontend/src/components/chat/ChatPanel.tsx:70,115 and
frontend/src/components/chat/ConfirmationCard.tsx:41,59 — `data-testid="chat-panel"`,
`data-testid="chat-loading"`, `data-testid="confirmation-card"`]. Everything else must be located
by visible text, table structure, or class name, extracted below verbatim from source:

| Element | Selector strategy | Verified source |
|---|---|---|
| Roster panel header | text `"Fleet Roster"` | FleetRosterPanel.tsx:33 |
| Roster row | `<tr>` containing drone id text e.g. `"FALCON-01"` | FleetRosterPanel.tsx:56-63 |
| Battery status labels | `"Idle"`, `"In Flight"`, `"Charging"`, `"Low Battery"`, `"Offline"` | [VERIFIED: frontend/src/components/FleetRosterPanel.tsx:4-10] — `{ idle: "Idle", in_flight: "In Flight", charging: "Charging", low_battery: "Low Battery", offline: "Offline" }` |
| Dispatch bar drone select | `<select>` inside a `<label>` with text "Drone", `required` | DispatchBar.tsx:78-92 |
| Dispatch bar zone input | `<input type="text">` inside label "Zone" | DispatchBar.tsx:96-103 |
| Dispatch bar distance input | `<input type="number">` inside label "Distance (km)" | DispatchBar.tsx:106-114 |
| Launch button | button text `"Launch Mission"` | DispatchBar.tsx:121 |
| Recall button | button text `"Recall"` | DispatchBar.tsx:129 |
| Dispatch error text | plain text = backend's `reason` string (e.g. `"insufficient_budget"`) | DispatchBar.tsx:132-142 |
| Missions table header | text `"Missions"` | MissionsTable.tsx:39 |
| Mission status labels | `"En Route"`, `"Delivered"`, `"Recalled"` | [VERIFIED: frontend/src/components/MissionsTable.tsx:6-10] — `{ en_route: "En Route", delivered: "Delivered", recalled: "Recalled" }` |
| Missions empty state | text `"No active missions"` | MissionsTable.tsx:83 |
| Fleet heatmap header | text `"Fleet Heatmap"` | FleetHeatmap.tsx:112 |
| Heatmap cells | SVG `<g><rect fill="..."><text>...` — one per drone in snapshot, plus a batteryPct-less root node that renders nothing (`content` returns `null` when `batteryPct` is not a number) | FleetHeatmap.tsx:59-82 |
| Energy budget header | text `"Energy Budget"` | EnergyBudgetChart.tsx:96 |
| Budget chart empty state | text `"No budget history yet."` | EnergyBudgetChart.tsx:101 |
| Budget chart rendered | Recharts `LineChart`/`Line` → SVG `path.recharts-line-curve` (or count of `.recharts-dot`/data points if `dot` were enabled — it's `dot={false}` here, so assert on `svg path` presence and the `XAxis` tick count matching snapshot length) | EnergyBudgetChart.tsx:104-125 |
| Sparkline | Recharts `LineChart` inside a fixed 80×24 `ResponsiveContainer`, `dot={false}` — assert `svg path` exists per roster row cell | DroneSparkline.tsx:33-46 |
| Connection dot | `<span>` with class containing `bg-emerald-500` (connected/"Live"), `bg-ops-amber` (connecting), or `bg-red-500` (disconnected), text label alongside it | [VERIFIED: frontend/src/components/ConnectionDot.tsx:3-13] — `COLORS = { connected: "bg-emerald-500", connecting: "bg-ops-amber", disconnected: "bg-red-500" }`, `LABELS = { connected: "Live", connecting: "Connecting", disconnected: "Disconnected" }` |
| Header energy budget | text `"Energy Budget:"` followed by `"{remaining} / {total} kWh"` | Header.tsx:28-33 |
| Header active missions | text `"Active Missions:"` followed by count | Header.tsx:34-39 |
| Chat panel | `[data-testid="chat-panel"]` | ChatPanel.tsx:70 |
| Chat input | `<input placeholder="Ask the flight director...">`, disabled while `sending` | ChatPanel.tsx:106-113 |
| Chat send button | `aria-label="Send message"` | ChatPanel.tsx:119-126 |
| Chat loading indicator | `[data-testid="chat-loading"]`, text `"Thinking…"` | ChatPanel.tsx:114-118 |
| Chat confirmation card | `[data-testid="confirmation-card"]` — success cards show verb `LAUNCH`/`RECALL`/`ADD`/`REMOVE` + badge `Dispatched`/`Recalled`/`Added`/`Removed`; failure cards show `"Failed:"` + message | [VERIFIED: frontend/src/components/chat/ConfirmationCard.tsx:5-17,44,54,79] |

### Pattern 3: Mocked chat — deterministic keyword triggers (LLM_MOCK=true)
**What:** `backend/app/chat/llm.py:mock_reply()` is a keyword-driven deterministic stand-in
explicitly documented as existing "so E2E tests can exercise auto-execution"
[VERIFIED: backend/app/chat/llm.py:149-186]:
- Message containing `"recall"` (case-insensitive) AND at least one active mission → recalls the
  first active mission, reply text ends `"Recalling {drone_id}."`
- Message containing `"launch"` (case-insensitive) AND at least one idle roster drone → launches
  that drone to zone `"Riverside"`, `distance_km=4.0`, reply text ends
  `"Launching {drone_id} to Riverside."`
- Any other message → plain summary only, no actions: `"[mock] {N} drones on roster, {M} en route, {X} kWh remaining."`
**When to use:** TEST-04's "AI chat (mocked)" scenario. Send `"Launch a drone"` (contains
"launch") when at least one drone is idle (true on fresh start) and assert a
`[data-testid="confirmation-card"]` with text `"LAUNCH"` and badge `"Dispatched"` appears, plus the
missions table gains a row.
**Example:**
```typescript
// Source: backend/app/chat/llm.py mock_reply() keyword contract (verified in-repo)
test("mocked chat launches a mission on request", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Ask the flight director...").fill("Launch a drone");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByTestId("confirmation-card").first()).toContainText("LAUNCH");
  await expect(page.getByTestId("confirmation-card").first()).toContainText("Dispatched");
});
```
Note: `tests/docker-compose.test.yml` already sets `LLM_MOCK: "true"` and a placeholder
`OPENROUTER_API_KEY` [VERIFIED: tests/docker-compose.test.yml:6-8] — no env changes needed for
this scenario to work in the isolated E2E container.

### Pattern 4: SSE disconnect/reconnect via route interception
**What:** The backend SSE endpoint sends a `retry: 1000\n\n` directive on connect and detects
client disconnect via `request.is_disconnected()`
[VERIFIED: backend/app/telemetry/stream.py:62,70-72] — reconnection is entirely native
`EventSource` browser behavior; the frontend hook does no manual retry logic, it only tracks
`onopen`/`onerror` to set `"connected"`/`"disconnected"` status
[VERIFIED: frontend/src/lib/useTelemetryStream.ts:31-32].
**When to use:** TEST-04's SSE resilience scenario. Playwright's `context.route()` /
`route.abort()` is Microsoft's documented pattern for simulating request failure
[CITED: github.com/microsoft/playwright docs/src/api/class-browsercontext.md via Context7,
`/microsoft/playwright`]. Scope the abort to only the stream URL so the 5s fleet-poll and 5s
budget-history poll are unaffected — keeps the test isolated to the SSE claim being verified.
**Example:**
```typescript
// Source: Playwright BrowserContext.route/abort pattern
// [CITED: github.com/microsoft/playwright/blob/main/docs/src/api/class-browsercontext.md]
test("SSE disconnects and reconnects, connection dot reflects both states", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByText("Live")).toBeVisible();

  await context.route("**/api/stream/telemetry", (route) => route.abort());
  // existing connection keeps running until the browser's next retry attempt fails;
  // force a reconnect attempt by reloading, or wait for the native retry cycle
  await page.reload();
  await expect(page.getByText("Disconnected")).toBeVisible({ timeout: 10_000 });

  await context.unroute("**/api/stream/telemetry");
  await expect(page.getByText("Live")).toBeVisible({ timeout: 10_000 });
});
```
**Caveat (open question):** aborting an *already-open* long-lived `EventSource` connection via
`route.abort()` only affects *new* requests matching the pattern — Playwright's routing intercepts
requests, not established streaming connections already in flight. The reliable way to force the
existing connection to break is either (a) `page.reload()` after installing the route (forces a
fresh `EventSource` that immediately fails), or (b) close the connection server-side by briefly
stopping/restarting the app's telemetry source — not available without app changes. Recommend (a):
reload-after-route is the simplest, most deterministic trigger and matches how a real network drop
would present to a fresh page load. Document this as the intended mechanism in the plan rather than
attempting to intercept a mid-flight stream.

### Anti-Patterns to Avoid
- **Screenshot-diff E2E assertions:** explicitly ruled out by D-03 — use structural DOM/SVG
  element-count and text assertions instead.
- **Rewriting existing pytest/Vitest suites:** D-02 explicitly forbids this — the ~300/81 tests
  already pass; only add tests for genuinely uncovered requirement wording.
- **`context.setOffline()` for the SSE test:** works, but also breaks the two unrelated 5s polling
  fetches during the same window (`FleetOpsProvider`, `EnergyBudgetChart`), producing console
  errors/state unrelated to the SSE claim under test — prefer `route()` scoped to the stream URL.
- **Assuming a manual "Add/Remove Drone" UI button exists:** it does not (verified — see Pattern
  1). Do not plan a UI-driven roster CRUD E2E test; use the `request` fixture.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE reconnection logic | Custom JS reconnect/backoff loop | Native `EventSource` (already used) + server's `retry: 1000` directive | Already implemented and correct; browser handles retry natively — the phase only needs a *test* for it, not new reconnect code |
| SQLite WAL-safe file copy | Manual byte-level file copy without checkpoint | `PRAGMA wal_checkpoint(TRUNCATE)` then copy while stopped (documented above) | Copying `.db` without checkpointing risks missing committed transactions still only in the `-wal` file |
| E2E visual regression | Custom screenshot diffing / `toHaveScreenshot()` | Structural DOM/SVG assertions (D-03) | Locked decision; screenshot diffs are flaky across CI environments (font rendering, GPU) |

**Key insight:** Every "don't hand-roll" concern in this phase is really "don't second-guess
decisions already locked in CONTEXT.md" — the phase has almost no open design space left; the
remaining work is executing verification and gap-fill against very specific, already-researched
constraints.

## Runtime State Inventory

**Trigger:** DEPLOY-04 changes how the SQLite database is mounted (named volume → bind mount),
which is a storage-location change, not a rename — but the "what runtime state exists that a
config change could orphan" question applies identically.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Named Docker volume `skyfleet-data` currently holds a live `skyfleet.db` (WAL mode) with 9 `fleet_roster` rows, 4 `mission_log` rows, plus `operator_profile`, `missions`, `budget_snapshots`, `chat_messages` tables [VERIFIED: `docker exec skyfleet-ops python3 -c "..."` this session] | Data migration (Option A) OR documented reset (Option B) — planner must pick one; both approaches given above |
| Live service config | None — no external services (n8n, Datadog, etc.) referenced anywhere in this codebase | None |
| OS-registered state | None — no Task Scheduler/pm2/launchd/systemd registrations found in scripts or docs | None |
| Secrets/env vars | `.env` at repo root holds the real `OPENROUTER_API_KEY`; read directly by `--env-file .env` in both start scripts [VERIFIED: scripts/start_mac.sh:38, scripts/start_windows.ps1 `--env-file .env`] — unaffected by the D-01 volume-mount edit, no key rename involved | None |
| Build artifacts | Currently-running image `skyfleet-ops:latest` was built from the *pre-D-01* Dockerfile/compose (still using the named volume) [VERIFIED: `docker image ls`/`docker ps -a` this session] — after this phase's edits, a fresh `docker build` is required; the running container will need to be stopped and replaced (`docker rm -f skyfleet-ops`), which the idempotent start script already does automatically on next run | Rebuild + restart via `scripts/start_mac.sh --build` after edits; no manual cleanup beyond what the script already does |

**Nothing found in category:** "Live service config" and "OS-registered state" — verified by
reading every file in `docker/`, `scripts/`, and `tests/` this session; none reference any
external service registration or OS-level task scheduling.

## Common Pitfalls

### Pitfall 1: No `.dockerignore` exists — secrets and bulk enter the build context
**What goes wrong:** `docker build -f docker/Dockerfile -t skyfleet-ops .` (run from repo root,
per `scripts/start_mac.sh:24`) sends the *entire* repo root as build context to the Docker
daemon, including `.env` (containing the real `OPENROUTER_API_KEY`), `database/skyfleet.db`
(currently 131KB + a 4MB `-wal` file), `tests/node_modules/`, and `.git/`. Confirmed no
`.dockerignore` file exists anywhere in the repo [VERIFIED: `ls -la .dockerignore
docker/.dockerignore` this session — both `No such file or directory`].
**Why it happens:** The Dockerfile's `COPY` instructions are correctly scoped
(`COPY frontend/ ./`, `COPY backend/ ./`), so nothing bad ends up *inside* the built image layers
— but the build *context* itself (everything sent to the daemon before any `COPY` filtering
happens) is unfiltered.
**How to avoid:** Add a `.dockerignore` at the repo root excluding at minimum: `.env`,
`.env.local`, `database/*.db*`, `**/node_modules`, `.git`, `frontend/.next`, `backend/.venv`,
`.planning`, `.claude`. This is a build-context hygiene fix, not a functional requirement of
DEPLOY-01-04 — recommend including it as a low-risk hardening task since it directly touches the
Docker packaging surface this phase already owns.
**Warning signs:** Slow `docker build` context-transfer step (`=> [internal] load build context`)
taking much longer than expected; `du -sh` on the repo root context noticeably larger than
`frontend/` + `backend/` alone.

### Pitfall 2: Reusing an already-running container/image masks a broken rebuild
**What goes wrong:** Both start scripts only rebuild `if $BUILD || ! docker image inspect
"$IMAGE_NAME"` succeeds [VERIFIED: scripts/start_mac.sh:22-25] — i.e., if an image tagged
`skyfleet-ops` already exists (it does, right now, in this environment), running
`./scripts/start_mac.sh` without `--build` will silently reuse the *stale* pre-phase-4 image and
never pick up the Dockerfile/compose edits this phase makes.
**Why it happens:** Idempotency-by-image-name-check is correct for "don't rebuild on every run"
but means the executor/verifier must remember to pass `--build` (or `docker rmi` first) when
validating this phase's changes.
**How to avoid:** Any verification task for DEPLOY-01 through DEPLOY-04 must explicitly run
`./scripts/start_mac.sh --build` (or `docker build` directly), not a bare `./scripts/start_mac.sh`.
**Warning signs:** Testing "confirms" the bind mount works, but `docker inspect skyfleet-ops`
still shows the named volume — the image was never rebuilt.

### Pitfall 3: `EnergyBudgetChart` and `FleetOpsProvider` poll on independent timers, not the SSE stream
**What goes wrong:** A test that launches a mission via the dispatch bar and immediately asserts
the header's remaining-kWh figure updated may flake, because `FleetOpsProvider`'s
`refetch()`/roster poll runs every 5000ms [VERIFIED: frontend/src/lib/FleetOpsProvider.tsx:25,122
— `FLEET_POLL_INTERVAL_MS = 5000`] and `EnergyBudgetChart`'s history poll is a *separate* 5000ms
interval [VERIFIED: frontend/src/components/EnergyBudgetChart.tsx:23]. However, `DispatchBar`
itself calls `refetch()` immediately after a successful launch/recall
[VERIFIED: frontend/src/components/DispatchBar.tsx:41-42 — `upsertMission(body); await
refetch();`], so the header and missions table update immediately; only the *budget chart*
(a separate `GET /api/fleet/history` poll) can lag up to 5s behind.
**Why it happens:** Two different data sources (live SSE snapshot vs. periodic REST polls) update
on different cadences by design.
**How to avoid:** For the mission launch/recall + budget scenario, assert on the header's
remaining-kWh text (updates immediately via `DispatchBar`'s explicit `refetch()`) rather than the
`EnergyBudgetChart` line count, or use a Playwright `expect(...).toPass({ timeout: 10_000 })` /
extended-timeout `expect` when asserting against the chart specifically.
**Warning signs:** Intermittent E2E failures on the budget-chart assertion only, not on the
header/missions-table assertions, in the same test run.

## Code Examples

### Backend test-gap-audit checklist (TEST-01/02, run this session)
```bash
# Source: this session's live pytest run against backend/tests/
cd backend && uv run --extra dev pytest -v
# Result: 300 passed, 6 skipped, 3 deselected (live-marker tests) in 5.84s
# roster/: test_models.py, test_repository.py, test_router.py, test_service.py — all present
# chat/: test_llm.py (incl. test_malformed_completions_raise_llm_error, line 137),
#        test_repository.py, test_router.py (incl. budget/roster validation-in-chat-flow tests:
#        test_second_launch_fails_when_first_exhausts_budget line 280,
#        test_add_duplicate_drone_returns_readable_error line 179,
#        test_remove_untracked_drone_returns_readable_error line 227), test_evals.py — all present
```
No gaps found against TEST-01/TEST-02's literal wording in this pass. If the planner wants a
second opinion, the check is mechanical: grep requirement nouns ("roster service", "roster
repository", "roster router", "malformed", "structured-output", "validation") against
`grep -rn "def test_" backend/tests/{roster,chat}/*.py` and confirm each noun has at least one
matching test name or docstring.

### Frontend test-gap-audit checklist (TEST-03, run this session)
```bash
# Source: this session's live vitest run
cd frontend && npm test
# Result: 14 test files passed, 81 tests passed, 3.68s
# DetailPanel.test.tsx, FleetHeatmap.test.tsx, EnergyBudgetChart.test.tsx, MissionsTable.test.tsx,
# DispatchBar.test.tsx, ChatPanel.test.tsx — all six components named in TEST-03 confirmed present
```
No gaps found against TEST-03's literal wording (detail panel, heatmap, budget chart, missions
table, dispatch bar, chat panel — all six have `.test.tsx` files, all passing).

### Docker build + smoke-test verification sequence (for DEPLOY-01/D-04 tasks)
```bash
# Source: verified live against the running container this session
docker build -f docker/Dockerfile -t skyfleet-ops .
docker run -d --name skyfleet-ops-verify -p 8001:8000 --env-file .env \
  -v "$(pwd)/database":/app/database skyfleet-ops
sleep 3
curl -sf http://localhost:8001/api/health   # expect {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/   # expect 200
docker rm -f skyfleet-ops-verify
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Named Docker volume (`skyfleet-data`) | Bind mount (`./database:/app/database`) | This phase (D-01) | Operator can inspect/back up `skyfleet.db` directly from the host filesystem, matching PLAN.md §11's documented command |

**Deprecated/outdated:** Nothing framework-level is outdated here — Docker 29.6.1, Compose v5.2.0,
Playwright 1.48.0, pytest 8.x, Vitest 2.x are all current, functioning stacks already in place;
this phase does not require any version bumps.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Option B (accept a reset at bind-mount cutover) is the recommended migration path over Option A (preserve data) | Docker Verification Findings / migration options | Low — this is a recommendation, not a locked decision; the planner/user can choose Option A instead using the documented commands. If the current 9-drone/4-mission state in the named volume matters to the user, Option A must be chosen explicitly |
| A2 | Reload-after-route (`page.reload()` after installing a route abort) is the most reliable way to force an SSE reconnect-visible-in-UI in Playwright, versus intercepting a mid-flight `EventSource` | Pattern 4 (SSE disconnect/reconnect) | Medium — if this doesn't reliably flip `ConnectionDot` to "Disconnected" in practice, the executor may need to fall back to `context.setOffline()` (noisier but simpler) or a short server-side restart within the test container |

**If this table is empty:** N/A — two assumptions logged above; both are choices with documented
fallbacks, not unverified factual claims about the codebase.

## Open Questions (RESOLVED)

1. **Preserve or reset the existing named-volume database data (D-01 migration)?** (RESOLVED: Recommendation — Option B, reset — provided below; planner adopted it per CONTEXT.md's discretion delegation.)
   - What we know: The volume currently holds real (if just exploratory) data — 9 roster rows, 4
     mission_log rows — and both a preserve-path (checkpoint + `docker cp`) and a reset-path are
     documented above with exact commands.
   - What's unclear: Whether the user cares about this specific data, or whether it's disposable
     test-run residue from earlier manual verification.
   - Recommendation: Default to Option B (documented reset) per the project's "be simple, don't
     over-engineer" stated preference, unless the user explicitly asks to preserve it — flag this
     as a one-line decision point in the plan rather than silently picking one.

2. **Exact mechanism to force a visible SSE reconnect in Playwright.** (RESOLVED: Recommendation — reload-based `route.abort()` — provided below; planner adopted it, with `setOffline()` documented as fallback.)
   - What we know: `route.abort()` scoped to the stream URL plus `page.reload()` is the
     Playwright-documented mechanism most likely to work deterministically (see Pattern 4).
   - What's unclear: Whether `route.abort()` alone (without reload) can break an *already open*
     streaming connection in Chromium — Playwright's docs describe request interception, not
     stream-teardown, and this specific EventSource case is not covered by the fetched Context7
     snippets.
   - Recommendation: Plan the test using the reload-based approach first (deterministic, matches
     documented API); if it proves unreliable during execution, `context.setOffline()` is the
     documented fallback (noisier, but definitely tears down the live connection).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | DEPLOY-01 through DEPLOY-04, TEST-05 | Yes [VERIFIED: `docker --version` this session] | 29.6.1 | — |
| Docker Compose | TEST-05, `docker/docker-compose.yml` | Yes [VERIFIED: `docker compose version` this session] | v5.2.0 | — |
| uv (Python package manager) | Backend test execution | Yes — `uv run --extra dev pytest` succeeded this session | (bundled in image via `pip install uv`) | — |
| Node.js / npm | Frontend test execution, Playwright container | Yes — `npm test` succeeded this session | Per `frontend/package.json` engines (Node 20 LTS per project CLAUDE.md) | — |
| Windows runner | Live-verifying `start_windows.ps1`/`stop_windows.ps1` | No — this environment is Linux | — | Code-review verification against the bash equivalents' logic (per CONTEXT.md Claude's Discretion) — no live-execution fallback needed since decision already accepts this |

**Missing dependencies with no fallback:** None blocking — the only "missing" dependency (a
Windows runner) already has an accepted fallback per CONTEXT.md's explicit discretion note.

**Missing dependencies with fallback:** Windows script verification — code review only, as
decided in CONTEXT.md.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Backend framework | pytest 8.3+, `asyncio_mode = "auto"` [VERIFIED: backend/pyproject.toml:32-38] |
| Backend config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Frontend framework | Vitest 2.1+, jsdom environment [VERIFIED: frontend/vitest.config.ts] |
| Frontend config file | `frontend/vitest.config.ts` |
| E2E framework | Playwright 1.48 [VERIFIED: tests/playwright.config.ts] |
| E2E config file | `tests/playwright.config.ts` |
| Backend quick run | `cd backend && uv run --extra dev pytest -v` |
| Frontend quick run | `cd frontend && npm test` |
| E2E full run | `cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | Image builds, serves both frontend+API on 8000 | smoke (manual/scripted) | `docker build -f docker/Dockerfile -t skyfleet-ops . && docker run ...` + curl checks (see Code Examples) | N/A — no dedicated test file; verified via TEST-04's fresh-start E2E scenario in practice |
| DEPLOY-02/03 | Scripts idempotent | manual/code-review | Run twice, assert same end state; PowerShell via code review | N/A — shell scripts aren't unit-testable in this stack; idempotency already verified by reading the guard clauses |
| DEPLOY-04 | DB persists across restart | E2E | `fresh-start.spec.ts` (restart scenario) or manual `docker restart` + `curl /api/roster` | ❌ Wave 0 |
| TEST-01 | roster service/repo/router | unit | `pytest backend/tests/roster/ -v` | ✅ (existing, verified passing) |
| TEST-02 | chat/LLM parsing, malformed, validation | unit | `pytest backend/tests/chat/ -v` | ✅ (existing, verified passing) |
| TEST-03 | 6 named frontend components | unit | `npm test -- src/components/{DetailPanel,FleetHeatmap,EnergyBudgetChart,MissionsTable,DispatchBar}.test.tsx src/components/chat/ChatPanel.test.tsx` | ✅ (existing, verified passing) |
| TEST-04 scenario 1 (fresh start) | Default roster, 500kWh, telemetry streaming | E2E | `tests/specs/fresh-start.spec.ts` | ❌ Wave 0 |
| TEST-04 scenario 2 (roster add/remove) | POST/DELETE via API, UI reflects | E2E | `tests/specs/roster.spec.ts` | ❌ Wave 0 |
| TEST-04 scenario 3 (launch/recall+budget) | Dispatch bar, header updates | E2E | `tests/specs/missions.spec.ts` | ❌ Wave 0 |
| TEST-04 scenario 4 (visualization) | Heatmap cells, budget chart, sparklines (structural, per D-03) | E2E | `tests/specs/visualization.spec.ts` | ❌ Wave 0 |
| TEST-04 scenario 5 (mocked chat) | Keyword-triggered launch/recall, confirmation card | E2E | `tests/specs/chat.spec.ts` | ❌ Wave 0 |
| TEST-04 scenario 6 (SSE resilience) | Disconnect/reconnect, ConnectionDot reflects | E2E | `tests/specs/sse-resilience.spec.ts` | ❌ Wave 0 |
| TEST-05 | Playwright isolated in test-only compose | infra | `tests/docker-compose.test.yml` | ✅ (existing, verified correct) |

### Sampling Rate
- **Per task commit:** Backend quick run + frontend quick run (both complete in under 6s combined,
  verified this session)
- **Per wave merge:** Full E2E suite (`docker compose -f tests/docker-compose.test.yml up --build
  --abort-on-container-exit`) — slower (image build + browser boot), run once per wave not per task
- **Phase gate:** Full E2E suite green, plus backend (300 tests) and frontend (81 tests) suites
  green, before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/specs/fresh-start.spec.ts` — covers DEPLOY-04 (restart persistence) + TEST-04 scenario 1
- [ ] `tests/specs/roster.spec.ts` — covers TEST-04 scenario 2 (via `request` fixture, no UI control exists)
- [ ] `tests/specs/missions.spec.ts` — covers TEST-04 scenario 3
- [ ] `tests/specs/visualization.spec.ts` — covers TEST-04 scenario 4 (structural assertions only, per D-03)
- [ ] `tests/specs/chat.spec.ts` — covers TEST-04 scenario 5 (uses `mock_reply()`'s `"launch"`/`"recall"` keyword contract)
- [ ] `tests/specs/sse-resilience.spec.ts` — covers TEST-04 scenario 6
- [ ] `.dockerignore` — not a test gap but a Wave 0-appropriate hardening file (Pitfall 1)
- [ ] Backend/frontend unit-test gap-fill — audit found none required this session; re-confirm at plan time in case source changed since this research

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Single-operator demo app, explicitly out of scope (REQUIREMENTS.md "Out of Scope") |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | No roles/permissions in this app |
| V5 Input Validation | No new surface | Already covered in Phases 1-2 (roster/chat validation); this phase adds no new endpoints |
| V6 Cryptography | No | No crypto operations added |
| V7 Error Handling/Logging | Yes | Docker container logs (`docker logs skyfleet-ops`) must never leak `OPENROUTER_API_KEY`; confirmed the app never logs raw env vars — `app/main.py` logging calls are lifecycle-only (`"SkyFleet Ops backend started/stopped"`) [VERIFIED: backend/app/main.py:71,77] |
| V14 Configuration | Yes | Missing `.dockerignore` (Pitfall 1) means `.env` (with the real API key) is included in the Docker build context sent to the daemon, though never copied into an image layer — low risk (local daemon, not baked into a shippable artifact) but a documented hardening gap this phase should close since it already owns `docker/` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Secret leakage via Docker build context | Information Disclosure | Add `.dockerignore` excluding `.env`, `database/*.db*`, `.git`, `node_modules`, `.venv` (Pitfall 1) |
| Stale image silently reused after config edits | Tampering (of expected behavior, not malicious) | Always verify with `--build` flag or explicit `docker rmi` before testing phase-4 Docker changes (Pitfall 2) |
| Named-volume data loss on cutover | Denial of Service (of data availability) | Explicit migration decision (Option A/B) documented above rather than a silent, unplanned data loss |

## Sources

### Primary (HIGH confidence — direct in-repo verification this session)
- `docker/Dockerfile`, `docker/docker-compose.yml` — multi-stage build and volume config, read in full
- `scripts/start_mac.sh`, `scripts/stop_mac.sh`, `scripts/start_windows.ps1`, `scripts/stop_windows.ps1` — read in full
- `tests/docker-compose.test.yml`, `tests/playwright.config.ts`, `tests/specs/health.spec.ts`, `tests/README.md` — read in full
- `backend/app/main.py`, `backend/app/telemetry/stream.py`, `backend/app/chat/llm.py`, `backend/app/chat/router.py`, `backend/app/roster/router.py` — read relevant sections
- `frontend/src/app/page.tsx`, `frontend/src/components/{FleetRosterPanel,DispatchBar,MissionsTable,FleetHeatmap,ConnectionDot,Header,EnergyBudgetChart,DroneSparkline}.tsx`, `frontend/src/components/chat/{ChatPanel,ConfirmationCard}.tsx`, `frontend/src/lib/{useTelemetryStream,FleetOpsProvider}.ts(x)` — read in full or relevant sections
- Live command execution this session: `cd backend && uv run --extra dev pytest -v` (300 passed, 6 skipped, 3 deselected); `cd frontend && npm test` (81 passed, 14 files); `docker volume ls`/`docker ps -a`/`docker exec skyfleet-ops ...` (live container/volume inspection); `docker exec skyfleet-ops curl ...` (smoke test)

### Secondary (MEDIUM confidence)
- Playwright `BrowserContext.route`/`route.abort()` API — [CITED: github.com/microsoft/playwright/blob/main/docs/src/api/class-browsercontext.md, fetched via Context7 `/microsoft/playwright`]

### Tertiary (LOW confidence)
- SQLite WAL-mode safe-copy guidance (checkpoint before copy) — [CITED, community sources via WebSearch: github.com/simonw/til/blob/master/sqlite/enabling-wal-mode.md, github.com/superfly/sqlite3-restore, pypi.org/project/sqlite-backup/0.1.2] — not official SQLite documentation directly, but consistent across multiple independent community sources; recommend the planner treat the exact `PRAGMA wal_checkpoint(TRUNCATE)` + stop-before-copy sequence as a reasonable, low-risk default rather than an authoritative requirement

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all versions verified live this session
- Architecture: HIGH — every file referenced was read in full this session; live container/volume state inspected directly
- Pitfalls: HIGH — all three pitfalls (missing `.dockerignore`, stale-image reuse, poll-timing) are verified facts about the current repo state and running container, not speculation

**Research date:** 2026-08-14
**Valid until:** 2026-09-13 (30 days — this phase touches config/infra with no fast-moving external dependencies; re-verify the live container/volume state if significant time passes before planning, since it may change)
