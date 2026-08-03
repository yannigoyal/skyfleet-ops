# Backend — Developer Guide

## Project Setup

```bash
cd backend
uv sync --extra dev   # Install all dependencies including test/lint tools
```

## Fleet Telemetry API

The telemetry subsystem lives in `app/telemetry/`. Use these imports:

```python
from app.telemetry import TelemetryCache, TelemetryUpdate, TelemetrySource, create_telemetry_source
```

### Core Types

- **`TelemetryUpdate`** — Immutable dataclass: `drone_id`, `battery_pct`, `previous_battery_pct`, `altitude_m`, `speed_kmh`, `status`, `timestamp`, plus properties `battery_delta`, `battery_direction` ("draining"/"charging"/"flat"), and `to_dict()` for JSON serialization.

- **`TelemetryCache`** — Thread-safe in-memory store. Key methods:
  - `update(drone_id, battery_pct, altitude_m, speed_kmh, status, timestamp=None) -> TelemetryUpdate`
  - `get(drone_id) -> TelemetryUpdate | None`
  - `get_battery(drone_id) -> float | None`
  - `get_all() -> dict[str, TelemetryUpdate]`
  - `remove(drone_id)`
  - `version` property — monotonic counter, increments on every update (for SSE change detection)

- **`TelemetrySource`** — Abstract interface implemented by `SimulatorTelemetrySource` and `MavlinkGatewayTelemetrySource`. Lifecycle: `start(drone_ids)` -> `add_drone()` / `remove_drone()` -> `stop()`.

- **`create_telemetry_source(cache)`** — Factory. Returns `MavlinkGatewayTelemetrySource` if `MAVLINK_GATEWAY_URL` is set, otherwise `SimulatorTelemetrySource`.

### SSE Streaming

```python
from app.telemetry import create_stream_router

router = create_stream_router(telemetry_cache)  # Returns FastAPI APIRouter
# Endpoint: GET /api/stream/telemetry (text/event-stream)
```

### Seed Data

Default fleet: FALCON-01 through FALCON-10. Seed telemetry and per-drone drain-rate/volatility params are in `app/telemetry/seed_fleet.py`.

## Running Tests

```bash
uv run --extra dev pytest -v              # All tests
uv run --extra dev pytest --cov=app       # With coverage
uv run --extra dev ruff check app/ tests/ # Lint
```

## Running the Dev Server

```bash
uv run uvicorn app.main:app --reload --port 8000
```
