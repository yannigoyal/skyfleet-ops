"""FastAPI router for the AI flight-director chat endpoint.

The LLM's proposed mission actions are executed through the same validated
`missions.service.launch_mission` function the manual dispatch bar uses.
Only actions that actually succeeded are echoed back in `missions` —
failures are collected into `errors` so the operator (and the model, on the
next turn) sees what went wrong. This is the tracer slice: launch only, no
recall path, no roster path (both land in plan 03).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints

from app.db import Database
from app.missions import service as missions_service
from app.missions.models import MissionError
from app.telemetry import TelemetryCache, TelemetrySource

from . import repository
from .context import build_fleet_context
from .llm import LLMError, MissionAction, generate_reply

HISTORY_LIMIT = 20


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


async def _execute_mission(
    db: Database, cache: TelemetryCache, action: MissionAction
) -> tuple[dict | None, str | None]:
    if action.action != "launch":
        return None, f"Could not {action.action} {action.drone_id}: not wired in this slice."

    if not action.zone or action.distance_km is None or action.distance_km <= 0:
        return None, f"Could not launch {action.drone_id}: missing zone or distance."

    try:
        await missions_service.launch_mission(
            db,
            cache,
            drone_id=action.drone_id,
            zone=action.zone,
            distance_km=action.distance_km,
        )
    except MissionError as exc:
        return None, f"Could not launch {action.drone_id} to {action.zone}: {exc.reason}."
    return {
        "drone_id": action.drone_id,
        "action": "launch",
        "zone": action.zone,
        "distance_km": action.distance_km,
    }, None


def create_chat_router(
    db: Database, cache: TelemetryCache, source: TelemetrySource | None = None
) -> APIRouter:
    """Create the flight-director chat router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api", tags=["chat"])

    @router.post("/chat")
    async def chat(request: ChatRequest):
        fleet_context = await build_fleet_context(db, cache)
        history = await repository.get_recent_messages(db, limit=HISTORY_LIMIT)

        try:
            reply = await generate_reply(fleet_context, history, request.message)
        except LLMError as exc:
            raise HTTPException(
                status_code=502, detail={"reason": exc.reason, "detail": str(exc)}
            ) from exc

        executed_missions: list[dict] = []
        mission_errors: list[str] = []
        for action in reply.missions:
            executed, failure = await _execute_mission(db, cache, action)
            if executed is not None:
                executed_missions.append(executed)
            if failure is not None:
                mission_errors.append(failure)

        # Roster-change execution is deferred to plan 03; nothing is proposed
        # gets acted on yet, so the response always reports an empty list.
        executed_roster: list[dict] = []

        await repository.append_message(db, "user", request.message, actions=None)
        await repository.append_message(
            db,
            "assistant",
            reply.message,
            actions={"missions": executed_missions, "roster_changes": executed_roster},
        )

        return {
            "message": reply.message,
            "missions": executed_missions,
            "roster_changes": executed_roster,
            "errors": mission_errors,
        }

    return router
