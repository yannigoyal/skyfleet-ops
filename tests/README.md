# End-to-End Tests

Playwright E2E tests against the full stack (frontend + backend + SQLite), run with `LLM_MOCK=true` for speed and determinism. See `planning/PLAN.md` section 12 for the full testing strategy; unit tests live in `frontend/` and `backend/tests/` instead.

## Running in Docker

```bash
cd tests
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

This builds the app image from `../docker/Dockerfile`, starts it with `LLM_MOCK=true`, and runs the suite against it in a separate container — keeping browser dependencies out of the production image. The Playwright image tag and the `@playwright/test` version in `package.json` must be bumped together.

## Running against a local backend

Same single-origin setup as the container, without Docker:

```bash
cd frontend && npm run build && cp -r out ../backend/static
cd ../backend && LLM_MOCK=true uv run uvicorn app.main:app --port 8000
cd ../tests && npm ci && npx playwright install chromium && npx playwright test
```

## Scenarios

| Spec | Covers |
|---|---|
| `health.spec.ts` | Backend health endpoint |
| `fresh-start.spec.ts` | Default roster, energy budget, live telemetry updates |
| `roster.spec.ts` | Add and remove a drone |
| `missions.spec.ts` | Launch (budget spent, mission listed) and recall |
| `visualization.spec.ts` | Heatmap tiles and battery colors, budget chart data |
| `chat.spec.ts` | Mocked flight director: status reply, launch and recall with inline confirmations |
| `sse.spec.ts` | Connection indicator, EventSource reconnection after a dropped stream |

Tests share one backend and mutate its state, so the suite runs with a single worker and each spec cleans up the missions and roster entries it creates.
