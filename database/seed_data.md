# Default Seed Data

Applied by the backend the first time it starts against an empty database (see `planning/PLAN.md` section 7).

## `operator_profile`

One row: `id="default"`, `energy_budget_kwh=500.0`.

## `fleet_roster`

Ten drones: `FALCON-01` through `FALCON-10`, matching `backend/app/telemetry/seed_fleet.py::SEED_TELEMETRY` so the roster and the live telemetry stream agree on which drones exist from the first request.

## Notes for implementers

- Seeding must be idempotent — check for an existing `operator_profile` row before inserting, not just "does the file exist," since a volume can be reused across schema changes.
- `fleet_roster` drone IDs are the join key against the in-memory `TelemetryCache` — keep them in sync with `seed_fleet.py` if the default fleet size changes.
