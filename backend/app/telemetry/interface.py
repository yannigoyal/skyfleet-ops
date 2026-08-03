"""Abstract interface for fleet telemetry sources."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TelemetrySource(ABC):
    """Contract for fleet telemetry providers.

    Implementations push telemetry updates into a shared TelemetryCache on
    their own schedule. Downstream code never calls the data source directly
    for readings — it reads from the cache.

    Lifecycle:
        source = create_telemetry_source(cache)
        await source.start(["FALCON-01", "FALCON-02", ...])
        # ... app runs ...
        await source.add_drone("FALCON-11")
        await source.remove_drone("FALCON-02")
        # ... app shutting down ...
        await source.stop()
    """

    @abstractmethod
    async def start(self, drone_ids: list[str]) -> None:
        """Begin producing telemetry for the given drones.

        Starts a background task that periodically writes to the
        TelemetryCache. Must be called exactly once. Calling start() twice
        is undefined behavior.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources.

        Safe to call multiple times. After stop(), the source will not write
        to the cache again.
        """

    @abstractmethod
    async def add_drone(self, drone_id: str) -> None:
        """Add a drone to the active fleet. No-op if already present.

        The next update cycle will include this drone.
        """

    @abstractmethod
    async def remove_drone(self, drone_id: str) -> None:
        """Remove a drone from the active fleet. No-op if not present.

        Also removes the drone from the TelemetryCache.
        """

    @abstractmethod
    def get_drone_ids(self) -> list[str]:
        """Return the current list of actively tracked drones."""
