"""Fleet context assembly for the flight-director prompt.

Reads live state through the existing mission/roster/telemetry layers so the
LLM sees exactly what the REST API would report.
"""

from __future__ import annotations

from app.db import Database
from app.missions import repository as missions_repository
from app.roster import repository as roster_repository
from app.telemetry import TelemetryCache


async def build_fleet_context(db: Database, cache: TelemetryCache) -> dict:
    """Snapshot of budget, active missions, and roster telemetry for the prompt."""
    budget = await missions_repository.get_energy_budget(db)
    remaining = await missions_repository.get_remaining_kwh(db)
    active_missions = await missions_repository.list_active_missions(db)
    roster_ids = await roster_repository.list_roster(db)

    drones = []
    batteries = []
    for drone_id in roster_ids:
        reading = cache.get(drone_id)
        entry: dict = {"drone_id": drone_id}
        if reading is not None:
            entry.update(
                battery_pct=reading.battery_pct,
                altitude_m=reading.altitude_m,
                speed_kmh=reading.speed_kmh,
                status=reading.status,
            )
            batteries.append(reading.battery_pct)
        drones.append(entry)

    return {
        "energy_budget_kwh": budget,
        "remaining_kwh": remaining,
        "active_mission_count": len(active_missions),
        "active_missions": [mission.to_dict() for mission in active_missions],
        "roster": drones,
        "average_battery_pct": round(sum(batteries) / len(batteries), 2) if batteries else None,
    }
