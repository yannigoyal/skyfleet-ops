"""Tests for mission persistence and the energy-budget ledger."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.missions import repository
from app.missions.models import DroneAlreadyEnRouteError, InsufficientBudgetError, NoActiveMissionError


class TestRosterQueries:
    async def test_is_drone_on_roster_true(self, db):
        assert await repository.is_drone_on_roster(db, "FALCON-01") is True

    async def test_is_drone_on_roster_false(self, db):
        assert await repository.is_drone_on_roster(db, "GHOST-01") is False

    async def test_list_roster_drone_ids(self, db):
        ids = await repository.list_roster_drone_ids(db)
        assert ids[0] == "FALCON-01"
        assert len(ids) == 10


class TestBudget:
    async def test_get_energy_budget_default(self, db):
        assert await repository.get_energy_budget(db) == 500.0

    async def test_remaining_equals_budget_when_no_missions(self, db):
        assert await repository.get_remaining_kwh(db) == 500.0


class TestCreateMission:
    async def test_creates_en_route_mission(self, db):
        mission = await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        assert mission.status == "en_route"
        assert mission.drone_id == "FALCON-01"
        assert mission.energy_cost_kwh == 3.36

    async def test_deducts_remaining_budget(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        assert await repository.get_remaining_kwh(db) == 500.0 - 3.36

    async def test_rejects_second_active_mission_for_same_drone(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        with pytest.raises(DroneAlreadyEnRouteError):
            await repository.create_mission(db, "FALCON-01", "Downtown", 2.0, 1.6)

    async def test_rejects_insufficient_budget(self, db):
        with pytest.raises(InsufficientBudgetError) as exc_info:
            await repository.create_mission(db, "FALCON-01", "Riverside", 1000.0, 800.0)
        assert exc_info.value.remaining_kwh == 500.0
        assert exc_info.value.requested_kwh == 800.0

    async def test_failed_launch_does_not_write_any_rows(self, db):
        with pytest.raises(InsufficientBudgetError):
            await repository.create_mission(db, "FALCON-01", "Riverside", 1000.0, 800.0)
        assert await repository.list_active_missions(db) == []
        assert await repository.list_budget_snapshots(db) == []

    async def test_writes_mission_log_entry(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        row = await db.fetchone(
            "SELECT * FROM mission_log WHERE drone_id = ? AND action = 'launch'", ("FALCON-01",)
        )
        assert row is not None

    async def test_writes_budget_snapshot(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        snapshots = await repository.list_budget_snapshots(db)
        assert len(snapshots) == 1
        assert snapshots[0]["remaining_kwh"] == 500.0 - 3.36

    async def test_different_drones_can_launch_independently(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        mission2 = await repository.create_mission(db, "FALCON-02", "Downtown", 2.0, 1.6)
        assert mission2.status == "en_route"
        assert await repository.get_remaining_kwh(db) == 500.0 - 3.36 - 1.6


class TestRecall:
    async def test_recalls_active_mission(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        recalled = await repository.recall(db, "FALCON-01")
        assert recalled.status == "recalled"

    async def test_energy_already_spent_is_not_refunded(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        remaining_before = await repository.get_remaining_kwh(db)
        await repository.recall(db, "FALCON-01")
        remaining_after = await repository.get_remaining_kwh(db)
        assert remaining_after == remaining_before

    async def test_raises_when_no_active_mission(self, db):
        with pytest.raises(NoActiveMissionError):
            await repository.recall(db, "FALCON-01")

    async def test_drone_can_relaunch_after_recall(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        await repository.recall(db, "FALCON-01")
        mission = await repository.create_mission(db, "FALCON-01", "Downtown", 2.0, 1.6)
        assert mission.status == "en_route"

    async def test_writes_budget_snapshot_on_recall(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        await repository.recall(db, "FALCON-01")
        snapshots = await repository.list_budget_snapshots(db)
        assert len(snapshots) == 2

    async def test_writes_recall_mission_log_entry(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        await repository.recall(db, "FALCON-01")
        row = await db.fetchone(
            "SELECT * FROM mission_log WHERE drone_id = ? AND action = 'recall'", ("FALCON-01",)
        )
        assert row is not None


class TestDeliveryScheduling:
    async def test_overdue_when_eta_elapsed(self, db):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        await db.execute(
            "INSERT INTO missions "
            "(id, operator_id, drone_id, zone, distance_km, energy_cost_kwh, status, updated_at) "
            "VALUES (?, 'default', ?, ?, ?, ?, 'en_route', ?)",
            (str(uuid.uuid4()), "FALCON-01", "Riverside", 4.2, 3.36, past),
        )
        overdue = await repository.get_overdue_en_route_missions(db, cruise_speed_kmh=40.0)
        assert len(overdue) == 1
        assert overdue[0].drone_id == "FALCON-01"

    async def test_not_overdue_when_recently_launched(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        overdue = await repository.get_overdue_en_route_missions(db, cruise_speed_kmh=40.0)
        assert overdue == []

    async def test_mark_delivered(self, db):
        mission = await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        await repository.mark_delivered(db, mission.id)
        row = await db.fetchone("SELECT status FROM missions WHERE id = ?", (mission.id,))
        assert row["status"] == "delivered"

    async def test_delivered_mission_no_longer_active(self, db):
        mission = await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        await repository.mark_delivered(db, mission.id)
        assert await repository.list_active_missions(db) == []


class TestActiveMissionQueries:
    async def test_list_active_missions(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        active = await repository.list_active_missions(db)
        assert len(active) == 1

    async def test_list_active_drone_ids(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        ids = await repository.list_active_drone_ids(db)
        assert ids == {"FALCON-01"}

    async def test_get_active_mission_for_drone_none(self, db):
        assert await repository.get_active_mission_for_drone(db, "FALCON-01") is None

    async def test_get_active_mission_for_drone_found(self, db):
        await repository.create_mission(db, "FALCON-01", "Riverside", 4.2, 3.36)
        mission = await repository.get_active_mission_for_drone(db, "FALCON-01")
        assert mission is not None
        assert mission.drone_id == "FALCON-01"
