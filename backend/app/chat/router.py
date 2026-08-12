"""FastAPI router for the AI flight-director chat endpoint.

The LLM's proposed actions are executed through the same validated service
functions the manual endpoints use. Only actions that actually succeeded are
returned in `missions`/`roster_changes` — failures are appended to `message`
so the operator (and the model, on the next turn) sees what went wrong.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import Database
from app.missions import service as missions_service
from app.missions.models import MissionError
from app.roster import repository as roster_repository
from app.roster.models import RosterError
from app.telemetry import TelemetryCache, TelemetrySource

from . import repository
from .context import build_fleet_context
from .llm import FlightDirectorReply, LLMError, MissionAction, RosterChange, generate_reply

HISTORY_LIMIT = 20


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


async def _execute_mission(
    db: Database, cache: TelemetryCache, action: MissionAction
) -> tuple[dict | None, str | None]:
    if action.action == "recall":
        try:
            await missions_service.recall_mission(db, action.drone_id)
        except MissionError as exc:
            return None, f"Could not recall {action.drone_id}: {exc.reason}."
        return {"drone_id": action.drone_id, "action": "recall"}, None

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


async def _execute_roster_change(
    db: Database, source: TelemetrySource | None, change: RosterChange
) -> tuple[dict | None, str | None]:
    try:
        if change.action == "add":
            await roster_repository.add_drone(db, change.drone_id)
            if source is not None:
                await source.add_drone(change.drone_id)
        else:
            await roster_repository.remove_drone(db, change.drone_id)
            if source is not None:
                await source.remove_drone(change.drone_id)
    except RosterError as exc:
        return None, f"Could not {change.action} {change.drone_id}: {exc.reason}."
    return {"drone_id": change.drone_id, "action": change.action}, None


async def execute_actions(
    db: Database, cache: TelemetryCache, source: TelemetrySource | None, reply: FlightDirectorReply
) -> tuple[list[dict], list[dict], list[str]]:
    """Run every proposed action, returning (executed missions, executed roster changes, failures)."""
    missions: list[dict] = []
    roster_changes: list[dict] = []
    failures: list[str] = []

    for action in reply.missions:
        executed, failure = await _execute_mission(db, cache, action)
        if executed is not None:
            missions.append(executed)
        if failure is not None:
            failures.append(failure)

    for change in reply.roster_changes:
        executed, failure = await _execute_roster_change(db, source, change)
        if executed is not None:
            roster_changes.append(executed)
        if failure is not None:
            failures.append(failure)

    return missions, roster_changes, failures


def create_chat_router(
    db: Database, cache: TelemetryCache, source: TelemetrySource | None = None
) -> APIRouter:
    """Create the flight-director chat router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api/chat", tags=["chat"])

    @router.post("")
    async def chat(request: ChatRequest):
        user_message = request.message.strip()
        fleet_context = await build_fleet_context(db, cache)
        history = await repository.get_recent_messages(db, limit=HISTORY_LIMIT)

        try:
            reply = await generate_reply(fleet_context, history, user_message)
        except LLMError as exc:
            raise HTTPException(
                status_code=502, detail={"reason": "llm_unavailable", "error": str(exc)}
            ) from exc

        missions, roster_changes, failures = await execute_actions(db, cache, source, reply)

        message = reply.message
        if failures:
            message = f"{message}\n\n" + "\n".join(failures)

        await repository.append_message(db, "user", user_message)
        actions_json = (
            json.dumps({"missions": missions, "roster_changes": roster_changes})
            if missions or roster_changes
            else None
        )
        await repository.append_message(db, "assistant", message, actions_json=actions_json)

        response: dict = {"message": message}
        if missions:
            response["missions"] = missions
        if roster_changes:
            response["roster_changes"] = roster_changes
        return response

    return router
