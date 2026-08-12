"""Fleet roster business logic — bridges persistence and the telemetry source."""

from __future__ import annotations

import logging

from app.db import Database
from app.missions.repository import get_active_mission_for_drone
from app.missions.service import recall_mission
from app.telemetry import TelemetrySource

from . import repository
from .models import RosterEntry

logger = logging.getLogger(__name__)


async def add_drone(db: Database, source: TelemetrySource | None, drone_id: str) -> RosterEntry:
    """Persist a new roster entry, then register the drone for telemetry.

    Raises DroneAlreadyTrackedError if the drone is already tracked. The DB
    write is the source of truth: if telemetry registration fails after the
    row is committed, the failure is logged and the entry is still returned
    (D-04) — a telemetry gap self-heals on the next update cycle.
    """
    entry = await repository.add_drone(db, drone_id)

    if source is not None:
        try:
            await source.add_drone(drone_id)
        except Exception:
            logger.exception("telemetry sync failed for add_drone(%s)", drone_id)

    return entry


async def remove_drone(db: Database, source: TelemetrySource | None, drone_id: str) -> None:
    """Remove a drone from the roster, auto-recalling any active mission first (D-03).

    Order is check-first, then recall, then delete, then best-effort telemetry
    sync:
      1. Query whether the drone currently has an en-route mission. If so,
         invoke the same entry point manual dispatch uses for a recall — so
         the mission_log/budget_snapshots side effects are identical to an
         explicit DELETE /api/fleet/missions call. Querying first avoids
         using the "no active mission" error as control flow.
      2. Delete the fleet_roster row. Raises UnknownDroneError if the drone
         wasn't tracked; this propagates for the router to translate.
      3. Deregister from the telemetry source, mirroring add_drone's D-04
         pattern: this runs after the deletion has committed, outside any
         db.transaction() callback, and failures are logged, not raised.

    The recall and the roster-row deletion are two separate
    Database.transaction() acquisitions, not one spanning transaction
    (accepted tradeoff, D-03's costly reversibility rating). A crash between
    them leaves the mission recalled with the drone still on the roster;
    re-issuing DELETE finishes the job because step 1 becomes a no-op.
    """
    if await get_active_mission_for_drone(db, drone_id) is not None:
        await recall_mission(db, drone_id)

    await repository.remove_drone(db, drone_id)

    if source is not None:
        try:
            await source.remove_drone(drone_id)
        except Exception:
            logger.exception("telemetry sync failed for remove_drone(%s)", drone_id)
