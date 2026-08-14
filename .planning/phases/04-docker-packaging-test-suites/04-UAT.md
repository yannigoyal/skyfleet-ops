---
status: diagnosed
phase: 04-docker-packaging-test-suites
source: [04-VERIFICATION.md]
started: 2026-08-14T06:57:12Z
updated: 2026-08-14T07:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Live Docker build + bind-mount/restart-persistence proof
expected: |
  Run `./scripts/start_mac.sh --build`, then `docker inspect skyfleet-ops` for a bind mount at
  /app/database, then curl / and /api/health (both 200), then `docker restart skyfleet-ops` and
  confirm `GET /api/roster` returns the same drones before/after.
result: pass

### 2. Live start/stop script idempotency (bash + PowerShell)
expected: |
  Run `./scripts/start_mac.sh` and `./scripts/stop_mac.sh` each twice in a row (and the
  PowerShell equivalents on an actual Windows host), confirming idempotency and the corrected
  `docker volume inspect` / `docker image inspect` guards (CR-01/CR-02 fixes) behave as intended
  at runtime. Exactly one container after two start calls; both stop calls exit 0; the
  leftover-skyfleet-data-volume notice fires when the volume exists; start_windows.ps1 does not
  abort on a fresh install under PowerShell 7.4+.
result: issue
reported: "after starting the script it takes 2 3 second to load in the meantime the screen shows page is not working"
severity: major

### 3. Full Playwright E2E harness run (twice, back-to-back)
expected: |
  Run `cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
  --exit-code-from playwright` twice in a row without recreating the app container, covering all
  seven specs (health, fresh-start, roster, missions, visualization, chat, sse-resilience). All
  seven specs pass both runs; the suite demonstrates idempotency; `docker run --rm skyfleet-ops`
  shows no `/ms-playwright` directory and no `node` binary (TEST-05 image-isolation proof).
result: issue
reported: "failed to set up container networking: driver failed programming external connectivity on endpoint tests-app-1 (f1013b8e38c1b8c82f9dfba6539d60a014b9db70d6a4275f9b7713522f517c12): Bind for 0.0.0.0:8000 failed: port is already allocated"
severity: blocker

### 4. SSE reconnect behavior (state-transition invariant)
expected: |
  With the app running, stop the container's telemetry route (or the container itself) and
  confirm the connection indicator turns red/Disconnected; restore it and confirm the indicator
  returns to Live on its own, without a page reload — via the client's native EventSource retry,
  not a fresh page load standing in for reconnection.
result: pass

### 5. Judgment-tier prohibitions sign-off
expected: |
  Review the four judgment-tier prohibitions recorded across 04-01 through 04-04 (no silent data
  loss on the volume cutover; no test-weakening in the audit; no E2E spec that would pass with
  its target behavior removed) and confirm they hold in practice, not just by design. The
  verifier's non-authoritative LLM-judge assessment found all four plausible-to-strongly-
  supported; final sign-off belongs to a human.
result: pass

## Summary

total: 5
passed: 3
issues: 2
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-04-2
  truth: "Container builds and starts serving immediately after the start script opens the browser; no unresponsive-page state on first load."
  status: failed
  reason: "User reported: after starting the script it takes 2 3 second to load in the meantime the screen shows page is not working"
  severity: major
  test: 2
  root_cause: "scripts/start_mac.sh and scripts/start_windows.ps1 launch the container detached (docker run -d) and immediately open the browser, with no readiness wait or health-endpoint poll in between. uvicorn startup (uv env resolution, imports, DB init, telemetry warmup) takes ~2-3s, so the browser's first request always lands before the server is accepting connections."
  artifacts:
    - path: "scripts/start_mac.sh"
      issue: "no readiness wait/poll between `docker run -d` and `open`"
    - path: "scripts/start_windows.ps1"
      issue: "no readiness wait/poll between `docker run -d` and `Start-Process`"
  missing:
    - "Bounded polling loop against /api/health (curl / Invoke-WebRequest) between container start and browser open, in both scripts"
  debug_session: .planning/debug/start-script-browser-race.md

- gap_id: G-04-3
  truth: "The E2E test harness (tests/docker-compose.test.yml) starts its app service on port 8000 without conflicting with a production container already running on the same host port."
  status: failed
  reason: "User reported: failed to set up container networking: driver failed programming external connectivity on endpoint tests-app-1: Bind for 0.0.0.0:8000 failed: port is already allocated"
  severity: blocker
  test: 3
  root_cause: "tests/docker-compose.test.yml's app service hardcodes a host port publish (8000:8000) that is not actually needed: Playwright reaches the app via the internal Compose network (BASE_URL=http://app:8000) and the healthcheck's curl runs inside the app container's own namespace. This unnecessary host publish collides with scripts/start_mac.sh's long-lived production container (docker run -d -p 8000:8000). tests/README.md's existing note names the right fix command (./scripts/stop_mac.sh) but misattributes the cause to docker/docker-compose.yml (documented as optional sugar) instead of scripts/start_mac.sh, and documents a manual workaround rather than isolation — which doesn't satisfy the UAT's actual expectation that the harness runs independently of an already-running production container."
  artifacts:
    - path: "tests/docker-compose.test.yml"
      issue: "app service publishes unnecessary host port 8000:8000, colliding with any process already bound to host port 8000"
    - path: "tests/README.md"
      issue: "collision note misattributes the cause to docker/docker-compose.yml instead of scripts/start_mac.sh"
  missing:
    - "Drop (or remap to a non-default host port) the `ports:` mapping on tests/docker-compose.test.yml's app service"
    - "Correct tests/README.md's causal explanation to name scripts/start_mac.sh as the actual collision source"
  debug_session: .planning/debug/e2e-harness-port-conflict.md
