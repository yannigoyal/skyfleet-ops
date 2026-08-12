"""Tests for roster service-layer telemetry registration and failure handling."""

from __future__ import annotations

import logging

import pytest

from app.missions.models import DroneUnavailableError
from app.missions.repository import (
    create_mission,
    get_active_mission_for_drone,
    get_remaining_kwh,
    mark_delivered,
)
from app.missions.service import recall_mission
from app.roster import service
from app.roster.models import DroneAlreadyTrackedError, UnknownDroneError
from app.roster.repository import list_roster

from .conftest import FakeSource, RaisingSource


def _racing_check(resolve):
    """Wrap service.get_active_mission_for_drone so that, when it finds an
    en_route mission, `resolve(mission)` runs inside the check->recall window
    before the now-stale mission is handed back to the caller — reproducing
    a concurrent writer (the delivery scheduler or a manual recall) winning
    the race against remove_drone's own recall step."""
    real_check = service.get_active_mission_for_drone

    async def wrapper(db_arg, drone_id, *args, **kwargs):
        mission = await real_check(db_arg, drone_id, *args, **kwargs)
        if mission is not None:
            await resolve(mission)
        return mission

    return wrapper


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


class TestRemoveIdempotency:
    async def test_second_removal_raises_and_leaves_state_unchanged(self, db):
        await service.remove_drone(db, None, "FALCON-01")
        log_count_before = len(await db.fetchall("SELECT id FROM mission_log"))

        with pytest.raises(UnknownDroneError) as exc_info:
            await service.remove_drone(db, None, "FALCON-01")

        assert exc_info.value.reason == "unknown_drone"
        assert len(await list_roster(db)) == 9
        log_count_after = len(await db.fetchall("SELECT id FROM mission_log"))
        assert log_count_after == log_count_before

    async def test_recall_before_remove_crash_window_completes_cleanly(self, db):
        """Simulates the accepted crash window: recall happens, then a retried
        DELETE re-issues remove_drone — the recall step is a no-op the second
        time, and the roster row still comes off cleanly (ROST-02 concurrency)."""
        await create_mission(db, "FALCON-02", "Riverside", 2.0, 1.6)
        await recall_mission(db, "FALCON-02")

        await service.remove_drone(db, None, "FALCON-02")

        assert "FALCON-02" not in await list_roster(db)


class TestRemoveTelemetrySyncFailure:
    async def test_row_survives_a_raising_source_and_logs_the_drone_id(self, db, caplog):
        source = RaisingSource()
        source.drone_ids = ["FALCON-01"]

        with caplog.at_level(logging.ERROR):
            await service.remove_drone(db, source, "FALCON-01")

        assert "FALCON-01" not in await list_roster(db)
        assert "FALCON-01" in caplog.text


class TestRemoveDroneMidWindowRace:
    async def test_scheduler_delivery_variant_preserves_terminal_status_and_no_recall_log(
        self, db, monkeypatch
    ):
        await create_mission(db, "FALCON-01", "Riverside", 4.0, 3.2)
        monkeypatch.setattr(
            service, "get_active_mission_for_drone", _racing_check(lambda m: mark_delivered(db, m.id))
        )

        await service.remove_drone(db, None, "FALCON-01")

        assert "FALCON-01" not in await list_roster(db)
        mission_row = await db.fetchone(
            "SELECT status FROM missions WHERE drone_id = ?", ("FALCON-01",)
        )
        assert mission_row["status"] == "delivered"
        recall_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM mission_log WHERE drone_id = ? AND action = 'recall'",
            ("FALCON-01",),
        )
        assert recall_row["c"] == 0

    async def test_concurrent_manual_recall_variant_preserves_single_recall_log_and_budget(
        self, db, monkeypatch
    ):
        await create_mission(db, "FALCON-02", "Riverside", 2.0, 1.6)
        captured: dict[str, float] = {}

        async def resolve(mission):
            await recall_mission(db, mission.drone_id)
            captured["remaining_after_resolution"] = await get_remaining_kwh(db)

        monkeypatch.setattr(service, "get_active_mission_for_drone", _racing_check(resolve))

        await service.remove_drone(db, None, "FALCON-02")

        assert "FALCON-02" not in await list_roster(db)
        mission_row = await db.fetchone(
            "SELECT status FROM missions WHERE drone_id = ?", ("FALCON-02",)
        )
        assert mission_row["status"] == "recalled"
        recall_row = await db.fetchone(
            "SELECT COUNT(*) AS c FROM mission_log WHERE drone_id = ? AND action = 'recall'",
            ("FALCON-02",),
        )
        assert recall_row["c"] == 1

        remaining_after_removal = await get_remaining_kwh(db)
        assert remaining_after_removal == captured["remaining_after_resolution"]

    async def test_idempotent_after_race_second_removal_raises_unknown_drone(self, db, monkeypatch):
        await create_mission(db, "FALCON-01", "Riverside", 4.0, 3.2)
        monkeypatch.setattr(
            service, "get_active_mission_for_drone", _racing_check(lambda m: mark_delivered(db, m.id))
        )

        await service.remove_drone(db, None, "FALCON-01")
        roster_count_before = len(await list_roster(db))
        log_count_before = len(await db.fetchall("SELECT id FROM mission_log"))

        with pytest.raises(UnknownDroneError) as exc_info:
            await service.remove_drone(db, None, "FALCON-01")

        assert exc_info.value.reason == "unknown_drone"
        assert len(await list_roster(db)) == roster_count_before
        log_count_after = len(await db.fetchall("SELECT id FROM mission_log"))
        assert log_count_after == log_count_before


class TestRemoveDroneCatchNarrowness:
    async def test_different_mission_error_propagates_and_leaves_roster_row(self, db, monkeypatch):
        await create_mission(db, "FALCON-01", "Riverside", 4.0, 3.2)

        async def raising_recall(db_arg, drone_id):
            raise DroneUnavailableError(drone_id)

        monkeypatch.setattr(service, "recall_mission", raising_recall)

        with pytest.raises(DroneUnavailableError):
            await service.remove_drone(db, None, "FALCON-01")

        assert "FALCON-01" in await list_roster(db)

    async def test_skipped_recall_logs_drone_id(self, db, caplog, monkeypatch):
        await create_mission(db, "FALCON-01", "Riverside", 4.0, 3.2)
        monkeypatch.setattr(
            service, "get_active_mission_for_drone", _racing_check(lambda m: mark_delivered(db, m.id))
        )

        with caplog.at_level(logging.INFO):
            await service.remove_drone(db, None, "FALCON-01")

        assert "FALCON-01" in caplog.text
