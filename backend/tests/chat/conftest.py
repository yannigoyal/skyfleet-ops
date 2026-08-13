"""Shared fixtures for chat history, LLM, and chat API tests."""

from __future__ import annotations

from types import SimpleNamespace

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
    """In-memory TelemetrySource test double, shared across chat tests."""

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


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")


@pytest.fixture
def real_mode(monkeypatch):
    monkeypatch.delenv("LLM_MOCK", raising=False)


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
