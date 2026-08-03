# Telemetry Subsystem — Design Notes (archived)

Superseded by `planning/TELEMETRY_SUMMARY.md` once the subsystem was built. Kept for historical context on the design decisions made before implementation.

## Goals

- Single abstract interface (`TelemetrySource`) so the simulator and a real MAVLink gateway are interchangeable
- Thread-safe cache as the single point of truth for the SSE endpoint and future mission-execution code
- Realistic-feeling simulated fleet: battery drain should mean-revert around a drone's cruise profile rather than random-walk unboundedly, since raw GBM (as used for stock prices in other course projects) would let battery wander above 100% or below 0% without bound

## Considered Alternatives

- **WebSockets** — rejected; telemetry is one-way (server → dispatcher), SSE is simpler and reconnects natively
- **GBM for battery drain** — rejected; unbounded random walk doesn't model a physical battery. An Ornstein-Uhlenbeck-style mean-reverting process bounded to [0, 100] was chosen instead, with drain rate as the "mean" pull and turbulence as volatility
- **Raw MAVLink UDP/serial in-process** — rejected for v1; a REST gateway bridge keeps the backend simple and network-boundary-friendly. Direct MAVLink support is a future extension

## Correlation Model

Drones are grouped into squadrons by delivery zone. Squadrons flying through the same weather cell see correlated extra drain, modeled the same way sector correlation was used for stock groupings elsewhere: a Cholesky decomposition of a squadron correlation matrix applied to independent normal draws.
