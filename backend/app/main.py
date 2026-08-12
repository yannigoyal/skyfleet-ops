"""SkyFleet Ops FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.chat import create_chat_router
from app.db import Database
from app.missions import (
    MissionQueue,
    create_missions_router,
    run_assignment_scheduler,
    run_budget_snapshot_loop,
    run_delivery_scheduler,
)
from app.roster import create_roster_router
from app.telemetry import TelemetryCache, create_stream_router, create_telemetry_source

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]


def _default_db_path() -> Path:
    """Resolve the SQLite file path.

    In the Docker image, backend/ is copied flat into /app (WORKDIR /app), so
    the volume-mounted "database" dir is a direct sibling of app/main.py's
    parent. In a local checkout, main.py sits inside backend/app/, two levels
    below the repo root's "database" dir. Prefer whichever actually exists;
    DATABASE_PATH overrides both when set.
    """
    override = os.environ.get("DATABASE_PATH", "").strip()
    if override:
        return Path(override)

    here = Path(__file__).resolve()
    for ancestor in (here.parents[1], here.parents[2]):
        db_dir = ancestor / "database"
        if db_dir.is_dir():
            return db_dir / "skyfleet.db"
    return here.parents[1] / "database" / "skyfleet.db"


telemetry_cache = TelemetryCache()
telemetry_source = create_telemetry_source(telemetry_cache)
mission_queue = MissionQueue()
database = Database(_default_db_path())


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.ensure_initialized()

    await telemetry_source.start(DEFAULT_FLEET)
    app.state.telemetry_source = telemetry_source

    background_tasks = [
        asyncio.create_task(run_assignment_scheduler(database, telemetry_cache, mission_queue)),
        asyncio.create_task(run_delivery_scheduler(database)),
        asyncio.create_task(run_budget_snapshot_loop(database)),
    ]

    logger.info("SkyFleet Ops backend started")
    yield

    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    await telemetry_source.stop()
    logger.info("SkyFleet Ops backend stopped")


app = FastAPI(title="SkyFleet Ops", lifespan=lifespan)
app.include_router(create_stream_router(telemetry_cache))
app.include_router(create_missions_router(database, telemetry_cache, mission_queue))
app.include_router(create_roster_router(database, telemetry_cache, telemetry_source))
app.include_router(create_chat_router(database, telemetry_cache, telemetry_source))


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the Next.js static export, if present (production Docker build).
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
