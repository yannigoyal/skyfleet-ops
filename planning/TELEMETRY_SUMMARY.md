# Fleet Telemetry Backend — Summary

**Status:** Complete, tested, passing.

## What Was Built

A complete fleet telemetry subsystem in `backend/app/telemetry/` (8 modules, ~650 lines) providing live drone telemetry simulation and a real-hardware bridge via a unified interface.

### Architecture

```
TelemetrySource (ABC)
├── SimulatorTelemetrySource        →  mean-reverting fleet simulator (default, no gateway needed)
└── MavlinkGatewayTelemetrySource   →  REST poller for a MAVLink bridge (when MAVLINK_GATEWAY_URL set)
        │
        ▼
   TelemetryCache (thread-safe, in-memory)
        │
        ├──→ SSE stream endpoint (/api/stream/telemetry)
        ├──→ Mission validation (planned)
        └──→ Fleet health scoring (planned)
```

### Modules

| File | Purpose |
|------|---------|
| `models.py` | `TelemetryUpdate` — immutable frozen dataclass (drone_id, battery_pct, previous_battery_pct, altitude_m, speed_kmh, status, timestamp, battery_delta, battery_direction) |
| `interface.py` | `TelemetrySource` — abstract base class defining `start/stop/add_drone/remove_drone/get_drone_ids` |
| `cache.py` | `TelemetryCache` — thread-safe reading store with version counter for SSE change detection |
| `seed_fleet.py` | Realistic seed telemetry, per-drone drain-rate/volatility params, squadron correlation groups |
| `simulator.py` | `FleetSimulator` (Ornstein-Uhlenbeck-style battery drain with Cholesky-correlated squadron turbulence) + `SimulatorTelemetrySource` |
| `mavlink_gateway.py` | `MavlinkGatewayTelemetrySource` — REST polling client for a MAVLink bridge service |
| `factory.py` | `create_telemetry_source()` — selects simulator or gateway based on `MAVLINK_GATEWAY_URL` env var |
| `stream.py` | `create_stream_router()` — FastAPI SSE endpoint factory using version-based change detection |

### Key Design Decisions

- **Strategy pattern** — both telemetry sources implement the same ABC; downstream code is source-agnostic
- **TelemetryCache as single point of truth** — producers write, consumers read; no direct coupling
- **Mean-reverting drain, not unbounded random walk** — a raw geometric random walk (as used for stock prices in other course projects) would let battery wander outside [0, 100]. Battery drains steadily toward zero with correlated turbulence layered on, and is clamped every tick
- **Squadron-correlated turbulence** — Cholesky decomposition of a squadron correlation matrix; north squadron correlates at 0.55, south at 0.45, cross-squadron/solo drones lower
- **Random wind-gust events** — ~0.1% chance per tick per drone of an extra 1.5-4% battery hit for visual drama
- **SSE over WebSockets** — simpler, one-way push, universal browser support

## Test Suite

**69 tests, all passing.** 6 test modules in `backend/tests/telemetry/`.

| Module | Tests | Coverage |
|--------|-------|----------|
| test_models.py | 9 | models.py: 100% |
| test_cache.py | 15 | cache.py: 100% |
| test_simulator.py | 20 | simulator.py: 97% |
| test_simulator_source.py | 8 | (integration tests) |
| test_factory.py | 8 | factory.py: 100% |
| test_mavlink_gateway.py | 9 | mavlink_gateway.py: 81% (expected — network paths mocked) |

Overall coverage: 83% (main.py and stream.py's SSE generator are exercised by the E2E suite, not unit tests).

## Bug Found and Fixed During Testing

A flaky `test_low_battery_status_transition` test caught a real rounding bug: `simulator.py` computed the `low_battery`/`in_flight` status threshold against the *unrounded* battery value, then stored the *rounded* value in the cache. A battery of `20.004` rounded to a displayed `20.0` (at or below the 20% threshold) while status was still computed as `in_flight` (using `20.004 > 20.0`). Fixed by rounding battery to 2 decimal places before the threshold comparison, so the displayed value and the status always agree.

## Usage for Downstream Code

```python
from app.telemetry import TelemetryCache, create_telemetry_source

# Startup
cache = TelemetryCache()
source = create_telemetry_source(cache)  # Reads MAVLINK_GATEWAY_URL
await source.start(["FALCON-01", "FALCON-02", ...])

# Read telemetry
reading = cache.get("FALCON-01")            # TelemetryUpdate or None
battery = cache.get_battery("FALCON-01")    # float or None
all_readings = cache.get_all()              # dict[str, TelemetryUpdate]

# Dynamic fleet roster
await source.add_drone("FALCON-11")
await source.remove_drone("FALCON-02")

# Shutdown
await source.stop()
```
