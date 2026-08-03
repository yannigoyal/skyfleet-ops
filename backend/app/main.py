"""SkyFleet Ops FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.telemetry import TelemetryCache, create_stream_router, create_telemetry_source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]

telemetry_cache = TelemetryCache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = create_telemetry_source(telemetry_cache)
    await source.start(DEFAULT_FLEET)
    app.state.telemetry_source = source
    logger.info("SkyFleet Ops backend started")
    yield
    await source.stop()
    logger.info("SkyFleet Ops backend stopped")


app = FastAPI(title="SkyFleet Ops", lifespan=lifespan)
app.include_router(create_stream_router(telemetry_cache))


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the Next.js static export, if present (production Docker build).
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
