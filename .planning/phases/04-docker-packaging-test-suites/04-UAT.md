---
status: testing
phase: 04-docker-packaging-test-suites
source: [04-VERIFICATION.md]
started: 2026-08-14T06:57:12Z
updated: 2026-08-14T06:57:12Z
---

## Current Test

number: 1
name: Live Docker build + bind-mount/restart-persistence proof
expected: |
  Container builds and serves both frontend and API on port 8000; bind mount type is `bind`
  sourced from the repo's database/ dir; roster identical across restart; database/skyfleet.db
  mtime advances.
awaiting: user response

## Tests

### 1. Live Docker build + bind-mount/restart-persistence proof
expected: |
  Run `./scripts/start_mac.sh --build`, then `docker inspect skyfleet-ops` for a bind mount at
  /app/database, then curl / and /api/health (both 200), then `docker restart skyfleet-ops` and
  confirm `GET /api/roster` returns the same drones before/after.
result: [pending]

### 2. Live start/stop script idempotency (bash + PowerShell)
expected: |
  Run `./scripts/start_mac.sh` and `./scripts/stop_mac.sh` each twice in a row (and the
  PowerShell equivalents on an actual Windows host), confirming idempotency and the corrected
  `docker volume inspect` / `docker image inspect` guards (CR-01/CR-02 fixes) behave as intended
  at runtime. Exactly one container after two start calls; both stop calls exit 0; the
  leftover-skyfleet-data-volume notice fires when the volume exists; start_windows.ps1 does not
  abort on a fresh install under PowerShell 7.4+.
result: [pending]

### 3. Full Playwright E2E harness run (twice, back-to-back)
expected: |
  Run `cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
  --exit-code-from playwright` twice in a row without recreating the app container, covering all
  seven specs (health, fresh-start, roster, missions, visualization, chat, sse-resilience). All
  seven specs pass both runs; the suite demonstrates idempotency; `docker run --rm skyfleet-ops`
  shows no `/ms-playwright` directory and no `node` binary (TEST-05 image-isolation proof).
result: [pending]

### 4. SSE reconnect behavior (state-transition invariant)
expected: |
  With the app running, stop the container's telemetry route (or the container itself) and
  confirm the connection indicator turns red/Disconnected; restore it and confirm the indicator
  returns to Live on its own, without a page reload — via the client's native EventSource retry,
  not a fresh page load standing in for reconnection.
result: [pending]

### 5. Judgment-tier prohibitions sign-off
expected: |
  Review the four judgment-tier prohibitions recorded across 04-01 through 04-04 (no silent data
  loss on the volume cutover; no test-weakening in the audit; no E2E spec that would pass with
  its target behavior removed) and confirm they hold in practice, not just by design. The
  verifier's non-authoritative LLM-judge assessment found all four plausible-to-strongly-
  supported; final sign-off belongs to a human.
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

None found at the code level. All gaps are live-execution evidence gaps caused by this sandbox
having no reachable Docker daemon and a host filesystem at 98% capacity (3.0GB free) — confirmed
independently by both the phase's executors (across three separate plan sessions) and by the
verifier. Every static, structural, and unit-test check passed, including a code review that
found and fixed two genuine blockers (CR-01, CR-02) and two warnings (WR-01, WR-02) in the start
scripts and E2E specs — all four fixes independently re-confirmed in source by the verifier.
