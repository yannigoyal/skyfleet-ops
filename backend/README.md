# SkyFleet Ops — Backend

FastAPI backend for the SkyFleet Ops drone fleet command center, managed as a `uv` project.

## Setup

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
```

## Layout

```
app/
├── main.py           # FastAPI app, lifespan-managed telemetry source
├── telemetry/        # Fleet telemetry: simulator, cache, SSE stream (complete)
└── db/               # SQLite schema and seed logic (planned — see planning/PLAN.md)
tests/
└── telemetry/        # Unit tests for the telemetry subsystem
```

See `CLAUDE.md` for the module API reference and `../planning/PLAN.md` for the full project specification.
