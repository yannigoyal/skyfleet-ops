---
status: diagnosed
trigger: "start-script-browser-race — After running the start script, the browser opens showing \"page not working\" for 2-3 seconds before the app becomes reachable."
created: 2026-08-14T07:32:34Z
updated: 2026-08-14T07:32:34Z
---

## Current Focus

hypothesis: CONFIRMED — both start scripts launch the container detached (`docker run -d`)
  and immediately open the browser with zero readiness wait/poll against the health
  endpoint in between, so the browser's first request races the container's boot
  sequence (interpreter start, `uv run` wrapper, module imports, uvicorn socket bind)
  and loses every time.
test: read scripts/start_mac.sh, scripts/start_windows.ps1, docker/Dockerfile,
  backend/app/main.py (lifespan), backend/app/db/connection.py, backend/app/telemetry/simulator.py,
  backend/app/chat/llm.py — traced the full sequence from `docker run -d` to first
  accepted HTTP connection and checked every candidate source of the 2-3s delay.
expecting: N/A — root cause confirmed, goal is find_root_cause_only (no fix stage).
next_action: none — return ROOT CAUSE FOUND to caller.

## Symptoms

expected: Container builds and starts serving immediately after the start script opens the browser; no unresponsive-page state on first load.
actual: after starting the script it takes 2 3 second to load in the meantime the screen shows page is not working
errors: None reported (browser shows a connection-refused / unreachable page, not an application error)
reproduction: Test 2 in UAT (.planning/phases/04-docker-packaging-test-suites/04-UAT.md) — run ./scripts/start_mac.sh (or start_windows.ps1) fresh
started: Discovered during UAT for phase 04 (docker-packaging-test-suites)

## Eliminated

- hypothesis: FastAPI lifespan startup work (lazy DB init, telemetry simulator warmup) is the dominant cause of the 2-3s delay.
  evidence: |
    `Database.ensure_initialized()` (backend/app/db/connection.py:41-51) is a synchronous
    `executescript` against a tiny SQLite schema plus `seed_if_empty` — sub-millisecond to
    low-single-digit-millisecond work, not seconds. `SimulatorTelemetrySource.start()`
    (backend/app/telemetry/simulator.py:257-268) only builds in-memory numpy arrays for 10
    drones and seeds the cache — no I/O, no sleeps. `litellm` (the one genuinely heavy
    import in the codebase) is imported lazily inside a function in
    backend/app/chat/llm.py:220, not at module load time, so it does not add to FastAPI
    app-import latency. None of this is fast enough to *cause* a 2-3s wait on its own, and
    critically: even if it were instant, the race would still exist because the start
    scripts never wait on anything after `docker run -d` returns.
  timestamp: 2026-08-14T07:32:34Z

## Evidence

- timestamp: 2026-08-14T07:32:34Z
  checked: scripts/start_mac.sh (lines 34-54)
  found: |
    `docker run -d ... "$IMAGE_NAME"` is called, then the very next non-cosmetic
    statement is `open "http://localhost:${PORT}"` (line 52-54). No curl/health-check
    loop, no `docker wait`, no `sleep`, no polling of `/api/health` anywhere in the file.
  implication: The browser is opened unconditionally right after `docker run -d` returns,
    with zero synchronization to server readiness.

- timestamp: 2026-08-14T07:32:34Z
  checked: scripts/start_windows.ps1 (lines 36-59)
  found: |
    Same pattern as the bash script: `docker run -d ...` followed immediately by
    `Start-Process "http://localhost:$Port"` (line 59), with only cosmetic
    `docker volume inspect` checks in between — no readiness wait/poll.
  implication: The Windows script has the identical race, confirming this is a design
    gap in both scripts rather than a platform-specific quirk.

- timestamp: 2026-08-14T07:32:34Z
  checked: docker/Dockerfile (lines 26-29) and semantics of `docker run -d`
  found: |
    CMD is `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`. `docker run -d`
    returns as soon as the container process is created/started by the Docker daemon —
    it does not wait for the process inside to finish booting or bind its port. Before
    uvicorn can accept a connection on 8000, the container must: start the Python
    interpreter, run the `uv run` wrapper (env resolution), import FastAPI/uvicorn/numpy/
    sqlite3 and all app modules (app.chat, app.missions, app.roster, app.telemetry), run
    the FastAPI lifespan startup (confirmed fast, see Eliminated), and only then bind and
    listen on port 8000.
  implication: There is a guaranteed, non-zero window between `docker run -d` returning
    and the port actually accepting connections — this is what a browser hitting the URL
    during that window sees as "page not working" (connection refused).

- timestamp: 2026-08-14T07:32:34Z
  checked: backend/app/main.py (lifespan, lines 59-79) and backend/app/db/connection.py,
    backend/app/telemetry/simulator.py, backend/app/chat/llm.py
  found: DB init and telemetry warmup are lightweight synchronous/in-memory operations;
    the one heavy dependency (litellm) is imported lazily, not at startup. See Eliminated
    entry for detail.
  implication: The 2-3s delay is not explained by unusually slow application-level startup
    work; it is consistent with normal container/process boot overhead (image layer setup,
    interpreter start, `uv run`, module imports, socket bind) racing against a start script
    that has no wait step at all — i.e., the missing readiness check is both necessary and
    sufficient to explain the symptom, independent of exactly how many hundred milliseconds
    each boot stage takes.

## Resolution

root_cause: |
  Both `scripts/start_mac.sh` and `scripts/start_windows.ps1` launch the container
  detached (`docker run -d ...`) and then immediately open the browser
  (`open "http://localhost:8000"` / `Start-Process "http://localhost:$Port"`) with no
  readiness wait or health-endpoint poll in between. `docker run -d` only guarantees the
  container process has been started, not that the FastAPI/uvicorn server inside it is
  yet accepting connections — which requires interpreter startup, `uv run` env resolution,
  module imports (FastAPI, uvicorn, numpy, sqlite3, and all `app.*` routers), and the
  FastAPI lifespan's DB-init/telemetry-warmup to complete first. That boot sequence
  reliably takes on the order of 2-3 seconds, and because nothing in either script waits
  for `/api/health` (or any equivalent signal) to return 200 before opening the browser,
  the browser's first request always lands inside that window and shows a
  connection-refused / "page not working" state until the server finishes booting up.
  This was checked against the alternative hypothesis of unusually slow FastAPI startup
  work (lazy DB init, simulator warmup, LLM client init) and that hypothesis was
  eliminated — those code paths are fast; the missing wait/poll is the sole root cause.
fix: (not applied — goal is find_root_cause_only)
verification: (not applicable — no fix stage in this mode)
files_changed: []
