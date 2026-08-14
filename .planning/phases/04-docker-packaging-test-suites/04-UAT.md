---
status: complete
phase: 04-docker-packaging-test-suites
source: [04-VERIFICATION.md]
started: 2026-08-14T06:57:12Z
updated: 2026-08-14T12:14:00Z
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

### 2. Live start/stop script idempotency (bash + PowerShell) — re-test after G-04-2 fix
expected: |
  Run `./scripts/start_mac.sh` and confirm the browser no longer shows an unresponsive/"page not
  working" state — start_mac.sh now polls `/api/health` (up to 60s) before opening the browser.
  Then run `./scripts/stop_mac.sh`, and run both twice in a row to confirm idempotency still
  holds. (PowerShell equivalents require an actual Windows host — mark blocked if unavailable.)
result: pass

### 3. Full Playwright E2E harness run (twice, back-to-back) — re-test after G-04-3 fix
expected: |
  With a production `skyfleet-ops` container already running (from Test 2) on port 8000, run
  `cd tests && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
  --exit-code-from playwright`. The harness no longer publishes a host port, so it should no
  longer collide with the running production container. All seven specs pass; the healthcheck
  (now a python3 urllib probe instead of curl, which doesn't exist in the app image) reports
  healthy.
result: pass

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
passed: 5
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-04-2
  status: resolved
  resolved_by: 04-05-PLAN.md
  resolved_at: 2026-08-14
  truth: "Container builds and starts serving immediately after the start script opens the browser; no unresponsive-page state on first load."
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
  status: resolved
  resolved_by: 04-06-PLAN.md
  resolved_at: 2026-08-14
  truth: "The E2E test harness (tests/docker-compose.test.yml) starts its app service on port 8000 without conflicting with a production container already running on the same host port."
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
  note: "Executor also found and fixed a second, previously-hidden blocker while proving this fix live: the harness healthcheck used `curl`, which does not exist in the python:3.12-slim app image, so the app was permanently unhealthy and playwright's `service_healthy` gate could never pass even with the port conflict fixed. Replaced with a python3 urllib probe (tests/docker-compose.test.yml only; no production image change)."
