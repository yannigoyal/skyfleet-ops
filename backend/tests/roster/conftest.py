"""Shared fixtures for fleet roster tests."""

from __future__ import annotations

import pytest

from app.db import Database
from app.telemetry import TelemetryCache, TelemetrySource


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "skyfleet.db")
    database.ensure_initialized()
    yield database
    database.close()


@pytest.fixture
def cache():
    return TelemetryCache()


def seed_telemetry(
    cache: TelemetryCache, drone_id: str, battery_pct: float = 90.0, status: str = "idle"
) -> None:
    cache.update(drone_id, battery_pct=battery_pct, altitude_m=100.0, speed_kmh=40.0, status=status)


class FakeSource(TelemetrySource):
    """In-memory TelemetrySource test double, shared across roster tests."""

    def __init__(self) -> None:
        self.drone_ids: list[str] = []

    async def start(self, drone_ids: list[str]) -> None:
        self.drone_ids = list(drone_ids)

    async def stop(self) -> None:
        pass

    async def add_drone(self, drone_id: str) -> None:
        self.drone_ids.append(drone_id)

    async def remove_drone(self, drone_id: str) -> None:
        self.drone_ids.remove(drone_id)

    def get_drone_ids(self) -> list[str]:
        return list(self.drone_ids)


class RaisingSource(FakeSource):
    """A TelemetrySource whose mutations always fail, for D-04 coverage."""

    async def add_drone(self, drone_id: str) -> None:
        raise RuntimeError("gateway offline")

    async def remove_drone(self, drone_id: str) -> None:
        raise RuntimeError("gateway offline")
