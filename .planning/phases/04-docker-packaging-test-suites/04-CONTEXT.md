# Phase 4: Docker Packaging & Test Suites - Context

**Gathered:** 2026-08-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator can launch the whole platform with a single command (Docker), and the already-built
platform (roster, chat, frontend from Phases 1–3) gets automated backend, frontend, and E2E test
coverage. Requirements: DEPLOY-01 through DEPLOY-04, TEST-01 through TEST-05. This phase is
packaging + testing only — no new product features. Scaffolding for Docker, scripts, and E2E
infra already exists on disk from an earlier pass; this phase verifies/hardens it and closes
coverage gaps rather than building from scratch.

**Roadmap note:** This phase was previously tagged `Mode: mvp` in ROADMAP.md; that tag was
cleared before planning (per user decision) because the phase is infra/test coverage work, not a
single user-facing vertical capability, and Phase 3's retrospective flagged the same mismatch as
unresolved. Standard tracer-first (non-MVP) planning applies.

</domain>

<decisions>
## Implementation Decisions

### Docker Volume Strategy
- **D-01:** `docker/docker-compose.yml` and `scripts/start_mac.sh` currently mount a named Docker
  volume (`skyfleet-data:/app/database`), but PLAN.md §11 and DEPLOY-04's requirement text both
  specify a bind mount of the host's `database/` directory
  (`-v $(pwd)/database:/app/database`) so the operator can inspect/back up `skyfleet.db` directly.
  **Decision: switch to the bind mount to match spec.** Update `docker/docker-compose.yml`,
  `scripts/start_mac.sh`, and `scripts/start_windows.ps1` accordingly. — **Reversibility:**
  costly — **rationale:** a named volume already holds this project's `skyfleet.db`; switching to
  a bind mount means either a documented one-time data migration step or accepting a fresh
  database at cutover. Flag this for the planner to address explicitly (migration note or
  accepted reset).

### Existing Unit Test Coverage
- **D-02:** Backend already has ~300 passing pytest tests (full `roster/` and `chat/` suites
  included) and frontend already has 81 passing Vitest tests (including `DetailPanel`,
  `FleetHeatmap`, `DispatchBar`, `ChatPanel`, `ConfirmationCard`, etc.) — all built during Phases
  1–3. TEST-01/02/03 are marked "Pending" in REQUIREMENTS.md but are likely substantially already
  satisfied. **Decision: audit for gaps against TEST-01/02/03's exact wording, do not rewrite
  existing suites.** Add only what's missing; mark the requirement satisfied by the existing
  suite plus any gap-fill work.

### E2E Assertion Depth
- **D-03:** TEST-04 lists 6 scenarios (fresh start, roster add/remove, mission launch/recall with
  budget updates, visualization rendering, mocked AI chat, SSE disconnect/reconnect). Only a
  health-check placeholder (`tests/specs/health.spec.ts`) exists today. **Decision: use structural
  DOM/data assertions for the "visualization rendering" scenario** (e.g., correct number of
  treemap cells, chart has data points, sparkline renders) — not pixel-level screenshot
  comparisons, to avoid flaky cross-environment visual diffs.

### Static Export / StaticFiles Serving Risk
- **D-04:** STATE.md's Phase 3 handoff flagged a specific known risk: Next.js static-export +
  FastAPI's `StaticFiles` serving has edge cases around `trailingSlash` routing and 404/fallback
  behavior. `frontend/next.config.js` does not set `trailingSlash` (defaults to `false`). This is
  a single-page app (one route only — `frontend/src/app/page.tsx`). **Decision: smoke-test only**
  — the "fresh start" TEST-04 E2E scenario (build → container start → `GET /`) is sufficient
  verification; dedicated deep-link/refresh/404-fallback tests are not required given there's
  only one route to serve.

### Claude's Discretion
- `backend/app/demo/mission_demo.py` (untracked, hand-written Rich-based terminal demo of the
  mission scheduler) — not discussed in depth; leave untouched unless it conflicts with phase
  work. Not part of DEPLOY/TEST requirements.
- Windows script (`start_windows.ps1`/`stop_windows.ps1`) verification depth — no Windows runner
  available in this environment; verify by code review against the bash equivalents' logic
  (idempotency checks, bind-mount update per D-01) rather than live execution.
- Exact SQL/file changes needed to migrate the named-volume database to the new bind mount (D-01)
  — planner/executor to determine the concrete migration or reset approach.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specification
- `planning/PLAN.md` §11 (Docker & Deployment) — the authoritative bind-mount command
  (`-v $(pwd)/database:/app/database`), multi-stage Dockerfile stages, start/stop script
  responsibilities (informs D-01).
- `planning/PLAN.md` §12 (Testing Strategy) — backend/frontend unit test scope and the 6 E2E
  scenarios (fresh start, add/remove drone, launch, recall, visualization, AI chat mocked, SSE
  resilience) that TEST-04 must cover.
- `.planning/REQUIREMENTS.md` — DEPLOY-01 through DEPLOY-04, TEST-01 through TEST-05 (this
  phase's requirement text).

### Codebase maps (already generated, dated 2026-08-12 — predates Phases 2–3, treat roster/chat
  sections as stale)
- `.planning/codebase/STACK.md` — pinned test frameworks (pytest, Vitest, Playwright), Docker
  multi-stage build description, `.env` variable list.
- `.planning/codebase/TESTING.md` — test file organization, naming conventions, mocking strategy
  for both backend (pytest, real DB via `tmp_path`, real cache) and E2E (Playwright,
  `docker-compose.test.yml`).
- `.planning/codebase/STRUCTURE.md` — directory layout for `docker/`, `scripts/`, `tests/`
  (note: shows `roster/`/`chat/` as empty — stale, both are now fully built per PROJECT.md).

### Existing implementation this phase builds on (verified on disk, current as of this session)
- `docker/Dockerfile` — multi-stage Node 20 → Python 3.12 build, already matches PLAN.md's shape;
  verify it builds and runs rather than assuming.
- `docker/docker-compose.yml`, `scripts/start_mac.sh`, `scripts/stop_mac.sh`,
  `scripts/start_windows.ps1`, `scripts/stop_windows.ps1` — already exist; D-01 requires editing
  the volume mount in the compose file and `start_mac.sh`/`start_windows.ps1`.
- `tests/docker-compose.test.yml`, `tests/playwright.config.ts` — already exist and appear
  complete (healthcheck, `LLM_MOCK=true`, Playwright container wiring); reuse as-is.
- `tests/specs/health.spec.ts` — only implemented E2E spec; TEST-04's other 5 scenarios need new
  spec files here.
- `backend/tests/roster/`, `backend/tests/chat/` — existing full test suites (models, repository,
  router, service for roster; repository, router, LLM, evals, live smoke for chat) — the baseline
  D-02's gap audit starts from.
- `frontend/src/components/*.test.tsx`, `frontend/src/lib/*.test.tsx` — existing Vitest suites
  covering all Phase 3 components — the baseline D-02's gap audit starts from.
- `backend/app/main.py` (~line 94-97) — `StaticFiles` mount logic (`if _static_dir.exists()`) —
  relevant to D-04's smoke-test scenario.
- `frontend/next.config.js` — `output: "export"`, `images: {unoptimized: true}`, no
  `trailingSlash` setting — relevant to D-04.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `docker/Dockerfile` — working multi-stage build; needs verification (build + run), not a rewrite.
- `tests/docker-compose.test.yml` + `tests/playwright.config.ts` — E2E harness already wired with
  healthcheck and `LLM_MOCK=true`; new specs slot into `tests/specs/`.
- `backend/tests/{roster,chat}/` and `frontend/src/**/*.test.tsx` — substantial existing coverage
  to audit against TEST-01/02/03 rather than duplicate.

### Established Patterns
- Backend tests: pytest, isolated `tmp_path` SQLite per test, real (unmocked) DB/cache instances,
  Arrange-Act-Assert, `class Test*` grouping (per `.planning/codebase/TESTING.md`).
- E2E tests: Playwright `test()` blocks, `request` fixture for direct API checks, `baseURL` from
  `BASE_URL` env var (defaults to `localhost:8000`).
- Idempotent shell scripts: `scripts/start_mac.sh` already checks `docker image inspect` /
  `docker ps -a` before building/removing — new script edits (D-01) should preserve this pattern.

### Integration Points
- `docker/Dockerfile` → copies `frontend/out` (Next static export) into backend `static/`,
  served by `backend/app/main.py`'s `StaticFiles` mount at `/`.
- `tests/docker-compose.test.yml` builds the same `docker/Dockerfile` the production scripts use
  — one build definition, two consumers (prod scripts, E2E harness).

</code_context>

<specifics>
## Specific Ideas

No literal UI/copy examples for this phase (packaging + testing, not user-facing feature work).
The concrete decisions above (D-01 through D-04) are the specific implementation guidance for
this phase.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. `backend/app/demo/mission_demo.py`'s disposition was
raised but resolved as Claude's Discretion (leave as-is), not deferred to another phase.

</deferred>

---

*Phase: 4-Docker Packaging & Test Suites*
*Context gathered: 2026-08-13*
