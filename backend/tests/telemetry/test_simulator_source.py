"""Integration tests for SimulatorTelemetrySource."""

import asyncio

import pytest

from app.telemetry.cache import TelemetryCache
from app.telemetry.simulator import SimulatorTelemetrySource


@pytest.fixture
def cache():
    return TelemetryCache()


class TestSimulatorTelemetrySource:
    async def test_start_seeds_cache_immediately(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=10.0)
        await source.start(["FALCON-01", "FALCON-02"])
        try:
            assert cache.get("FALCON-01") is not None
            assert cache.get("FALCON-02") is not None
        finally:
            await source.stop()

    async def test_background_loop_updates_cache(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=0.05)
        await source.start(["FALCON-01"])
        try:
            initial_version = cache.version
            await asyncio.sleep(0.2)
            assert cache.version > initial_version
        finally:
            await source.stop()

    async def test_stop_halts_updates(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=0.05)
        await source.start(["FALCON-01"])
        await source.stop()
        version_after_stop = cache.version
        await asyncio.sleep(0.2)
        assert cache.version == version_after_stop

    async def test_stop_is_idempotent(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=1.0)
        await source.start(["FALCON-01"])
        await source.stop()
        await source.stop()  # should not raise

    async def test_add_drone(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=10.0)
        await source.start(["FALCON-01"])
        try:
            await source.add_drone("FALCON-02")
            assert "FALCON-02" in source.get_drone_ids()
            assert cache.get("FALCON-02") is not None
        finally:
            await source.stop()

    async def test_remove_drone(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=10.0)
        await source.start(["FALCON-01", "FALCON-02"])
        try:
            await source.remove_drone("FALCON-01")
            assert "FALCON-01" not in source.get_drone_ids()
            assert cache.get("FALCON-01") is None
        finally:
            await source.stop()

    async def test_get_drone_ids_before_start(self, cache):
        source = SimulatorTelemetrySource(cache)
        assert source.get_drone_ids() == []

    async def test_start_with_empty_fleet(self, cache):
        source = SimulatorTelemetrySource(cache, update_interval=0.05)
        await source.start([])
        try:
            await asyncio.sleep(0.1)
            assert len(cache) == 0
        finally:
            await source.stop()
