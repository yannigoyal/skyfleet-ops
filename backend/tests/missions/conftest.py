"""Shared fixtures for mission scheduling tests."""

from __future__ import annotations

import pytest

from app.db import Database
from app.telemetry import TelemetryCache


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
