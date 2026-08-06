"""Default operator profile and fleet roster seed data."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

DEFAULT_OPERATOR_ID = "default"
DEFAULT_ENERGY_BUDGET_KWH = 500.0
DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """Insert the default operator profile and 10-drone roster if absent.

    Safe to call on every startup — a no-op once the operator row exists.
    """
    row = conn.execute(
        "SELECT 1 FROM operator_profile WHERE id = ?", (DEFAULT_OPERATOR_ID,)
    ).fetchone()
    if row is not None:
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO operator_profile (id, energy_budget_kwh, created_at) VALUES (?, ?, ?)",
        (DEFAULT_OPERATOR_ID, DEFAULT_ENERGY_BUDGET_KWH, now),
    )
    conn.executemany(
        "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
        [(str(uuid.uuid4()), DEFAULT_OPERATOR_ID, drone_id, now) for drone_id in DEFAULT_FLEET],
    )
    conn.commit()
