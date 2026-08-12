"""FastAPI router for fleet roster CRUD."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.db import Database
from app.telemetry import TelemetryCache, TelemetrySource

from . import repository, service
from .models import RosterEntry, RosterError

_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_tracked": 409,
}

_TELEMETRY_FIELDS = ("battery_pct", "altitude_m", "speed_kmh", "status")


class AddDroneRequest(BaseModel):
    drone_id: str = Field(min_length=1)


def _error_response(exc: RosterError) -> HTTPException:
    status_code = _ERROR_STATUS.get(exc.reason, 400)
    return HTTPException(status_code=status_code, detail={"reason": exc.reason})


def _entry_response(entry: RosterEntry, cache: TelemetryCache) -> dict:
    payload = entry.to_dict()
    reading = cache.get(entry.drone_id)
    if reading:
        telemetry = reading.to_dict()
        payload.update({field: telemetry[field] for field in _TELEMETRY_FIELDS})
    return payload


def create_roster_router(
    db: Database, cache: TelemetryCache, source: TelemetrySource | None = None
) -> APIRouter:
    """Create the roster router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/roster", tags=["roster"])

    @router.get("")
    async def list_drones():
        entries = await repository.list_roster_entries(db)
        return {"drones": [_entry_response(entry, cache) for entry in entries]}

    @router.post("", status_code=201)
    async def add_drone(request: AddDroneRequest):
        try:
            entry = await service.add_drone(db, source, request.drone_id)
        except RosterError as exc:
            raise _error_response(exc) from exc
        return _entry_response(entry, cache)

    @router.delete("/{drone_id}", status_code=204)
    async def remove_drone(drone_id: str):
        try:
            await service.remove_drone(db, source, drone_id)
        except RosterError as exc:
            raise _error_response(exc) from exc
        return Response(status_code=204)

    return router
