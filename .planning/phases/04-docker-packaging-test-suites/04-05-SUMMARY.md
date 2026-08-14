---
phase: 04-docker-packaging-test-suites
plan: 05
subsystem: infra
tags: [docker, shell, powershell, healthcheck, startup, uat-gap]

requires:
  - phase: 04-docker-packaging-test-suites
    provides: "start_mac.sh / start_windows.ps1 bind-mount launch scripts (04-01) that this plan adds a readiness wait to"
provides:
  - "scripts/wait_for_health.sh — bounded HTTP readiness poll with distinct exit codes for ready / timeout / curl-missing"
  - "scripts/tests/test_wait_for_health.sh — Docker-free behavioral test covering ready, late-start, and never-up cases"
  - "Readiness wait wired into both start scripts between `docker run -d` and the browser open"
affects: [deployment, operator-onboarding, uat]

actuals:
  tokens: 3400
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Operator-facing wait loops are deadline-bounded and degrade to a warning, never a hang or a non-zero script exit"
    - "Shell helpers get a Docker-free behavioral test driven by python3's stdlib http.server"

key-files:
  created:
    - scripts/wait_for_health.sh
    - scripts/tests/test_wait_for_health.sh
  modified:
    - scripts/start_mac.sh
    - scripts/start_windows.ps1

key-decisions:
  - "The readiness wait is a standalone helper rather than an inline loop, so its three behaviors can be pinned by a real test without Docker"
  - "PowerShell gets its own Wait-ForHealth function rather than shelling out to the bash helper — the two start scripts stay intentionally standalone"
  - "A readiness timeout warns and still opens the browser; it never aborts the script, so an unhealthy container degrades to today's behavior rather than a worse one"
  - "The poll silences curl's per-retry connection errors — a refused connection is the expected state during boot, and printing one per retry would bury the script's own status lines"

patterns-established:
  - "Ordering gates over shell/PowerShell scripts must filter comment lines (`grep -n X file | grep -v ':[[:space:]]*#'`) — an explanatory comment naming the grepped literal otherwise self-invalidates the gate"

requirements-completed: [DEPLOY-02, DEPLOY-03]

coverage:
  - id: D1
    description: "scripts/wait_for_health.sh exits 0 when the endpoint is already answering, exits 0 only after a late-starting endpoint comes up, and exits non-zero within its deadline when nothing is listening"
    requirement: DEPLOY-02
    verification:
      - kind: integration
        ref: "bash scripts/tests/test_wait_for_health.sh (3/3 cases; late start detected after 2s, dead port gave up after 3s)"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/start_mac.sh polls /api/health between `docker run -d` and the browser open, and a timeout warns without aborting the script under `set -euo pipefail`"
    requirement: DEPLOY-02
    verification:
      - kind: integration
        ref: "bash -n scripts/start_mac.sh + comment-filtered ordering assertion (poll line 47 < open line 66) + set -euo pipefail timeout-branch simulation reaching end-of-script with exit 0"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/start_windows.ps1 performs the same bounded poll before Start-Process opens the browser"
    requirement: DEPLOY-03
    verification:
      - kind: other
        ref: "comment-filtered ordering assertion (Wait-ForHealth call line 66 < Start-Process line 87) + structural check (balanced braces, AddSeconds deadline, paced Start-Sleep)"
        status: pass
    human_judgment: true
    rationale: "No pwsh on this host, so the script was never parsed or run by a PowerShell interpreter. Structural checks cannot prove runtime behavior on Windows — a real PowerShell 7.4+ run is required (UAT test 2)."
  - id: D4
    description: "The operator's first page load after running the start script is served by a ready server, with no intermediate error page (the G-04-2 symptom)"
    requirement: DEPLOY-02
    verification: []
    human_judgment: true
    rationale: "The reported symptom is a visual browser state during a live Docker launch. Docker was not exercised here (see Issues Encountered); only a human running ./scripts/start_mac.sh from the main checkout can confirm the error page window is gone."

duration: 14 min
completed: 2026-08-14
status: complete
---

# Phase 04 Plan 05: Start-Script Readiness Wait Summary

**Bounded `/api/health` poll (`scripts/wait_for_health.sh`, exit 0/1/2) wired between `docker run -d` and the browser open in both start scripts, pinned by a Docker-free three-case behavioral test.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-08-14T13:20:00Z
- **Completed:** 2026-08-14T13:34:00Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Closed gap G-04-2's single `missing` item in both start scripts: a bounded poll against `/api/health` now sits between container start and browser open, so the browser is no longer opened into the 2-3s uvicorn boot window.
- Pinned the poll's three behaviors with a test that needs no Docker — it serves a temp docroot containing `api/health` via `python3 -m http.server` and polls it with the real helper. The late-start case asserts elapsed time is at least 2s, so a helper that returned early or slept a fixed interval would fail it.
- Proved the degradation path directly: under `set -euo pipefail`, a poll timeout takes the warning branch and the script still reaches its end with exit 0, rather than aborting or hanging.
- Both script edits are pure insertions (41 added, 0 removed), so the CR-01/CR-02 idempotency guards, the bind mount, and the leftover-volume notice verified in UAT test 2 are provably untouched.

## Task Commits

1. **Task 1 (RED): failing behavioral test for the readiness poll** — `6af265a` (test) — 3 failures, exit 3, against the not-yet-existing helper
2. **Task 1 (GREEN): helper + start_mac.sh wiring** — `1ee3870` (feat)
3. **Task 2: start_windows.ps1 parity** — `3a0d32b` (feat)

## Files Created/Modified

- `scripts/wait_for_health.sh` — Polls a URL until it answers or the deadline passes. Exit 0 ready, 1 timeout, 2 curl unavailable. Deliberately no `set -e`: a failing curl is the loop's expected steady state.
- `scripts/tests/test_wait_for_health.sh` — Three cases (already-up, ~2s late, nothing listening) using ephemeral ports allocated by binding port 0, so it cannot collide with anything running.
- `scripts/start_mac.sh` — Waiting line, poll with a 60s timeout, and a three-way branch on the exit code, inserted before the "is running at" message so that message is only printed once true.
- `scripts/start_windows.ps1` — `Wait-ForHealth` function (deadline via `AddSeconds`, `Invoke-WebRequest -TimeoutSec 2`, paced `Start-Sleep`) defined near the top and called before `Start-Process`.

## Decisions Made

- **Standalone helper over an inline loop.** An inline loop in `start_mac.sh` could only have been verified by grepping the script. Extracting it makes the actual polling behavior testable, which is what the gap is about.
- **No cross-language reuse.** `start_windows.ps1` gets its own function; shelling out to a bash helper from PowerShell on a Windows host is not viable, and the two scripts were already intentionally standalone.
- **Timeout is a warning, not a failure.** The browser opens either way. A container that is merely slow should not leave the operator with a script that exited non-zero and no browser.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The poll printed a curl connection error on every retry**

- **Found during:** Task 1 (first GREEN run)
- **Issue:** The plan specified `curl -fsS`. `-S` forces error display even in silent mode, so the first green run emitted 17 `Failed to connect ... Couldn't connect to server` lines. During a real launch that is ~8-12 error lines scrolling past the operator during the boot window — the opposite of the calm startup this plan exists to produce, and in direct tension with the plan's own stated intent that the poll not write response detail into scrollback.
- **Fix:** Dropped `-S` and added `2>/dev/null`, keeping `-f` (fail on HTTP error) and `-s` (silent). Comment updated to record why the silencing is deliberate.
- **Files modified:** `scripts/wait_for_health.sh`
- **Verification:** Re-ran the behavioral test — 3/3 cases pass with clean output, no curl noise.
- **Committed in:** `1ee3870` (Task 1 commit)

**2. [Rule 1 - Bug] An explanatory comment self-invalidated the Windows ordering gate**

- **Found during:** Task 2 (running the plan's `<verify>` block)
- **Issue:** The gate asserts the `Wait-ForHealth` call precedes `Start-Process`. My own comment above the call read "Without this wait Start-Process opens the browser into the boot window", so `grep -n 'Start-Process' | head -1` matched the comment (line 63) rather than the real call (line 87), and the gate failed on correct code. This is exactly the comment-text-discipline hazard: a literal a gate greps for must not appear in nearby prose.
- **Fix:** Reworded the comment to "the browser is opened" (no cmdlet name), and hardened both scripts' ordering gates to filter comment lines via `grep -n X file | grep -v ':[[:space:]]*#'` so a future comment edit cannot silently break or falsely satisfy them.
- **Files modified:** `scripts/start_windows.ps1`
- **Verification:** Comment-filtered gate now reports call line 66 < `Start-Process` line 87; the same filtered form re-run against `start_mac.sh` confirms 47 < 66.
- **Committed in:** `3a0d32b` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both were defects in the plan's own specified commands rather than scope changes. No scope creep; the deliverable is exactly what the gap called for.

## Issues Encountered

**Docker was never exercised, so the live proof of the fix did not run here.** The `docker` CLI is present but the daemon was not reachable from this execution context. Everything verified above is Docker-free by construction (the behavioral test uses `python3 -m http.server`; the ordering and syntax checks are static). The end-to-end claim — that running `./scripts/start_mac.sh` now opens the browser onto a working console with no error-page window — is recorded as **unrun-verify** (coverage D4) for the human UAT re-run of test 2, from the main checkout rather than a worktree per 04-01-SUMMARY.md's Docker file-sharing constraint.

**PowerShell was never parsed.** No `pwsh` on this host, so `start_windows.ps1` has structural verification only (balanced braces, deadline computation, paced sleep, call ordering) and no interpreter check. Recorded as **unrun-verify** (coverage D3); UAT test 2's Windows half still requires a real PowerShell 7.4+ host.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- G-04-2's `missing` item is satisfied in both scripts. UAT test 2 can be re-run.
- Two unrun verifications are carried to the human: the live macOS/Linux launch (D4) and the Windows host run (D3). Neither is a code gap; both are environment limits of this execution context.
- No blockers for 04-06, which touches only `tests/` and shares no files with this plan.

---
*Phase: 04-docker-packaging-test-suites*
*Completed: 2026-08-14*
