"""Tests for default operator/roster seed data."""

from __future__ import annotations

import sqlite3

from app.db.schema import SCHEMA_SQL
from app.db.seed import DEFAULT_ENERGY_BUDGET_KWH, DEFAULT_FLEET, DEFAULT_OPERATOR_ID, seed_if_empty


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


class TestSeedIfEmpty:
    def test_inserts_default_operator(self):
        conn = _fresh_conn()
        seed_if_empty(conn)
        row = conn.execute(
            "SELECT * FROM operator_profile WHERE id = ?", (DEFAULT_OPERATOR_ID,)
        ).fetchone()
        assert row["energy_budget_kwh"] == DEFAULT_ENERGY_BUDGET_KWH

    def test_inserts_ten_drones(self):
        conn = _fresh_conn()
        seed_if_empty(conn)
        rows = conn.execute("SELECT drone_id FROM fleet_roster ORDER BY drone_id").fetchall()
        assert [row["drone_id"] for row in rows] == DEFAULT_FLEET
        assert len(DEFAULT_FLEET) == 10

    def test_noop_when_operator_already_exists(self):
        conn = _fresh_conn()
        seed_if_empty(conn)
        seed_if_empty(conn)
        rows = conn.execute("SELECT * FROM fleet_roster").fetchall()
        assert len(rows) == 10
