# End-to-End Tests

Playwright E2E tests against the fully built container (frontend + backend + SQLite), run with `LLM_MOCK=true` for speed and determinism. See `planning/PLAN.md` section 12 for the full testing strategy; unit tests live in `frontend/` and `backend/tests/` instead.

## Running

```bash
cd tests
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

This builds the app image from `../docker/Dockerfile`, starts it with `LLM_MOCK=true`, and runs the Playwright suite against it in a separate container — keeping browser dependencies out of the production image.

**Before running:** stop any dev container first (`./scripts/stop_mac.sh` or `./scripts/stop_windows.ps1`) — the test compose file publishes the same host port (8000) as the production `docker/docker-compose.yml`, and the two will conflict if both try to bind it.

## Specs

Seven spec files under `specs/`, run against one shared app container holding one energy budget, one roster, and one mission list:

| File | Covers |
|------|--------|
| `health.spec.ts` | `/api/health` returns 200 |
| `fresh-start.spec.ts` | Default ten-drone roster, 500.0 kWh total budget, live telemetry (TEST-04 scenario 1) |
| `roster.spec.ts` | Adding/removing a drone via the API, reflected in the roster panel and dispatch selector (TEST-04 scenario 2) |
| `missions.spec.ts` | Launch/recall through the dispatch bar, header budget decrease, missions table, active mission count round trip (TEST-04 scenario 3) |
| `visualization.spec.ts` | Fleet heatmap cells (structural, per D-03), energy-budget chart line, per-row sparklines (TEST-04 scenario 4) |
| `chat.spec.ts` | Mocked flight-director launch/recall via chat, inline confirmation cards (TEST-04 scenario 5) |
| `sse-resilience.spec.ts` | Telemetry stream disconnect and unaided reconnect, no reload standing in for recovery (TEST-04 scenario 6) |

## Execution model

The suite runs serially against one app container: `playwright.config.ts` sets `workers: 1` and `fullyParallel: false` because all seven specs share one mutable fleet state (one energy budget, one roster, one mission list) — parallel workers would interleave mutations and produce failures that look like product bugs but are test-harness artifacts. Each mutating spec cleans up after itself via `helpers.ts`'s `restoreFleetState` (registered in `afterEach`), which is what makes the suite safe to run twice in a row without recreating the app container between runs.

## Status

Implemented — all six TEST-04 scenarios plus the pre-existing health check are covered by the seven spec files listed above, driven by `helpers.ts`'s shared fixtures (`getFleet`, `getRoster`, `readHeaderRemainingKwh`, `pickIdleDrone`, `restoreFleetState`).
