"""SQLite-backed persistence for the fleet roster."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.db import Database

from .models import DroneAlreadyTrackedError, RosterEntry, UnknownDroneError

DEFAULT_OPERATOR_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def list_roster(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> list[str]:
    rows = await db.fetchall(
        "SELECT drone_id FROM fleet_roster WHERE operator_id = ? ORDER BY drone_id", (operator_id,)
    )
    return [row["drone_id"] for row in rows]


async def list_roster_entries(
    db: Database, operator_id: str = DEFAULT_OPERATOR_ID
) -> list[RosterEntry]:
    rows = await db.fetchall(
        "SELECT * FROM fleet_roster WHERE operator_id = ? ORDER BY drone_id", (operator_id,)
    )
    return [
        RosterEntry(
            id=row["id"],
            operator_id=row["operator_id"],
            drone_id=row["drone_id"],
            added_at=row["added_at"],
        )
        for row in rows
    ]


async def add_drone(
    db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID
) -> RosterEntry:
    entry = RosterEntry(
        id=str(uuid.uuid4()), operator_id=operator_id, drone_id=drone_id, added_at=_now()
    )
    try:
        await db.execute(
            "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
            (entry.id, entry.operator_id, entry.drone_id, entry.added_at),
        )
    except sqlite3.IntegrityError as exc:
        raise DroneAlreadyTrackedError(drone_id) from exc
    return entry


async def remove_drone(db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID) -> None:
    def _txn(conn: sqlite3.Connection) -> None:
        cursor = conn.execute(
            "DELETE FROM fleet_roster WHERE operator_id = ? AND drone_id = ?",
            (operator_id, drone_id),
        )
        if cursor.rowcount == 0:
            raise UnknownDroneError(drone_id)

    await db.transaction(_txn)
