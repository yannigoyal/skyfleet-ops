"""Mean-reverting fleet telemetry simulator."""

from __future__ import annotations

import asyncio
import logging
import random

import numpy as np

from .cache import TelemetryCache
from .interface import TelemetrySource
from .seed_fleet import (
    CROSS_GROUP_CORR,
    DEFAULT_PARAMS,
    INTRA_NORTH_CORR,
    INTRA_SOUTH_CORR,
    LOW_BATTERY_THRESHOLD,
    SEED_TELEMETRY,
    SOLO_CORR,
    SQUADRON_GROUPS,
    TICKER_PARAMS,
)

logger = logging.getLogger(__name__)

_GROUND_STATUSES = ("idle", "offline")
_DEFAULT_CRUISE_ALTITUDE_M = 100.0
_DEFAULT_CRUISE_SPEED_KMH = 40.0


class FleetSimulator:
    """Ornstein-Uhlenbeck-style battery drain simulator for a drone fleet.

    Unlike an unbounded random walk, battery percentage must stay in [0, 100].
    In-flight drones drain steadily toward zero (a fixed per-tick drain rate)
    with correlated turbulence noise layered on top; charging drones climb
    back toward 100 and then go idle; idle/offline drones sit nearly flat.

    Correlated turbulence: drones in the same squadron (flying the same
    weather cell) share a Cholesky-decomposed correlation matrix, the same
    technique used to correlate sector stock moves elsewhere in this course.
    """

    def __init__(
        self,
        drone_ids: list[str],
        event_probability: float = 0.001,
    ) -> None:
        self._event_prob = event_probability

        # Per-drone state
        self._drone_ids: list[str] = []
        self._battery: dict[str, float] = {}
        self._altitude: dict[str, float] = {}
        self._speed: dict[str, float] = {}
        self._status: dict[str, str] = {}
        self._base_altitude: dict[str, float] = {}
        self._base_speed: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}

        # Cholesky decomposition of the squadron correlation matrix
        self._cholesky: np.ndarray | None = None

        for drone_id in drone_ids:
            self._add_drone_internal(drone_id)
        self._rebuild_cholesky()

    # --- Public API ---

    def step(self) -> dict[str, dict[str, float | str]]:
        """Advance all drones by one time step. Returns {drone_id: reading}.

        This is the hot path — called every 500ms. Keep it fast.
        """
        n = len(self._drone_ids)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, dict[str, float | str]] = {}
        for i, drone_id in enumerate(self._drone_ids):
            status = self._status[drone_id]
            battery = self._battery[drone_id]
            params = self._params[drone_id]
            z = float(z_correlated[i])

            if status == "charging":
                battery = min(100.0, battery + 0.8 + abs(z) * 0.05)
                if battery >= 100.0:
                    status = "idle"
                altitude, speed = 0.0, 0.0
            elif status in _GROUND_STATUSES:
                battery = max(0.0, battery - 0.002)
                altitude, speed = 0.0, 0.0
            else:  # "in_flight" or "low_battery"
                battery -= params["drain_rate"] + params["volatility"] * z * 0.5

                if random.random() < self._event_prob:
                    gust = random.uniform(1.5, 4.0)
                    battery -= gust
                    logger.debug("Wind gust on %s: -%.1f%% battery", drone_id, gust)

                battery = round(max(0.0, min(100.0, battery)), 2)
                status = "low_battery" if battery <= LOW_BATTERY_THRESHOLD else "in_flight"
                if battery <= 0.0:
                    status = "offline"

                altitude = max(0.0, self._base_altitude[drone_id] + np.random.normal(0, 3))
                speed = max(0.0, self._base_speed[drone_id] + np.random.normal(0, 2))

            self._battery[drone_id] = round(battery, 2)
            self._status[drone_id] = status
            self._altitude[drone_id] = round(altitude, 1)
            self._speed[drone_id] = round(speed, 1)

            result[drone_id] = {
                "battery_pct": self._battery[drone_id],
                "altitude_m": self._altitude[drone_id],
                "speed_kmh": self._speed[drone_id],
                "status": status,
            }

        return result

    def add_drone(self, drone_id: str) -> None:
        """Add a drone to the simulation. Rebuilds the correlation matrix."""
        if drone_id in self._battery:
            return
        self._add_drone_internal(drone_id)
        self._rebuild_cholesky()

    def remove_drone(self, drone_id: str) -> None:
        """Remove a drone from the simulation. Rebuilds the correlation matrix."""
        if drone_id not in self._battery:
            return
        self._drone_ids.remove(drone_id)
        for store in (
            self._battery,
            self._altitude,
            self._speed,
            self._status,
            self._base_altitude,
            self._base_speed,
            self._params,
        ):
            del store[drone_id]
        self._rebuild_cholesky()

    def get_reading(self, drone_id: str) -> dict[str, float | str] | None:
        """Current reading for a drone, or None if not tracked."""
        if drone_id not in self._battery:
            return None
        return {
            "battery_pct": self._battery[drone_id],
            "altitude_m": self._altitude[drone_id],
            "speed_kmh": self._speed[drone_id],
            "status": self._status[drone_id],
        }

    def get_drone_ids(self) -> list[str]:
        """Return the list of currently tracked drones."""
        return list(self._drone_ids)

    # --- Internals ---

    def _add_drone_internal(self, drone_id: str) -> None:
        """Add a drone without rebuilding Cholesky (for batch initialization)."""
        if drone_id in self._battery:
            return
        seed = SEED_TELEMETRY.get(
            drone_id,
            {
                "battery_pct": 100.0,
                "altitude_m": 0.0,
                "speed_kmh": 0.0,
                "status": "idle",
            },
        )
        self._drone_ids.append(drone_id)
        self._battery[drone_id] = float(seed["battery_pct"])
        self._altitude[drone_id] = float(seed["altitude_m"])
        self._speed[drone_id] = float(seed["speed_kmh"])
        self._status[drone_id] = str(seed["status"])
        self._base_altitude[drone_id] = (
            float(seed["altitude_m"]) if seed["status"] == "in_flight" else _DEFAULT_CRUISE_ALTITUDE_M
        )
        self._base_speed[drone_id] = (
            float(seed["speed_kmh"]) if seed["status"] == "in_flight" else _DEFAULT_CRUISE_SPEED_KMH
        )
        self._params[drone_id] = TICKER_PARAMS.get(drone_id, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        """Rebuild the Cholesky decomposition of the drone correlation matrix.

        Called whenever drones are added or removed. O(n^2) but n stays small.
        """
        n = len(self._drone_ids)
        if n <= 1:
            self._cholesky = None
            return

        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._drone_ids[i], self._drone_ids[j])
                corr[i, j] = rho
                corr[j, i] = rho

        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(d1: str, d2: str) -> float:
        """Determine correlation between two drones based on squadron grouping.

        Correlation structure:
          - Same north squadron: 0.55
          - Same south squadron: 0.45
          - Cross-squadron:      0.2
          - Solo drones:         0.15
        """
        north = SQUADRON_GROUPS["north"]
        south = SQUADRON_GROUPS["south"]

        if d1 in north and d2 in north:
            return INTRA_NORTH_CORR
        if d1 in south and d2 in south:
            return INTRA_SOUTH_CORR
        if d1 in (north | south) and d2 in (north | south):
            return CROSS_GROUP_CORR
        if d1 in (north | south) or d2 in (north | south):
            return CROSS_GROUP_CORR
        return SOLO_CORR


class SimulatorTelemetrySource(TelemetrySource):
    """TelemetrySource backed by the FleetSimulator.

    Runs a background asyncio task that calls FleetSimulator.step() every
    `update_interval` seconds and writes results to the TelemetryCache.
    """

    def __init__(
        self,
        telemetry_cache: TelemetryCache,
        update_interval: float = 0.5,
        event_probability: float = 0.001,
    ) -> None:
        self._cache = telemetry_cache
        self._interval = update_interval
        self._event_prob = event_probability
        self._sim: FleetSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, drone_ids: list[str]) -> None:
        self._sim = FleetSimulator(
            drone_ids=drone_ids,
            event_probability=self._event_prob,
        )
        # Seed the cache with initial readings so SSE has data immediately
        for drone_id in drone_ids:
            reading = self._sim.get_reading(drone_id)
            if reading is not None:
                self._cache.update(drone_id=drone_id, **reading)
        self._task = asyncio.create_task(self._run_loop(), name="fleet-simulator-loop")
        logger.info("Fleet simulator started with %d drones", len(drone_ids))

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Fleet simulator stopped")

    async def add_drone(self, drone_id: str) -> None:
        if self._sim:
            self._sim.add_drone(drone_id)
            reading = self._sim.get_reading(drone_id)
            if reading is not None:
                self._cache.update(drone_id=drone_id, **reading)
            logger.info("Simulator: added drone %s", drone_id)

    async def remove_drone(self, drone_id: str) -> None:
        if self._sim:
            self._sim.remove_drone(drone_id)
        self._cache.remove(drone_id)
        logger.info("Simulator: removed drone %s", drone_id)

    def get_drone_ids(self) -> list[str]:
        return self._sim.get_drone_ids() if self._sim else []

    async def _run_loop(self) -> None:
        """Core loop: step the simulation, write to cache, sleep."""
        while True:
            try:
                if self._sim:
                    readings = self._sim.step()
                    for drone_id, reading in readings.items():
                        self._cache.update(drone_id=drone_id, **reading)
            except Exception:
                logger.exception("Fleet simulator step failed")
            await asyncio.sleep(self._interval)
