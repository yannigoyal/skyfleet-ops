"""Shared fixtures for fleet roster tests."""

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
