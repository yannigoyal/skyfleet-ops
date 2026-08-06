"""Data models, constants, and validation errors for mission scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MISSION_STATUSES = ("en_route", "delivered", "recalled")
UNSAFE_TELEMETRY_STATUSES = frozenset({"offline", "low_battery"})

ENERGY_COST_PER_KM_KWH = 0.8
DEFAULT_CRUISE_SPEED_KMH = 40.0


@dataclass(frozen=True, slots=True)
class Mission:
    """A delivery mission — mirrors a row in the `missions` table."""

    id: str
    operator_id: str
    drone_id: str
    zone: str
    distance_km: float
    energy_cost_kwh: float
    status: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "drone_id": self.drone_id,
            "zone": self.zone,
            "distance_km": self.distance_km,
            "energy_cost_kwh": self.energy_cost_kwh,
            "status": self.status,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def energy_cost_for(distance_km: float) -> float:
        return round(distance_km * ENERGY_COST_PER_KM_KWH, 4)


class MissionError(Exception):
    """Base class for mission validation failures raised by the service layer."""

    reason: str = "mission_error"


class UnknownDroneError(MissionError):
    reason = "unknown_drone"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone not on roster: {drone_id}")


class DroneAlreadyEnRouteError(MissionError):
    reason = "drone_already_en_route"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone already en route: {drone_id}")


class DroneUnavailableError(MissionError):
    reason = "drone_unavailable"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone unavailable for dispatch: {drone_id}")


class NoActiveMissionError(MissionError):
    reason = "no_active_mission"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"no active mission for drone: {drone_id}")


class NoEligibleDroneError(MissionError):
    reason = "no_eligible_drone"

    def __init__(self, zone: str) -> None:
        self.zone = zone
        super().__init__(f"no eligible drone available for zone: {zone}")


class InsufficientBudgetError(MissionError):
    reason = "insufficient_budget"

    def __init__(self, requested_kwh: float, remaining_kwh: float) -> None:
        self.requested_kwh = requested_kwh
        self.remaining_kwh = remaining_kwh
        super().__init__(
            f"insufficient budget: requested {requested_kwh} kWh, remaining {remaining_kwh} kWh"
        )
