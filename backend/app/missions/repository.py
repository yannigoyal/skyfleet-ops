"""SQLite-backed persistence for mission lifecycle state.

Energy accounting model: `remaining_kwh` is the operator's budget minus the
cumulative energy cost of every mission ever launched (read from the
append-only `mission_log`), not just currently en-route missions. Recalling
a drone does not refund the energy already spent flying out — see
DRONE_BACKEND_DESIGN.md section 6.2 for the "atomic mission, no refunds"
rationale.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.db import Database

from .models import DroneAlreadyEnRouteError, InsufficientBudgetError, Mission, NoActiveMissionError

DEFAULT_OPERATOR_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_mission(row: sqlite3.Row) -> Mission:
    return Mission(
        id=row["id"],
        operator_id=row["operator_id"],
        drone_id=row["drone_id"],
        zone=row["zone"],
        distance_km=row["distance_km"],
        energy_cost_kwh=row["energy_cost_kwh"],
        status=row["status"],
        updated_at=row["updated_at"],
    )


def _spent_kwh(conn: sqlite3.Connection, operator_id: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(energy_cost_kwh), 0) AS spent FROM mission_log "
        "WHERE operator_id = ? AND action = 'launch'",
        (operator_id,),
    ).fetchone()
    return row["spent"]


def _remaining_kwh(conn: sqlite3.Connection, operator_id: str) -> float:
    budget_row = conn.execute(
        "SELECT energy_budget_kwh FROM operator_profile WHERE id = ?", (operator_id,)
    ).fetchone()
    budget = budget_row["energy_budget_kwh"] if budget_row is not None else 0.0
    return round(budget - _spent_kwh(conn, operator_id), 4)


async def is_drone_on_roster(db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID) -> bool:
    row = await db.fetchone(
        "SELECT 1 FROM fleet_roster WHERE operator_id = ? AND drone_id = ?", (operator_id, drone_id)
    )
    return row is not None


async def list_roster_drone_ids(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> list[str]:
    rows = await db.fetchall(
        "SELECT drone_id FROM fleet_roster WHERE operator_id = ? ORDER BY drone_id", (operator_id,)
    )
    return [row["drone_id"] for row in rows]


async def get_active_mission_for_drone(
    db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID
) -> Mission | None:
    row = await db.fetchone(
        "SELECT * FROM missions WHERE operator_id = ? AND drone_id = ? AND status = 'en_route'",
        (operator_id, drone_id),
    )
    return _row_to_mission(row) if row is not None else None


async def list_active_missions(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> list[Mission]:
    rows = await db.fetchall(
        "SELECT * FROM missions WHERE operator_id = ? AND status = 'en_route' ORDER BY updated_at",
        (operator_id,),
    )
    return [_row_to_mission(row) for row in rows]


async def list_active_drone_ids(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> set[str]:
    rows = await db.fetchall(
        "SELECT drone_id FROM missions WHERE operator_id = ? AND status = 'en_route'", (operator_id,)
    )
    return {row["drone_id"] for row in rows}


async def get_energy_budget(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> float:
    row = await db.fetchone("SELECT energy_budget_kwh FROM operator_profile WHERE id = ?", (operator_id,))
    return row["energy_budget_kwh"] if row is not None else 0.0


async def get_remaining_kwh(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> float:
    return await db.transaction(lambda conn: _remaining_kwh(conn, operator_id))


async def create_mission(
    db: Database,
    drone_id: str,
    zone: str,
    distance_km: float,
    energy_cost_kwh: float,
    operator_id: str = DEFAULT_OPERATOR_ID,
) -> Mission:
    """Atomically validate the drone is free and the budget covers the cost, then dispatch.

    Runs inside one locked SQLite transaction so two concurrent launches
    can't both pass validation and jointly overdraw the budget or
    double-book a drone (see DRONE_BACKEND_DESIGN.md section 6.5).
    """
    mission_id = str(uuid.uuid4())
    now = _now()

    def _txn(conn: sqlite3.Connection) -> None:
        existing = conn.execute(
            "SELECT 1 FROM missions WHERE operator_id = ? AND drone_id = ? AND status = 'en_route'",
            (operator_id, drone_id),
        ).fetchone()
        if existing is not None:
            raise DroneAlreadyEnRouteError(drone_id)

        remaining = _remaining_kwh(conn, operator_id)
        if energy_cost_kwh > remaining:
            raise InsufficientBudgetError(energy_cost_kwh, remaining)

        conn.execute(
            "INSERT INTO missions "
            "(id, operator_id, drone_id, zone, distance_km, energy_cost_kwh, status, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'en_route', ?)",
            (mission_id, operator_id, drone_id, zone, distance_km, energy_cost_kwh, now),
        )
        conn.execute(
            "INSERT INTO mission_log "
            "(id, operator_id, drone_id, action, zone, energy_cost_kwh, executed_at) "
            "VALUES (?, ?, ?, 'launch', ?, ?, ?)",
            (str(uuid.uuid4()), operator_id, drone_id, zone, energy_cost_kwh, now),
        )
        conn.execute(
            "INSERT INTO budget_snapshots (id, operator_id, remaining_kwh, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), operator_id, round(remaining - energy_cost_kwh, 4), now),
        )

    await db.transaction(_txn)
    return Mission(
        id=mission_id,
        operator_id=operator_id,
        drone_id=drone_id,
        zone=zone,
        distance_km=distance_km,
        energy_cost_kwh=energy_cost_kwh,
        status="en_route",
        updated_at=now,
    )


async def recall(db: Database, drone_id: str, operator_id: str = DEFAULT_OPERATOR_ID) -> Mission:
    now = _now()

    def _txn(conn: sqlite3.Connection) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM missions WHERE operator_id = ? AND drone_id = ? AND status = 'en_route'",
            (operator_id, drone_id),
        ).fetchone()
        if row is None:
            raise NoActiveMissionError(drone_id)

        conn.execute(
            "UPDATE missions SET status = 'recalled', updated_at = ? WHERE id = ?", (now, row["id"])
        )
        conn.execute(
            "INSERT INTO mission_log "
            "(id, operator_id, drone_id, action, zone, energy_cost_kwh, executed_at) "
            "VALUES (?, ?, ?, 'recall', ?, ?, ?)",
            (str(uuid.uuid4()), operator_id, drone_id, row["zone"], row["energy_cost_kwh"], now),
        )
        remaining = _remaining_kwh(conn, operator_id)
        conn.execute(
            "INSERT INTO budget_snapshots (id, operator_id, remaining_kwh, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), operator_id, remaining, now),
        )
        return row

    row = await db.transaction(_txn)
    return Mission(
        id=row["id"],
        operator_id=row["operator_id"],
        drone_id=row["drone_id"],
        zone=row["zone"],
        distance_km=row["distance_km"],
        energy_cost_kwh=row["energy_cost_kwh"],
        status="recalled",
        updated_at=now,
    )


async def mark_delivered(db: Database, mission_id: str) -> None:
    await db.execute(
        "UPDATE missions SET status = 'delivered', updated_at = ? WHERE id = ?", (_now(), mission_id)
    )


async def get_overdue_en_route_missions(
    db: Database, cruise_speed_kmh: float, operator_id: str = DEFAULT_OPERATOR_ID
) -> list[Mission]:
    """En-route missions whose ETA (distance / cruise speed) has elapsed since launch."""
    missions = await list_active_missions(db, operator_id)
    now = datetime.now(timezone.utc)
    overdue = []
    for mission in missions:
        launched_at = datetime.fromisoformat(mission.updated_at)
        eta_hours = mission.distance_km / cruise_speed_kmh
        elapsed_hours = (now - launched_at).total_seconds() / 3600
        if elapsed_hours >= eta_hours:
            overdue.append(mission)
    return overdue


async def insert_budget_snapshot(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> None:
    def _txn(conn: sqlite3.Connection) -> None:
        remaining = _remaining_kwh(conn, operator_id)
        conn.execute(
            "INSERT INTO budget_snapshots (id, operator_id, remaining_kwh, recorded_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), operator_id, remaining, _now()),
        )

    await db.transaction(_txn)


async def list_budget_snapshots(db: Database, operator_id: str = DEFAULT_OPERATOR_ID) -> list[dict]:
    rows = await db.fetchall(
        "SELECT remaining_kwh, recorded_at FROM budget_snapshots WHERE operator_id = ? ORDER BY recorded_at",
        (operator_id,),
    )
    return [{"remaining_kwh": row["remaining_kwh"], "recorded_at": row["recorded_at"]} for row in rows]
