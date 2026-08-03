"""SSE streaming endpoint for live fleet telemetry."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import TelemetryCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])


def create_stream_router(telemetry_cache: TelemetryCache) -> APIRouter:
    """Create the SSE streaming router with a reference to the telemetry cache.

    This factory pattern lets us inject the TelemetryCache without globals.
    """

    @router.get("/telemetry")
    async def stream_telemetry(request: Request) -> StreamingResponse:
        """SSE endpoint for live fleet telemetry.

        Streams all tracked drone readings every ~500ms. The client connects
        with EventSource and receives events in the format:

            data: {"FALCON-01": {"drone_id": "FALCON-01", "battery_pct": 87.5, ...}, ...}

        Includes a retry directive so the browser auto-reconnects on
        disconnection (EventSource built-in behavior).
        """
        return StreamingResponse(
            _generate_events(telemetry_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if proxied
            },
        )

    return router


async def _generate_events(
    telemetry_cache: TelemetryCache,
    request: Request,
    interval: float = 0.5,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted telemetry events.

    Sends all readings every `interval` seconds. Stops when the client
    disconnects (detected via request.is_disconnected()).
    """
    # Tell the client to retry after 1 second if the connection drops
    yield "retry: 1000\n\n"

    last_version = -1
    client_ip = request.client.host if request.client else "unknown"
    logger.info("SSE client connected: %s", client_ip)

    try:
        while True:
            if await request.is_disconnected():
                logger.info("SSE client disconnected: %s", client_ip)
                break

            current_version = telemetry_cache.version
            if current_version != last_version:
                last_version = current_version
                readings = telemetry_cache.get_all()

                if readings:
                    data = {drone_id: update.to_dict() for drone_id, update in readings.items()}
                    payload = json.dumps(data)
                    yield f"data: {payload}\n\n"

            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info("SSE stream cancelled for: %s", client_ip)
