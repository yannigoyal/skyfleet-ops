"""Tests for the Database connection wrapper."""

from __future__ import annotations

import pytest

from app.db import Database
from app.db.seed import DEFAULT_FLEET


class TestEnsureInitialized:
    def test_creates_file_and_tables(self, tmp_path):
        path = tmp_path / "sub" / "skyfleet.db"
        database = Database(path)
        database.ensure_initialized()
        assert path.exists()

    def test_idempotent(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()
        database.ensure_initialized()  # must not raise or duplicate seed data

    async def test_seeds_default_operator_and_roster(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()

        profile = await database.fetchone("SELECT * FROM operator_profile WHERE id = 'default'")
        assert profile["energy_budget_kwh"] == 500.0

        roster = await database.fetchall("SELECT drone_id FROM fleet_roster ORDER BY drone_id")
        assert [row["drone_id"] for row in roster] == DEFAULT_FLEET

    async def test_seed_runs_once(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()
        database.ensure_initialized()

        roster = await database.fetchall("SELECT drone_id FROM fleet_roster")
        assert len(roster) == len(DEFAULT_FLEET)


class TestExecuteAndFetch:
    async def test_execute_and_fetchone(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()

        await database.execute(
            "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
            ("row-1", "default", "FALCON-99", "2026-01-01T00:00:00+00:00"),
        )
        row = await database.fetchone("SELECT * FROM fleet_roster WHERE drone_id = ?", ("FALCON-99",))
        assert row["id"] == "row-1"

    async def test_fetchone_returns_none_when_missing(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()

        row = await database.fetchone("SELECT * FROM fleet_roster WHERE drone_id = ?", ("NOPE",))
        assert row is None

    async def test_fetchall_returns_empty_list_when_no_rows(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()

        rows = await database.fetchall("SELECT * FROM missions")
        assert rows == []


class TestTransaction:
    async def test_commits_on_success(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()

        def _txn(conn):
            conn.execute(
                "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
                ("row-2", "default", "FALCON-98", "2026-01-01T00:00:00+00:00"),
            )
            return "ok"

        result = await database.transaction(_txn)
        assert result == "ok"

        row = await database.fetchone("SELECT * FROM fleet_roster WHERE drone_id = ?", ("FALCON-98",))
        assert row is not None

    async def test_rolls_back_on_exception(self, tmp_path):
        database = Database(tmp_path / "skyfleet.db")
        database.ensure_initialized()

        def _txn(conn):
            conn.execute(
                "INSERT INTO fleet_roster (id, operator_id, drone_id, added_at) VALUES (?, ?, ?, ?)",
                ("row-3", "default", "FALCON-97", "2026-01-01T00:00:00+00:00"),
            )
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await database.transaction(_txn)

        row = await database.fetchone("SELECT * FROM fleet_roster WHERE drone_id = ?", ("FALCON-97",))
        assert row is None
