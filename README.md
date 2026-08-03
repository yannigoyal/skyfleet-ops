# SkyFleet Ops — AI Drone Delivery Command Center

A real-time operations console for a simulated last-mile drone delivery fleet. Dispatchers watch live telemetry stream in from every aircraft, track active deliveries, and collaborate with an AI flight director that can analyze fleet health and dispatch missions via natural language.

Built as a capstone-style demonstration of orchestrated AI-agent development: a single shared specification in `planning/`, independent frontend/backend workstreams, and an architecture designed to be extended by coding agents one module at a time.

## Features

- **Live telemetry streaming** via SSE — battery, altitude, speed, and status for every drone in the fleet, updating twice a second
- **Simulated fleet physics** — mean-reverting battery drain, correlated squadron weather effects, and random wind-gust events for realistic drama
- **Mission control** — dispatch, recall, and monitor delivery missions against a shared energy budget (no real hardware required)
- **Fleet visualizations** — live map/grid view, battery sparklines, utilization heatmap, energy-budget chart over time
- **AI flight director** — chat assistant that reads fleet state, recommends dispatches, and auto-executes structured actions
- **Dark ops-console aesthetic** — high-contrast, data-dense, built for long shifts

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/`uv`) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Telemetry**: Built-in fleet simulator (default) or a real MAVLink gateway bridge (optional)

See [`planning/PLAN.md`](planning/PLAN.md) for the full specification.

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Run with Docker
docker build -f docker/Dockerfile -t skyfleet-ops .
docker run -v skyfleet-data:/app/database -p 8000:8000 --env-file .env skyfleet-ops

# Open http://localhost:8000
```

Or use the convenience scripts: `scripts/start_mac.sh` / `scripts/start_windows.ps1`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for the AI flight director |
| `MAVLINK_GATEWAY_URL` | No | URL of a real MAVLink telemetry gateway; omit to use the built-in simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |

## Project Structure

```
skyfleet-ops/
├── frontend/    # Next.js static export — ops console UI
├── backend/     # FastAPI uv project — telemetry, missions, chat
├── database/    # SQLite schema, seed data, migration notes
├── planning/    # Project specification and agent contracts
├── tests/       # Playwright E2E tests
├── docker/      # Dockerfile and compose files
└── scripts/     # Start/stop helpers
```

## Status

The telemetry subsystem (`backend/app/telemetry/`) is complete, tested, and ready to build on. The rest of the platform — mission/database layer, chat integration, and frontend — is specified in `planning/PLAN.md` and scaffolded for the next build phase.

## License

MIT — see [LICENSE](LICENSE).
