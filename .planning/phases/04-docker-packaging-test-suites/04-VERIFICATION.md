---
phase: 04-docker-packaging-test-suites
verified: 2026-08-14T06:57:12Z
status: human_needed
score: 1/5 roadmap truths verified (behavior-executed); 4 present + structurally wired, live execution unverified
behavior_unverified: 4
overrides_applied: 0
human_verification:
  - test: "Run `./scripts/start_mac.sh --build`, then `docker inspect skyfleet-ops` for a bind mount at /app/database, then curl / and /api/health (both 200), then `docker restart skyfleet-ops` and confirm `GET /api/roster` returns the same drones before/after."
    expected: "Container builds and serves both frontend and API on port 8000; bind mount type is `bind` sourced from the repo's database/ dir; roster identical across restart; database/skyfleet.db mtime advances."
    why_human: "Requires a live Docker build + running container. This sandbox has Docker unreachable (`docker info` fails) and the host filesystem is at 98% capacity (3.0GB free), reproducing the exact ENOSPC/socket-hang conditions documented across all four plan SUMMARYs. Static evidence (Dockerfile, compose file, start-script guards, .dockerignore) is structurally correct; only the live execution is unobserved."
  - test: "Run `./scripts/start_mac.sh` and `./scripts/stop_mac.sh` each twice in a row (and the PowerShell equivalents on an actual Windows host), confirming idempotency and the corrected `docker volume inspect` / `docker image inspect` guards (CR-01/CR-02 fixes) behave as intended at runtime."
    expected: "Exactly one container after two start calls; both stop calls exit 0; the leftover-`skyfleet-data`-volume notice fires when the volume exists (verified previously to never fire due to the substring-vs-regex filter bug, now fixed in source); start_windows.ps1 does not abort on a fresh install under PowerShell 7.4+."
    why_human: "No Docker daemon available in this sandbox to execute either script's live path; no Windows host available at all. The CR-01/CR-02 source fixes were confirmed present and correctly shaped by direct file inspection, but their runtime behavior was never observed."
  - test: "Run the full Playwright E2E harness (`cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright`) twice in a row without recreating the app container, covering all seven specs (health, fresh-start, roster, missions, visualization, chat, sse-resilience)."
    expected: "All seven specs pass both runs; the suite demonstrates idempotency (no leftover state from run 1 breaks run 2); `docker run --rm skyfleet-ops` shows no `/ms-playwright` directory and no `node` binary (TEST-05 image-isolation proof)."
    why_human: "Requires a live Docker build and multi-container compose run. Blocked in this sandbox by the same disk/Docker unavailability confirmed above. Every spec file was read in full and its assertions verified against the actual component/backend source (selectors, API shapes, mock keyword contract) — the code is present, wired, and passed all static checks (tsc, no skip/fixme/only, no screenshot assertions) — but no spec has been observed passing against a running container."
  - test: "Specifically for `sse-resilience.spec.ts`: with the app running, stop the container's telemetry route (or the container itself) and confirm the connection indicator turns red/`Disconnected`; restore it and confirm the indicator returns to `Live` on its own, without a page reload."
    expected: "The indicator recovers via the client's native EventSource retry (`retry: 1000` server directive), not via a fresh page load standing in for reconnection — this is the specific behavior the phase's own flagged prohibition (T-04-16) targets."
    why_human: "This is a state-transition/recovery invariant that only a live browser + live container can exercise. Source shows the reload happens only on the disconnect half, never between `unroute()` and the final `Live` assertion (confirmed by direct read of the spec file), which is the correct shape — but the actual recovery has never been observed to occur."
  - test: "Review the four judgment-tier prohibitions recorded across 04-01 through 04-04 (no silent data loss on the volume cutover; no test-weakening in the audit; no E2E spec that would pass with its target behavior removed) and confirm they hold in practice, not just by design."
    expected: "Each prohibition's mitigating evidence (recoverable-data notice + MIGRATION.md; unchanged git diff + suite counts matching baseline exactly, confirmed independently in this verification; specs with relative/scoped/fill-value assertions) is judged sufficient by a human reviewer."
    why_human: "These are flagged judgment-tier prohibitions per each plan's own frontmatter (`verification: judgment`, `flagged: true`). This is an LLM-judge, non-authoritative assessment: source evidence for all four is reasonably strong (see notes below), but final sign-off belongs to a human per the escalation-gate pattern."
---

# Phase 04: Docker Packaging & Test Suites Verification Report

**Phase Goal:** Operator can launch the whole platform with a single command, and the remaining
build (roster, chat, frontend, packaging) is verified by automated backend, frontend, and E2E
test suites.
**Verified:** 2026-08-14T06:57:12Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Environment Constraint Confirmed Independently

Before scoring, I independently reproduced the environment limitation documented in all four
plan SUMMARYs (04-01, 04-03, 04-04) and in `.planning/WINDOWS.md`:

```
$ df -h /
/dev/nvme0n1p7  121G  112G  3.0G  98% /
$ docker info >/dev/null 2>&1 && echo reachable || echo "docker NOT reachable"
docker NOT reachable
```

This matches the executors' own findings exactly (Docker Desktop socket unreachable / hung,
host disk under ~3.1GB free, ENOSPC risk on any multi-stage image build). This is an
environment condition, not a code defect — consistent with the orchestrator's framing for this
verification pass.

## Goal Achievement

### Observable Truths (mapped to ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A single multi-stage Docker build (Node → Python) serves the Next.js static export and FastAPI backend together on port 8000 | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `docker/Dockerfile` confirmed: Stage 1 `node:20-slim` builds `frontend/out` via `npm run build`; Stage 2 `python:3.12-slim` + `uv sync`, copies frontend build to `./static`, `CMD uvicorn ... --port 8000`. `docker/docker-compose.yml` builds from the same Dockerfile. Structurally correct and unchanged from what 04-RESEARCH.md verified live in an earlier session, but **not** rebuilt/served live in this verification — Docker unreachable in this sandbox. |
| 2 | Idempotent start/stop scripts for macOS/Linux and Windows build/run/stop the container with the volume mount and .env file | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `scripts/start_mac.sh` retains the `.env` existence check, `docker image inspect` build guard, and `docker ps -a`/grep container-replacement guard. Code review's CR-01 (volume-detection substring-vs-regex bug) and CR-02 (PowerShell 7.4+ `ErrorActionPreference` abort) were both found **and independently confirmed fixed** in source (`docker volume inspect skyfleet-data`, `$PSNativeCommandUseErrorActionPreference` toggled around native probes in `start_windows.ps1`). No live run of either script was performed here — no Docker, no Windows host. |
| 3 | SQLite data in database/ persists across container restarts | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | `docker/docker-compose.yml` and `scripts/start_mac.sh`/`start_windows.ps1` bind-mount `../database:/app/database` (or `$ROOT_DIR/database`) — no named volume remains. `docker/MIGRATION.md` exists with `wal_checkpoint` and a numbered preserve procedure. Restart-persistence itself (`docker restart` + `GET /api/roster` before/after) was never observed live in any of the four plans' sessions, nor in this verification. |
| 4 | Backend and frontend unit test suites pass, covering roster service/repository/router logic, chat/LLM structured-output parsing and validation delegation, and the new frontend components | ✓ VERIFIED | Re-ran both suites myself in this verification: **backend `300 passed, 6 skipped, 3 deselected`** (matches the 04-02 baseline exactly); **frontend `81 passed` across `14 files`** (matches the 04-02 baseline exactly). `frontend/src/components/{DetailPanel,FleetHeatmap,EnergyBudgetChart,MissionsTable,DispatchBar}.test.tsx` and `frontend/src/components/chat/ChatPanel.test.tsx` all present with real render-and-assert bodies per 04-02's own read-through table. `npm run build` (frontend static export) succeeds. |
| 5 | A Playwright E2E suite, isolated via tests/docker-compose.test.yml and run with LLM_MOCK=true, passes covering fresh start, roster add/remove, mission launch/recall with budget updates, visualization rendering, mocked AI chat, and SSE disconnect/reconnect resilience | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | All seven spec files exist under `tests/specs/` (`health`, `fresh-start`, `roster`, `missions`, `visualization`, `chat`, `sse-resilience`). `tests/docker-compose.test.yml` correctly isolates the browser to a separate `playwright` service pinned to `mcr.microsoft.com/playwright:v1.48.0-jammy`; production Dockerfile has no Node/browser runtime in its runtime stage. `tests/playwright.config.ts` sets `workers: 1` / `fullyParallel: false`. `cd tests && npx tsc --noEmit --skipLibCheck` exits 0. No `test.skip/fixme/only` anywhere; no `toHaveScreenshot`/`toMatchSnapshot` anywhere. Review's WR-01 (misleading try/catch comment) and WR-02 (unscoped locator hazard) both confirmed fixed in source. **No spec has ever been observed passing against a live container** — every plan's live harness run is recorded `status: unrun` in its own SUMMARY, and this verification could not run it either (same disk/Docker constraint). |

**Score:** 1/5 roadmap truths behaviorally verified; 4 present, structurally wired, and passing every check that does not require a live Docker daemon — behavior itself unexercised due to a confirmed, reproducible environment constraint (not a code gap).

### Flagged Prohibitions (judgment-tier, non-authoritative LLM assessment)

| Plan | Prohibition | My assessment | Basis |
|------|-------------|----------------|-------|
| 04-01 | MUST NOT silently discard/overwrite the operator's existing database on the volume-to-bind-mount cutover | Likely satisfied | `docker volume inspect skyfleet-data` (post-fix) correctly detects the leftover volume; `docker/MIGRATION.md` documents WAL-checkpoint-and-copy recovery; no script ever calls `docker volume rm`. Not observed printing live. |
| 04-02 | MUST NOT weaken tests (delete/skip/loosen) to turn a suite green | Confirmed satisfied | I independently re-ran both suites and got the exact same pass counts the audit claims (300 backend / 81 frontend) — this is strong, freshly-generated evidence, not merely trusting the SUMMARY. `git diff --numstat` over `backend/tests/` and `frontend/src/` for 04-02's commit shows no deletions per the SUMMARY (not independently re-verified via git diff in this pass, but consistent with the matching counts). |
| 04-03 | MUST NOT ship an E2E spec that would still pass with its target behavior removed | Plausible, unverified live | Design shows relative assertions (`readHeaderRemainingKwh` before/after), fill-value-scoped selectors, drone-id+zone pairing rather than bare row counts — all read directly in source. The plans' own claim that "every assertion was observed failing once against a deliberately broken condition" cannot be independently confirmed without re-running that break/fix cycle, which requires a live container. |
| 04-04 | Same prohibition, applied to visualization/chat/SSE specs | Plausible, unverified live | `sse-resilience.spec.ts` correctly has no reload between `unroute()` and the final `Live` assertion (confirmed by direct read) — this is the literal shape the prohibition demands. Heatmap assertion is fill-value-scoped, not a bare `rect` count. Still requires live execution to confirm these actually detect regressions rather than merely reading well. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/docker-compose.yml` | Bind mount `../database:/app/database`, no named volume | ✓ VERIFIED | Confirmed by direct read; no top-level `volumes:` block |
| `scripts/start_mac.sh` | Idempotent build/run, bind mount, leftover-volume notice | ✓ VERIFIED | All guards present; CR-01 fix confirmed (`docker volume inspect`) |
| `scripts/start_windows.ps1` | PowerShell mirror + CR-02 fix | ✓ VERIFIED | `$PSNativeCommandUseErrorActionPreference` toggle present around both `docker image inspect` and `docker volume inspect` |
| `docker/MIGRATION.md` | Cutover rationale + numbered preserve procedure | ✓ VERIFIED | Contains `wal_checkpoint` and numbered steps |
| `.dockerignore` | Excludes `.env`, database files, `.git`, dependency dirs | ✓ VERIFIED | All required lines present |
| `tests/playwright.config.ts` | `workers: 1`, `fullyParallel: false` | ✓ VERIFIED | Both settings present |
| `tests/specs/helpers.ts` | 5 exported fixtures | ✓ VERIFIED | `getFleet`, `getRoster`, `readHeaderRemainingKwh`, `pickIdleDrone`, `restoreFleetState` all present; WR-01 misleading-comment fix confirmed |
| `tests/specs/{fresh-start,roster,missions,visualization,chat,sse-resilience}.spec.ts` | Six TEST-04 scenarios | ✓ VERIFIED (present/wired) | All exist, content matches plan intent; WR-02 locator-scoping fix confirmed in `fresh-start.spec.ts` |
| `tests/README.md` | Accurate suite description | ✓ VERIFIED | Lists all seven specs, host-port note, single-worker rationale — no longer says "Specification only" |
| `backend/tests/roster/`, `backend/tests/chat/` | TEST-01/02 coverage | ✓ VERIFIED | Re-run confirms 300 passed including these modules |
| `frontend/src/components/*.test.tsx` (6 files) | TEST-03 coverage | ✓ VERIFIED | Re-run confirms 81 passed including these files |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scripts/start_mac.sh` | `docker/Dockerfile` | `docker build -f docker/Dockerfile` | ✓ WIRED | Confirmed in source |
| `scripts/start_mac.sh` | `database/skyfleet.db` | bind mount | ✓ WIRED | Confirmed in source; live write-through unverified |
| `docker/docker-compose.yml` | `docker/Dockerfile` | `build.dockerfile` | ✓ WIRED | Confirmed |
| `tests/docker-compose.test.yml` | `docker/Dockerfile` | app service builds production image | ✓ WIRED | Confirmed |
| `tests/specs/chat.spec.ts` | `backend/app/chat/llm.py` mock | `mock_reply` keyword contract | ✓ WIRED (source) | Confirmed by reading both files; live path unexercised |
| `tests/specs/sse-resilience.spec.ts` | `frontend/src/lib/useTelemetryStream.ts` | EventSource onopen/onerror | ✓ WIRED (source) | Confirmed by reading both files; live recovery unexercised |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend unit suite | `cd backend && uv run --extra dev pytest -q` | `300 passed, 6 skipped, 3 deselected` | ✓ PASS |
| Frontend unit suite | `cd frontend && npm test` | `81 passed` across `14 files` | ✓ PASS |
| Frontend production build | `cd frontend && npm run build` | Static export succeeds, generates `frontend/out` | ✓ PASS |
| E2E spec typecheck | `cd tests && npx tsc --noEmit --skipLibCheck` | exit 0 | ✓ PASS |
| No disabled/focused specs | `grep -rEn 'test\.(skip\|fixme\|only)' tests/specs/` | clean | ✓ PASS |
| No screenshot assertions | `grep -rE 'toHaveScreenshot\|toMatchSnapshot' tests/specs/` | none | ✓ PASS |
| Git-ignore of WAL/SHM sidecars | `git check-ignore -q database/skyfleet.db-wal`, `-shm` | both ignored; `.gitkeep` still tracked | ✓ PASS |
| Live Docker build/run/E2E harness | `docker info`, `docker compose ... up --build` | Docker unreachable; disk at 98% (3.0GB free) | ? SKIP (environment) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention exists in this project; the phase's own live-execution verification is the docker-compose harness itself, addressed under Behavioral Spot-Checks and Human Verification above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| DEPLOY-01 | 04-01 | Multi-stage Dockerfile serves both on port 8000 | Present/wired, live-unverified | Dockerfile confirmed structurally correct; no live build in this session |
| DEPLOY-02 | 04-01 | start_mac.sh/stop_mac.sh idempotent | Present/wired, live-unverified | Guards confirmed present + CR-01 fix confirmed; no live run |
| DEPLOY-03 | 04-01 | start_windows.ps1/stop_windows.ps1 idempotent | Present/wired, live-unverified (backstop truth by design — no Windows host in this env) | CR-02 fix confirmed; no Windows host available anywhere in this pipeline |
| DEPLOY-04 | 04-01 | SQLite persists via bind mount | Present/wired, live-unverified | Bind mount confirmed in compose + scripts; restart-persistence not observed |
| TEST-01 | 04-02 | Backend unit tests: roster service/repo/router | ✓ SATISFIED | Re-ran suite myself: 300 passed, roster tests included |
| TEST-02 | 04-02 | Backend unit tests: chat/LLM parsing + validation | ✓ SATISFIED | Same re-run; chat tests included; noun-to-test mapping read and confirmed plausible |
| TEST-03 | 04-02 | Frontend unit tests: 6 named components | ✓ SATISFIED | Re-ran suite myself: 81 passed across 14 files, all 6 named test files present |
| TEST-04 | 04-03, 04-04 | Playwright E2E: 6 scenarios | Present/wired, live-unverified | All 7 spec files exist, structurally sound, WR-01/WR-02 fixed; never observed passing live |
| TEST-05 | 04-03 | Browser isolated to test-only compose service | Present/wired, live-unverified | `tests/docker-compose.test.yml` structurally correct; browser-absence-in-production-image probe never run live |

No orphaned requirements — all 9 IDs (DEPLOY-01..04, TEST-01..05) appear in a plan's `requirements` frontmatter and in `.planning/REQUIREMENTS.md`'s Phase 4 mapping, all marked `[x]`/Complete there.

### Anti-Patterns Found

None. `grep -nE "TBD|FIXME|XXX"` across all phase-modified files (start scripts, compose files, E2E specs, README, MIGRATION.md, .dockerignore) returned nothing. No `TODO`/`HACK`/`PLACEHOLDER` markers found in the reviewed files. Code review (04-REVIEW.md) found 2 critical + 2 warning issues, all four independently confirmed fixed in source in this verification pass (CR-01, CR-02, WR-01, WR-02).

### Human Verification Required

See frontmatter `human_verification` block. Summary: five items, all rooted in the same underlying cause — this environment (and every environment the four plans executed in) lacks a working Docker daemon with sufficient disk space to run the live container build, the start/stop scripts against a real container, and the Playwright E2E harness. All code-level, static, and structural verification passed. The fifth item asks a human to make the final call on four LLM-judged (non-authoritative) prohibition assessments.

### Gaps Summary

No code-level gaps were found. Every artifact required by the phase's must-haves exists, is substantive (not a stub), and is wired to its dependencies by direct source inspection. Both unit test suites were re-run independently in this verification and reproduced their claimed baselines exactly (backend 300/6/3, frontend 81/14). All four code-review blockers/warnings (CR-01, CR-02, WR-01, WR-02) were independently confirmed fixed in the actual source files, not merely claimed fixed.

The remaining gap is purely one of live-execution evidence: the Docker build, the start/stop scripts' runtime idempotency, the bind-mount restart-persistence proof, and the full seven-spec Playwright E2E harness have never been observed passing in any of the four plan-execution sessions or in this verification session — all for the same documented, reproducible reason (Docker daemon unreachable and/or host disk at or near capacity). This routes the phase to `human_needed` rather than `gaps_found`, per the explicit environment-constraint framing provided for this verification: re-run the live Docker/Playwright harness from a session with a healthy Docker daemon and adequate free disk space, then close out the 5 open `unrun-verify` entries in `.planning/WINDOWS.md` before `/gsd-ship`.

---

_Verified: 2026-08-14T06:57:12Z_
_Verifier: Claude (gsd-verifier)_
