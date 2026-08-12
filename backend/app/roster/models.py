"""Data models and validation errors for the fleet roster."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RosterEntry:
    """A tracked drone — mirrors a row in the `fleet_roster` table."""

    id: str
    operator_id: str
    drone_id: str
    added_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"drone_id": self.drone_id, "added_at": self.added_at}


class RosterError(Exception):
    """Base class for roster validation failures raised by the repository."""

    reason: str = "roster_error"


class DroneAlreadyTrackedError(RosterError):
    reason = "drone_already_tracked"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone already on roster: {drone_id}")


class UnknownDroneError(RosterError):
    reason = "unknown_drone"

    def __init__(self, drone_id: str) -> None:
        self.drone_id = drone_id
        super().__init__(f"drone not on roster: {drone_id}")
