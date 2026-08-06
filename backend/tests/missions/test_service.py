"""Tests for mission launch/recall validation and drone auto-assignment."""

from __future__ import annotations

import pytest

from app.missions import service
from app.missions.models import (
    DroneUnavailableError,
    InsufficientBudgetError,
    NoEligibleDroneError,
    UnknownDroneError,
)

from .conftest import seed_telemetry


class TestLaunchMission:
    async def test_launches_when_valid(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=90.0, status="idle")
        mission = await service.launch_mission(
            db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2
        )
        assert mission.status == "en_route"
        assert mission.drone_id == "FALCON-01"

    async def test_rejects_unknown_drone(self, db, cache):
        with pytest.raises(UnknownDroneError):
            await service.launch_mission(
                db, cache, drone_id="GHOST-01", zone="Riverside", distance_km=4.2
            )

    async def test_rejects_offline_drone(self, db, cache):
        seed_telemetry(cache, "FALCON-01", status="offline")
        with pytest.raises(DroneUnavailableError):
            await service.launch_mission(
                db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2
            )

    async def test_rejects_low_battery_drone(self, db, cache):
        seed_telemetry(cache, "FALCON-01", status="low_battery")
        with pytest.raises(DroneUnavailableError):
            await service.launch_mission(
                db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2
            )

    async def test_allows_launch_with_no_telemetry_yet(self, db, cache):
        # A drone with no telemetry reading yet (just added) isn't blocked
        # purely on missing data - only a known-unsafe status blocks it.
        mission = await service.launch_mission(
            db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2
        )
        assert mission.status == "en_route"

    async def test_rejects_insufficient_budget(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        with pytest.raises(InsufficientBudgetError):
            await service.launch_mission(
                db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=1000.0
            )


class TestRecallMission:
    async def test_recalls_active_mission(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        await service.launch_mission(db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2)
        mission = await service.recall_mission(db, "FALCON-01")
        assert mission.status == "recalled"


class TestFindEligibleDrone:
    async def test_prefers_highest_battery(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=40.0)
        seed_telemetry(cache, "FALCON-02", battery_pct=95.0)
        drone_id = await service.find_eligible_drone(db, cache)
        assert drone_id == "FALCON-02"

    async def test_skips_active_drones(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=95.0)
        seed_telemetry(cache, "FALCON-02", battery_pct=50.0)
        await service.launch_mission(db, cache, drone_id="FALCON-01", zone="Riverside", distance_km=4.2)
        drone_id = await service.find_eligible_drone(db, cache)
        assert drone_id == "FALCON-02"

    async def test_skips_unsafe_status(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=95.0, status="offline")
        seed_telemetry(cache, "FALCON-02", battery_pct=50.0, status="idle")
        drone_id = await service.find_eligible_drone(db, cache)
        assert drone_id == "FALCON-02"

    async def test_returns_none_without_any_telemetry(self, db, cache):
        assert await service.find_eligible_drone(db, cache) is None

    async def test_prefers_requested_drone_when_eligible(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=40.0)
        seed_telemetry(cache, "FALCON-02", battery_pct=95.0)
        drone_id = await service.find_eligible_drone(db, cache, preferred_drone_id="FALCON-01")
        assert drone_id == "FALCON-01"

    async def test_falls_back_when_preferred_ineligible(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=40.0, status="offline")
        seed_telemetry(cache, "FALCON-02", battery_pct=95.0)
        drone_id = await service.find_eligible_drone(db, cache, preferred_drone_id="FALCON-01")
        assert drone_id == "FALCON-02"


class TestAutoAssignMission:
    async def test_dispatches_to_best_drone(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=40.0)
        seed_telemetry(cache, "FALCON-02", battery_pct=95.0)
        mission = await service.auto_assign_mission(db, cache, zone="Riverside", distance_km=4.2)
        assert mission.drone_id == "FALCON-02"
        assert mission.status == "en_route"

    async def test_raises_when_no_drone_eligible(self, db, cache):
        with pytest.raises(NoEligibleDroneError):
            await service.auto_assign_mission(db, cache, zone="Riverside", distance_km=4.2)

    async def test_raises_when_budget_insufficient(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=90.0)
        with pytest.raises(InsufficientBudgetError):
            await service.auto_assign_mission(db, cache, zone="Riverside", distance_km=1000.0)
