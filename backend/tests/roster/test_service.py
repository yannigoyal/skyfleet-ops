"""Tests for roster service-layer telemetry registration and failure handling."""

from __future__ import annotations

import logging

import pytest

from app.roster import service
from app.roster.models import DroneAlreadyTrackedError
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
