"""Tests for telemetry source factory."""

import os
from unittest.mock import patch

from app.telemetry.cache import TelemetryCache
from app.telemetry.factory import create_telemetry_source
from app.telemetry.mavlink_gateway import MavlinkGatewayTelemetrySource
from app.telemetry.simulator import SimulatorTelemetrySource


class TestFactory:
    """Tests for create_telemetry_source factory."""

    def test_creates_simulator_when_no_gateway_url(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, SimulatorTelemetrySource)

    def test_creates_simulator_when_url_empty(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {"MAVLINK_GATEWAY_URL": ""}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, SimulatorTelemetrySource)

    def test_creates_simulator_when_url_whitespace(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {"MAVLINK_GATEWAY_URL": "   "}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, SimulatorTelemetrySource)

    def test_creates_gateway_when_url_set(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {"MAVLINK_GATEWAY_URL": "http://gateway.local"}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, MavlinkGatewayTelemetrySource)

    def test_gateway_receives_url(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {"MAVLINK_GATEWAY_URL": "http://gateway.local"}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, MavlinkGatewayTelemetrySource)
        assert source._gateway_url == "http://gateway.local"

    def test_simulator_receives_cache(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, SimulatorTelemetrySource)
        assert source._cache is cache

    def test_gateway_receives_cache(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {"MAVLINK_GATEWAY_URL": "http://gateway.local"}, clear=True):
            source = create_telemetry_source(cache)
        assert isinstance(source, MavlinkGatewayTelemetrySource)
        assert source._cache is cache

    def test_gateway_url_trailing_slash_stripped(self):
        cache = TelemetryCache()
        with patch.dict(os.environ, {"MAVLINK_GATEWAY_URL": "http://gateway.local/"}, clear=True):
            source = create_telemetry_source(cache)
        assert source._gateway_url == "http://gateway.local"
