"""Shared fixtures for chat history, LLM, and chat API tests."""

from __future__ import annotations

from types import SimpleNamespace

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


@pytest.fixture
def stub_completion(monkeypatch):
    """Replace litellm.acompletion so no test ever reaches the network.

    Returns a factory: call it with the string the model should "return"
    (or an Exception to raise). It hands back a list that records the kwargs
    of each call.
    """
    import litellm

    calls: list[dict] = []

    def _install(result):
        async def _fake_acompletion(**kwargs):
            calls.append(kwargs)
            if isinstance(result, Exception):
                raise result
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=result))]
            )

        monkeypatch.setattr(litellm, "acompletion", _fake_acompletion)
        return calls

    return _install


def seed_telemetry(
    cache: TelemetryCache, drone_id: str, battery_pct: float = 90.0, status: str = "idle"
) -> None:
    cache.update(drone_id, battery_pct=battery_pct, altitude_m=100.0, speed_kmh=40.0, status=status)
