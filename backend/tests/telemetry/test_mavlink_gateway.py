"""Tests for MavlinkGatewayTelemetrySource."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telemetry.cache import TelemetryCache
from app.telemetry.mavlink_gateway import MavlinkGatewayTelemetrySource


def make_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def cache():
    return TelemetryCache()


class TestMavlinkGatewayTelemetrySource:
    async def test_start_polls_immediately(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache, poll_interval=100.0)
        source._client = AsyncMock()
        source._client.get = AsyncMock(
            return_value=make_response(
                [
                    {
                        "drone_id": "FALCON-01",
                        "battery_pct": 87.5,
                        "altitude_m": 118.0,
                        "speed_kmh": 41.2,
                        "status": "in_flight",
                        "timestamp": 1000.0,
                    }
                ]
            )
        )
        # Manually poll since start() would create a fresh httpx.AsyncClient.
        source._drone_ids = ["FALCON-01"]
        await source._poll_once()

        reading = cache.get("FALCON-01")
        assert reading is not None
        assert reading.battery_pct == 87.5
        assert reading.status == "in_flight"

        await source.stop()

    async def test_poll_skips_malformed_entries(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache, poll_interval=100.0)
        source._client = AsyncMock()
        source._client.get = AsyncMock(
            return_value=make_response(
                [
                    {"drone_id": "FALCON-01"},  # missing required fields
                    {
                        "drone_id": "FALCON-02",
                        "battery_pct": 60.0,
                        "altitude_m": 90.0,
                        "speed_kmh": 35.0,
                        "status": "in_flight",
                    },
                ]
            )
        )
        source._drone_ids = ["FALCON-01", "FALCON-02"]
        await source._poll_once()

        assert cache.get("FALCON-01") is None
        assert cache.get("FALCON-02") is not None

        await source.stop()

    async def test_poll_handles_request_failure_gracefully(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache, poll_interval=100.0)
        source._client = AsyncMock()
        source._client.get = AsyncMock(side_effect=ConnectionError("gateway unreachable"))
        source._drone_ids = ["FALCON-01"]

        await source._poll_once()  # should not raise

        assert cache.get("FALCON-01") is None
        await source.stop()

    async def test_poll_once_noop_without_drones(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache, poll_interval=100.0)
        source._client = AsyncMock()
        await source._poll_once()
        source._client.get.assert_not_called()

    async def test_add_drone(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache)
        await source.add_drone("falcon-02")
        assert source.get_drone_ids() == ["FALCON-02"]

    async def test_add_duplicate_drone_is_noop(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache)
        await source.add_drone("FALCON-01")
        await source.add_drone("FALCON-01")
        assert source.get_drone_ids() == ["FALCON-01"]

    async def test_remove_drone(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache)
        await source.add_drone("FALCON-01")
        cache.update(drone_id="FALCON-01", battery_pct=80.0, altitude_m=100.0, speed_kmh=40.0, status="in_flight")

        await source.remove_drone("FALCON-01")

        assert source.get_drone_ids() == []
        assert cache.get("FALCON-01") is None

    async def test_gateway_url_strips_trailing_slash(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local/", cache)
        assert source._gateway_url == "http://gateway.local"

    async def test_stop_without_start_is_safe(self, cache):
        source = MavlinkGatewayTelemetrySource("http://gateway.local", cache)
        await source.stop()  # should not raise
