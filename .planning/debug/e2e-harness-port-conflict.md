---
status: diagnosed
trigger: "Investigate issue: e2e-harness-port-conflict — The Playwright E2E test harness (tests/docker-compose.test.yml) fails to start because its app service tries to bind host port 8000, which is already occupied by a production container started via scripts/start_mac.sh."
created: 2026-08-14T00:00:00Z
updated: 2026-08-14T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — tests/docker-compose.test.yml's `app` service publishes a hardcoded host port `8000:8000` that is unnecessary for the harness's own operation (Playwright reaches the app via the internal Compose DNS name `http://app:8000`, and the healthcheck's `curl http://localhost:8000` runs inside the app container's own namespace) but collides with any other process already bound to host port 8000 — including scripts/start_mac.sh's long-lived, detached `docker run -d -p 8000:8000` production container.
test: read tests/docker-compose.test.yml, docker/docker-compose.yml, scripts/start_mac.sh, docker/Dockerfile, tests/README.md, 04-04-SUMMARY.md, 04-VERIFICATION.md, 04-UAT.md
expecting: confirm exact collision source and whether tests/README.md's existing note adequately documents/prevents it
next_action: none — diagnose-only mode, root cause confirmed, returning to caller

## Symptoms

expected: Running `cd tests && docker compose -f docker-compose.test.yml up --build ...` succeeds and runs the full E2E suite twice back-to-back, independent of whether a production skyfleet-ops container is already running on port 8000.
actual: "failed to set up container networking: driver failed programming external connectivity on endpoint tests-app-1: Bind for 0.0.0.0:8000 failed: port is already allocated"
errors: "Bind for 0.0.0.0:8000 failed: port is already allocated"
reproduction: Test 3 in UAT (.planning/phases/04-docker-packaging-test-suites/04-UAT.md) — with a skyfleet-ops container already running from Test 2 (scripts/start_mac.sh), run the tests/docker-compose.test.yml harness
started: Discovered during UAT for phase 04, immediately after testing scripts/start_mac.sh in Test 2

## Eliminated

(none — root cause found on first pass; no competing hypotheses required elimination)

## Evidence

- timestamp: investigation
  checked: tests/docker-compose.test.yml lines 1-16
  found: |
    app service publishes `ports: - "8000:8000"` (fixed host-port mapping, no override
    mechanism, no dynamic/ephemeral port allocation). Healthcheck is
    `curl -f http://localhost:8000/api/health` — this CMD healthcheck executes inside the
    app container's own network namespace, not on the host, so it does not require the
    host port publish to function. The `playwright` service is configured with
    `BASE_URL: "http://app:8000"` — the internal Compose service DNS name/port, reachable
    over the private Compose network without any host port publish at all.
  implication: The `ports: "8000:8000"` line in tests/docker-compose.test.yml is not
    required for the E2E suite to function (Playwright never touches localhost:8000 on
    the host); it exists purely for optional external/host access. This makes it the
    direct, avoidable cause of the collision.

- timestamp: investigation
  checked: docker/docker-compose.yml lines 1-14
  found: production convenience-wrapper compose file also hardcodes `ports: - "8000:8000"`.
    Header comment: "Convenience wrapper for local runs. Production deployment is a single
    `docker run` (see README.md) — this file is optional sugar on top of that."
  implication: docker/docker-compose.yml is NOT the primary documented launch path; it is
    explicitly a secondary convenience file.

- timestamp: investigation
  checked: scripts/start_mac.sh lines 34-40
  found: |
    docker run -d --name skyfleet-ops -v "$ROOT_DIR/database:/app/database" \
      -p "8000:8000" --env-file .env skyfleet-ops
    Container is started detached (-d) and named, with no auto-stop — it remains bound to
    host port 8000 indefinitely until the operator runs scripts/stop_mac.sh.
  implication: This is the actual production entry point exercised in UAT Test 2 (per
    PLAN.md section 11, the documented single-command launch flow). It does NOT go through
    docker/docker-compose.yml at all — it's a raw `docker run` invocation. It binds host
    port 8000 and stays running, which is exactly what collided with the E2E harness in
    UAT Test 3.

- timestamp: investigation
  checked: tests/README.md line 14 (the "Before running" note)
  found: |
    "Before running: stop any dev container first (`./scripts/stop_mac.sh` or
    `./scripts/stop_windows.ps1`) — the test compose file publishes the same host port
    (8000) as the production `docker/docker-compose.yml`, and the two will conflict if
    both try to bind it."
  implication: The note DOES name the correct remediation command (`./scripts/stop_mac.sh`,
    the exact counterpart to the script that caused the collision in UAT Test 2) — so
    procedurally, following the note's instruction would have avoided the failure. However
    the note's stated CAUSAL EXPLANATION is imprecise/misleading: it attributes the
    conflict to "the production `docker/docker-compose.yml`" — a secondary convenience
    wrapper the header comment itself says most users won't invoke — rather than to
    scripts/start_mac.sh's raw `docker run -p 8000:8000`, which is the actual documented
    single-command launch path (PLAN.md section 11) and the one UAT Test 2 exercised. A
    reader who only runs `scripts/start_mac.sh` (never touching docker/docker-compose.yml)
    could reasonably read this note and think it doesn't apply to them, even though it does.

- timestamp: investigation
  checked: .planning/phases/04-docker-packaging-test-suites/04-UAT.md gap G-04-3
  found: |
    truth: "The E2E test harness (tests/docker-compose.test.yml) starts its app service on
    port 8000 without conflicting with a production container already running on the same
    host port." status: failed.
  implication: The UAT's stated expected behavior is harness/production INDEPENDENCE
    (the suite should succeed regardless of what else is running on port 8000), not merely
    "documented as a manual pre-flight step." A README note requiring the operator to
    manually stop the other container first does not satisfy this expectation even when
    its instructions are followed correctly — it is a workaround, not the isolation the
    UAT scenario calls for. Given Evidence entry 1 (the host port publish is functionally
    unnecessary for the harness to operate), the adequate fix is structural: drop or
    remap the test harness's host port publish, not just improve documentation wording.

## Resolution

root_cause: "tests/docker-compose.test.yml's `app` service hardcodes a host port publish (`8000:8000`) that duplicates the port used by scripts/start_mac.sh's long-lived, detached production container (`docker run -d -p 8000:8000`) — and that host port publish is not actually required for the E2E suite to function, since Playwright reaches the app over the internal Compose network via `http://app:8000` and the healthcheck's `curl http://localhost:8000` executes inside the app container's own namespace. tests/README.md's existing note (line 14) gives the correct remediation command (`./scripts/stop_mac.sh`) but misattributes the collision's cause to the secondary `docker/docker-compose.yml` convenience wrapper rather than to `scripts/start_mac.sh`'s raw `docker run` (the actual documented single-command production launch path per PLAN.md section 11, and the one exercised in UAT Test 2) — under-documenting the specific collision this UAT gap reports. More importantly, the UAT's expected behavior (G-04-3) calls for the harness to succeed independent of any running production container, which a manual-pre-stop documentation note cannot satisfy even when accurate — this is a structural/design gap in the test harness, not solely a documentation gap."
fix: ""
verification: ""
files_changed: []
