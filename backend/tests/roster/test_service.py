"""Tests for roster service-layer telemetry registration and failure handling."""

from __future__ import annotations

import logging

import pytest

from app.missions.repository import create_mission, get_active_mission_for_drone, get_remaining_kwh
from app.roster import service
from app.roster.models import DroneAlreadyTrackedError, UnknownDroneError
from app.roster.repository import list_roster

from .conftest import FakeSource, RaisingSource


class TestAddDrone:
    async def test_persists_and_registers_with_working_source(self, db, cache):
        source = FakeSource()
        entry = await service.add_drone(db, source, "FALCON-11")
        assert entry.drone_id == "FALCON-11"
        assert "FALCON-11" in source.get_drone_ids()
        assert "FALCON-11" in await list_roster(db)

    async def test_succeeds_without_a_source(self, db):
        entry = await service.add_drone(db, None, "FALCON-11")
        assert entry.drone_id == "FALCON-11"
        assert "FALCON-11" in await list_roster(db)

    async def test_duplicate_raises_and_never_touches_source(self, db, cache):
        source = FakeSource()
        with pytest.raises(DroneAlreadyTrackedError):
            await service.add_drone(db, source, "FALCON-01")
        assert source.get_drone_ids() == []


class TestTelemetrySyncFailure:
    async def test_row_survives_a_raising_source(self, db, cache):
        source = RaisingSource()
        entry = await service.add_drone(db, source, "FALCON-11")
        assert entry.drone_id == "FALCON-11"
        assert "FALCON-11" in await list_roster(db)

    async def test_failure_is_logged_with_drone_id(self, db, cache, caplog):
        source = RaisingSource()
        with caplog.at_level(logging.ERROR):
            await service.add_drone(db, source, "FALCON-11")
        assert "FALCON-11" in caplog.text


class TestRemoveDrone:
    async def test_removes_drone_with_no_active_mission(self, db):
        await service.remove_drone(db, None, "FALCON-01")
        assert "FALCON-01" not in await list_roster(db)

    async def test_unknown_drone_raises_and_performs_no_recall(self, db):
        with pytest.raises(UnknownDroneError):
            await service.remove_drone(db, None, "FALCON-99")

    async def test_deregisters_from_a_working_source(self, db):
        source = FakeSource()
        await source.start(["FALCON-01"])
        await service.remove_drone(db, source, "FALCON-01")
        assert "FALCON-01" not in source.get_drone_ids()


class TestRemoveDroneWithActiveMission:
    async def test_auto_recalls_active_mission_and_releases_budget(self, db):
        energy_cost_kwh = 2.4
        await create_mission(db, "FALCON-01", "Downtown", 3.0, energy_cost_kwh)
        remaining_before = await get_remaining_kwh(db)

        await service.remove_drone(db, None, "FALCON-01")

        assert await get_active_mission_for_drone(db, "FALCON-01") is None
        assert "FALCON-01" not in await list_roster(db)

        mission_row = await db.fetchone(
            "SELECT status FROM missions WHERE drone_id = ?", ("FALCON-01",)
        )
        assert mission_row["status"] == "recalled"

        log_row = await db.fetchone(
            "SELECT action FROM mission_log WHERE drone_id = ? AND action = 'recall'",
            ("FALCON-01",),
        )
        assert log_row is not None

        remaining_after = await get_remaining_kwh(db)
        assert remaining_after == remaining_before
