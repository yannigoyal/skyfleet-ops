"""Tests for mission models and validation error types."""

from __future__ import annotations

from app.missions.models import (
    ENERGY_COST_PER_KM_KWH,
    DroneAlreadyEnRouteError,
    DroneUnavailableError,
    InsufficientBudgetError,
    Mission,
    NoActiveMissionError,
    NoEligibleDroneError,
    UnknownDroneError,
)


class TestMission:
    def test_energy_cost_for(self):
        assert Mission.energy_cost_for(5.0) == round(5.0 * ENERGY_COST_PER_KM_KWH, 4)

    def test_to_dict_shape(self):
        mission = Mission(
            id="m1",
            operator_id="default",
            drone_id="FALCON-01",
            zone="Riverside",
            distance_km=4.2,
            energy_cost_kwh=3.36,
            status="en_route",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        data = mission.to_dict()
        assert data["drone_id"] == "FALCON-01"
        assert data["zone"] == "Riverside"
        assert data["status"] == "en_route"
        assert "operator_id" not in data


class TestMissionErrors:
    def test_reason_codes(self):
        assert UnknownDroneError("F1").reason == "unknown_drone"
        assert DroneAlreadyEnRouteError("F1").reason == "drone_already_en_route"
        assert DroneUnavailableError("F1").reason == "drone_unavailable"
        assert NoActiveMissionError("F1").reason == "no_active_mission"
        assert NoEligibleDroneError("Zone").reason == "no_eligible_drone"
        assert InsufficientBudgetError(1.0, 0.5).reason == "insufficient_budget"

    def test_insufficient_budget_carries_amounts(self):
        exc = InsufficientBudgetError(10.0, 3.5)
        assert exc.requested_kwh == 10.0
        assert exc.remaining_kwh == 3.5
