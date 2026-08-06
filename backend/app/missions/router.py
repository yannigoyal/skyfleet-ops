"""FastAPI router for mission dispatch, recall, and fleet energy status."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.db import Database
from app.telemetry import TelemetryCache

from . import repository, service
from .models import DEFAULT_CRUISE_SPEED_KMH, InsufficientBudgetError, Mission, MissionError
from .queue import MissionQueue

_ERROR_STATUS = {
    "unknown_drone": 404,
    "drone_already_en_route": 409,
    "drone_unavailable": 409,
    "no_active_mission": 404,
    "insufficient_budget": 422,
    "no_eligible_drone": 422,
}


class LaunchMissionRequest(BaseModel):
    drone_id: str | None = None
    zone: str
    distance_km: float = Field(gt=0)


def _error_response(exc: MissionError) -> HTTPException:
    status_code = _ERROR_STATUS.get(exc.reason, 400)
    detail: dict = {"reason": exc.reason}
    if isinstance(exc, InsufficientBudgetError):
        detail["requested_kwh"] = exc.requested_kwh
        detail["remaining_kwh"] = exc.remaining_kwh
    return HTTPException(status_code=status_code, detail=detail)


def _mission_response(mission: Mission, cache: TelemetryCache) -> dict:
    payload = mission.to_dict()
    if mission.status == "en_route":
        reading = cache.get(mission.drone_id)
        speed = reading.speed_kmh if reading and reading.speed_kmh > 0 else DEFAULT_CRUISE_SPEED_KMH
        payload["eta_minutes"] = round((mission.distance_km / speed) * 60, 1)
    return payload


def create_missions_router(db: Database, cache: TelemetryCache, queue: MissionQueue) -> APIRouter:
    """Create the mission-dispatch router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/fleet", tags=["missions"])

    @router.get("")
    async def get_fleet_status():
        remaining_kwh = await repository.get_remaining_kwh(db)
        budget = await repository.get_energy_budget(db)
        active = await repository.list_active_missions(db)
        return {
            "energy_budget_kwh": budget,
            "remaining_kwh": remaining_kwh,
            "active_mission_count": len(active),
            "missions": [_mission_response(mission, cache) for mission in active],
        }

    @router.get("/history")
    async def get_fleet_history():
        return {"snapshots": await repository.list_budget_snapshots(db)}

    @router.get("/missions/queue")
    async def get_mission_queue():
        return {
            "pending": [entry.to_dict() for entry in queue.pending()],
            "failed": [entry.to_dict() for entry in queue.failed()],
        }

    @router.post("/missions", status_code=201)
    async def launch(request: LaunchMissionRequest, response: Response):
        if request.drone_id is not None:
            try:
                mission = await service.launch_mission(
                    db,
                    cache,
                    drone_id=request.drone_id,
                    zone=request.zone,
                    distance_km=request.distance_km,
                )
            except MissionError as exc:
                raise _error_response(exc) from exc
            return _mission_response(mission, cache)

        try:
            mission = await service.auto_assign_mission(
                db, cache, zone=request.zone, distance_km=request.distance_km
            )
        except MissionError as exc:
            entry = queue.enqueue(request.zone, request.distance_km)
            response.status_code = 202
            return {"reason": "queued", "queued_mission_id": entry.id, "cause": exc.reason}
        return _mission_response(mission, cache)

    @router.delete("/missions/{drone_id}")
    async def recall(drone_id: str):
        try:
            mission = await service.recall_mission(db, drone_id)
        except MissionError as exc:
            raise _error_response(exc) from exc
        return _mission_response(mission, cache)

    return router
