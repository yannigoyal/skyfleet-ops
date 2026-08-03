"""Thread-safe in-memory telemetry cache."""

from __future__ import annotations

import time
from threading import Lock

from .models import TelemetryUpdate


class TelemetryCache:
    """Thread-safe in-memory cache of the latest telemetry for each drone.

    Writers: SimulatorTelemetrySource or MavlinkGatewayTelemetrySource (one at a time).
    Readers: SSE streaming endpoint, fleet health scoring, mission validation.
    """

    def __init__(self) -> None:
        self._readings: dict[str, TelemetryUpdate] = {}
        self._lock = Lock()
        self._version: int = 0  # Monotonically increasing; bumped on every update

    def update(
        self,
        drone_id: str,
        battery_pct: float,
        altitude_m: float,
        speed_kmh: float,
        status: str,
        timestamp: float | None = None,
    ) -> TelemetryUpdate:
        """Record a new reading for a drone. Returns the created TelemetryUpdate.

        Automatically computes battery delta/direction from the previous reading.
        If this is the first reading for the drone, previous_battery_pct == battery_pct
        (direction='flat').
        """
        with self._lock:
            ts = timestamp or time.time()
            prev = self._readings.get(drone_id)
            previous_battery_pct = prev.battery_pct if prev else battery_pct

            update = TelemetryUpdate(
                drone_id=drone_id,
                battery_pct=round(battery_pct, 2),
                previous_battery_pct=round(previous_battery_pct, 2),
                altitude_m=round(altitude_m, 1),
                speed_kmh=round(speed_kmh, 1),
                status=status,
                timestamp=ts,
            )
            self._readings[drone_id] = update
            self._version += 1
            return update

    def get(self, drone_id: str) -> TelemetryUpdate | None:
        """Get the latest reading for a single drone, or None if unknown."""
        with self._lock:
            return self._readings.get(drone_id)

    def get_all(self) -> dict[str, TelemetryUpdate]:
        """Snapshot of all current readings. Returns a shallow copy."""
        with self._lock:
            return dict(self._readings)

    def get_battery(self, drone_id: str) -> float | None:
        """Convenience: get just the battery percentage, or None."""
        update = self.get(drone_id)
        return update.battery_pct if update else None

    def remove(self, drone_id: str) -> None:
        """Remove a drone from the cache (e.g., when removed from the roster)."""
        with self._lock:
            self._readings.pop(drone_id, None)

    @property
    def version(self) -> int:
        """Current version counter. Useful for SSE change detection."""
        return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._readings)

    def __contains__(self, drone_id: str) -> bool:
        with self._lock:
            return drone_id in self._readings
