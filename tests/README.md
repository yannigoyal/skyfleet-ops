# End-to-End Tests

Playwright E2E tests against the fully built container (frontend + backend + SQLite), run with `LLM_MOCK=true` for speed and determinism. See `planning/PLAN.md` section 12 for the full testing strategy; unit tests live in `frontend/` and `backend/tests/` instead.

## Running

```bash
cd tests
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

This builds the app image from `../docker/Dockerfile`, starts it with `LLM_MOCK=true`, and runs the Playwright suite against it in a separate container — keeping browser dependencies out of the production image.

## Key scenarios (planned)

- Fresh start: default roster appears, 500 kWh budget shown, telemetry is streaming
- Add and remove a drone from the roster
- Launch a mission: energy budget decreases, mission appears, fleet updates
- Recall a mission: drone returns to base, mission status updates
- Fleet visualization: heatmap renders with correct colors, budget chart has data points
- AI chat (mocked): send a message, receive a response, mission dispatch appears inline
- SSE resilience: disconnect and verify reconnection

## Status

Specification only — the frontend and mission API this suite exercises are not yet built. `playwright.config.ts` and `specs/` are scaffolded so the suite can be filled in as those land.
