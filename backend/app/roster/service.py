"""Fleet roster business logic — bridges persistence and the telemetry source."""

from __future__ import annotations

import logging

from app.db import Database
from app.telemetry import TelemetrySource

from . import repository
from .models import RosterEntry

logger = logging.getLogger(__name__)


async def add_drone(db: Database, source: TelemetrySource | None, drone_id: str) -> RosterEntry:
    """Persist a new roster entry, then register the drone for telemetry.

    Raises DroneAlreadyTrackedError if the drone is already tracked.
    """
    entry = await repository.add_drone(db, drone_id)

    if source is not None:
        await source.add_drone(drone_id)

    return entry
