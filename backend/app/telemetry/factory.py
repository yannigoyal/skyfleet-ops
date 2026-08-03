"""Factory for creating fleet telemetry sources."""

from __future__ import annotations

import logging
import os

from .cache import TelemetryCache
from .interface import TelemetrySource
from .mavlink_gateway import MavlinkGatewayTelemetrySource
from .simulator import SimulatorTelemetrySource

logger = logging.getLogger(__name__)


def create_telemetry_source(telemetry_cache: TelemetryCache) -> TelemetrySource:
    """Create the appropriate telemetry source based on environment variables.

    - MAVLINK_GATEWAY_URL set and non-empty → MavlinkGatewayTelemetrySource (real hardware)
    - Otherwise → SimulatorTelemetrySource (mean-reverting simulation)

    Returns an unstarted source. Caller must await source.start(drone_ids).
    """
    gateway_url = os.environ.get("MAVLINK_GATEWAY_URL", "").strip()

    if gateway_url:
        logger.info("Telemetry source: MAVLink gateway at %s", gateway_url)
        return MavlinkGatewayTelemetrySource(gateway_url=gateway_url, telemetry_cache=telemetry_cache)
    else:
        logger.info("Telemetry source: fleet simulator")
        return SimulatorTelemetrySource(telemetry_cache=telemetry_cache)
