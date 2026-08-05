"""Background tasks that drive mission lifecycle: retrying queued
auto-assignment requests, completing arrived deliveries, and periodically
snapshotting the remaining energy budget for the budget chart.

Each loop delegates to a single-tick function (`process_due_assignments`,
`deliver_overdue_missions`, `record_budget_snapshot`) so the tick logic can
be unit tested without waiting on real sleeps.
"""

from __future__ import annotations

import asyncio
import logging

from app.db import Database
from app.telemetry import TelemetryCache

from . import repository, service
from .models import DEFAULT_CRUISE_SPEED_KMH, InsufficientBudgetError, Mission, NoEligibleDroneError
from .queue import MissionQueue

logger = logging.getLogger(__name__)


async def process_due_assignments(
    db: Database, cache: TelemetryCache, queue: MissionQueue, now: float | None = None
) -> None:
    """Retry drone assignment for every queued request whose backoff has elapsed."""
    for entry in queue.due(now=now):
        try:
            mission = await service.auto_assign_mission(
                db,
                cache,
                zone=entry.zone,
                distance_km=entry.distance_km,
                preferred_drone_id=entry.preferred_drone_id,
            )
        except (NoEligibleDroneError, InsufficientBudgetError) as exc:
            queue.record_failure(entry.id, str(exc))
        else:
            queue.remove(entry.id)
            logger.info("Queued mission for %s auto-assigned to %s", entry.zone, mission.drone_id)


async def run_assignment_scheduler(
    db: Database, cache: TelemetryCache, queue: MissionQueue, interval: float = 2.0
) -> None:
    while True:
        await asyncio.sleep(interval)
        await process_due_assignments(db, cache, queue)


async def deliver_overdue_missions(
    db: Database, cruise_speed_kmh: float = DEFAULT_CRUISE_SPEED_KMH
) -> list[Mission]:
    """Mark en_route missions delivered once their ETA (distance / cruise speed) has elapsed."""
    delivered = []
    for mission in await repository.get_overdue_en_route_missions(db, cruise_speed_kmh):
        await repository.mark_delivered(db, mission.id)
        delivered.append(mission)
        logger.info("Mission %s (drone %s) delivered", mission.id, mission.drone_id)
    return delivered


async def run_delivery_scheduler(
    db: Database, interval: float = 5.0, cruise_speed_kmh: float = DEFAULT_CRUISE_SPEED_KMH
) -> None:
    while True:
        await asyncio.sleep(interval)
        await deliver_overdue_missions(db, cruise_speed_kmh)


async def record_budget_snapshot(db: Database) -> None:
    await repository.insert_budget_snapshot(db)


async def run_budget_snapshot_loop(db: Database, interval: float = 30.0) -> None:
    while True:
        await asyncio.sleep(interval)
        await record_budget_snapshot(db)
