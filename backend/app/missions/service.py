"""Mission launch/recall validation and drone-assignment logic.

Two entry points into mission creation:
  - launch_mission(): explicit drone_id, used by the manual dispatch bar and
    direct API/chat calls. Fails fast if the target drone isn't eligible.
  - auto_assign_mission(): no drone_id given; picks the best eligible drone
    itself. Used for auto-assigned launches and by the scheduler when
    retrying a queued request.

Both ultimately call repository.create_mission(), which is the single
atomic point where drone-availability and budget checks are enforced
against concurrent launches.
"""

from __future__ import annotations

from app.db import Database
from app.telemetry import TelemetryCache

from . import repository
from .models import UNSAFE_TELEMETRY_STATUSES, DroneUnavailableError, Mission, NoEligibleDroneError, UnknownDroneError


async def launch_mission(
    db: Database, cache: TelemetryCache, *, drone_id: str, zone: str, distance_km: float
) -> Mission:
    """Validate and dispatch a mission to an explicit drone.

    Raises UnknownDroneError, DroneUnavailableError, DroneAlreadyEnRouteError,
    or InsufficientBudgetError on failure.
    """
    if not await repository.is_drone_on_roster(db, drone_id):
        raise UnknownDroneError(drone_id)

    reading = cache.get(drone_id)
    if reading is not None and reading.status in UNSAFE_TELEMETRY_STATUSES:
        raise DroneUnavailableError(drone_id)

    energy_cost_kwh = Mission.energy_cost_for(distance_km)
    return await repository.create_mission(db, drone_id, zone, distance_km, energy_cost_kwh)


async def recall_mission(db: Database, drone_id: str) -> Mission:
    """Recall the drone's active mission. Raises NoActiveMissionError if none."""
    return await repository.recall(db, drone_id)


async def find_eligible_drone(
    db: Database, cache: TelemetryCache, *, preferred_drone_id: str | None = None
) -> str | None:
    """Pick a drone for auto-assignment: on roster, idle, telemetry-safe.

    Prefers `preferred_drone_id` if it's still eligible, otherwise the
    eligible candidate with the highest battery (ties broken by drone_id).
    Returns None if no drone currently qualifies.
    """
    active_drone_ids = await repository.list_active_drone_ids(db)

    def _is_eligible(candidate_id: str) -> bool:
        if candidate_id in active_drone_ids:
            return False
        reading = cache.get(candidate_id)
        return reading is not None and reading.status not in UNSAFE_TELEMETRY_STATUSES

    if (
        preferred_drone_id is not None
        and await repository.is_drone_on_roster(db, preferred_drone_id)
        and _is_eligible(preferred_drone_id)
    ):
        return preferred_drone_id

    roster = await repository.list_roster_drone_ids(db)
    candidates = [
        (cache.get(candidate_id).battery_pct, candidate_id)
        for candidate_id in roster
        if _is_eligible(candidate_id)
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda pair: (-pair[0], pair[1]))
    return candidates[0][1]


async def auto_assign_mission(
    db: Database,
    cache: TelemetryCache,
    *,
    zone: str,
    distance_km: float,
    preferred_drone_id: str | None = None,
) -> Mission:
    """Attempt immediate auto-assignment and dispatch.

    Raises NoEligibleDroneError if no drone is currently eligible, or
    InsufficientBudgetError if the budget can't cover it (surfaced by the
    atomic repository.create_mission call).
    """
    drone_id = await find_eligible_drone(db, cache, preferred_drone_id=preferred_drone_id)
    if drone_id is None:
        raise NoEligibleDroneError(zone)

    energy_cost_kwh = Mission.energy_cost_for(distance_km)
    return await repository.create_mission(db, drone_id, zone, distance_km, energy_cost_kwh)
