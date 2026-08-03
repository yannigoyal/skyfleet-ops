"""REST client for a MAVLink telemetry gateway bridge."""

from __future__ import annotations

import asyncio
import logging

import httpx

from .cache import TelemetryCache
from .interface import TelemetrySource

logger = logging.getLogger(__name__)


class MavlinkGatewayTelemetrySource(TelemetrySource):
    """TelemetrySource backed by a REST MAVLink gateway bridge.

    Polls GET {gateway_url}/telemetry?drones=... for all watched drones in a
    single HTTP call, then writes results to the TelemetryCache. Talking to a
    REST bridge rather than a raw MAVLink socket keeps the backend simple and
    lets the gateway live behind any network boundary (VPN, cellular modem, etc).

    Expected bridge response shape:
        [
          {"drone_id": "FALCON-01", "battery_pct": 87.5, "altitude_m": 118.0,
           "speed_kmh": 41.2, "status": "in_flight", "timestamp": 1730000000.0},
          ...
        ]
    """

    def __init__(
        self,
        gateway_url: str,
        telemetry_cache: TelemetryCache,
        poll_interval: float = 2.0,
    ) -> None:
        self._gateway_url = gateway_url.rstrip("/")
        self._cache = telemetry_cache
        self._interval = poll_interval
        self._drone_ids: list[str] = []
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self, drone_ids: list[str]) -> None:
        self._client = httpx.AsyncClient(timeout=5.0)
        self._drone_ids = list(drone_ids)

        # Do an immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="mavlink-gateway-poller")
        logger.info(
            "MAVLink gateway poller started: %d drones, %.1fs interval",
            len(drone_ids),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        if self._client:
            await self._client.aclose()
        self._client = None
        logger.info("MAVLink gateway poller stopped")

    async def add_drone(self, drone_id: str) -> None:
        drone_id = drone_id.upper().strip()
        if drone_id not in self._drone_ids:
            self._drone_ids.append(drone_id)
            logger.info("MAVLink gateway: added drone %s (will appear on next poll)", drone_id)

    async def remove_drone(self, drone_id: str) -> None:
        drone_id = drone_id.upper().strip()
        self._drone_ids = [d for d in self._drone_ids if d != drone_id]
        self._cache.remove(drone_id)
        logger.info("MAVLink gateway: removed drone %s", drone_id)

    def get_drone_ids(self) -> list[str]:
        return list(self._drone_ids)

    # --- Internal ---

    async def _poll_loop(self) -> None:
        """Poll on interval. First poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Execute one poll cycle: fetch readings, update cache."""
        if not self._drone_ids or not self._client:
            return

        try:
            readings = await self._fetch_readings()
            processed = 0
            for reading in readings:
                try:
                    self._cache.update(
                        drone_id=reading["drone_id"],
                        battery_pct=reading["battery_pct"],
                        altitude_m=reading["altitude_m"],
                        speed_kmh=reading["speed_kmh"],
                        status=reading["status"],
                        timestamp=reading.get("timestamp"),
                    )
                    processed += 1
                except (KeyError, TypeError) as e:
                    logger.warning("Skipping malformed gateway reading: %s", e)
            logger.debug("Gateway poll: updated %d/%d drones", processed, len(self._drone_ids))

        except Exception as e:
            logger.error("MAVLink gateway poll failed: %s", e)
            # Don't re-raise — the loop will retry on the next interval.
            # Common failures: gateway unreachable, malformed JSON, timeout.

    async def _fetch_readings(self) -> list[dict]:
        """Call the gateway bridge and return the parsed JSON list."""
        response = await self._client.get(
            f"{self._gateway_url}/telemetry",
            params={"drones": ",".join(self._drone_ids)},
        )
        response.raise_for_status()
        return response.json()
