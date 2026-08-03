"""Data models for fleet telemetry."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

# Statuses a drone can report. "low_battery" and "offline" are derived by the
# telemetry source when battery crosses a safety threshold.
STATUSES = ("idle", "in_flight", "charging", "low_battery", "offline")


@dataclass(frozen=True, slots=True)
class TelemetryUpdate:
    """Immutable snapshot of a single drone's telemetry at a point in time."""

    drone_id: str
    battery_pct: float
    previous_battery_pct: float
    altitude_m: float
    speed_kmh: float
    status: str
    timestamp: float = field(default_factory=time.time)  # Unix seconds

    @property
    def battery_delta(self) -> float:
        """Change in battery percentage since the previous reading."""
        return round(self.battery_pct - self.previous_battery_pct, 4)

    @property
    def battery_direction(self) -> str:
        """'draining', 'charging', or 'flat'."""
        if self.battery_pct > self.previous_battery_pct:
            return "charging"
        elif self.battery_pct < self.previous_battery_pct:
            return "draining"
        return "flat"

    def to_dict(self) -> dict:
        """Serialize for JSON / SSE transmission."""
        return {
            "drone_id": self.drone_id,
            "battery_pct": self.battery_pct,
            "previous_battery_pct": self.previous_battery_pct,
            "altitude_m": self.altitude_m,
            "speed_kmh": self.speed_kmh,
            "status": self.status,
            "timestamp": self.timestamp,
            "battery_delta": self.battery_delta,
            "battery_direction": self.battery_direction,
        }
