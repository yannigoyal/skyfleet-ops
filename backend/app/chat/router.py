"""FastAPI router for the AI flight-director chat endpoint.

The LLM's proposed mission and roster actions are executed through the exact
service-layer functions the manual dispatch bar and roster panel use —
`missions.service` for launch/recall, `roster.service` for add/remove. This
file must never import either domain's persistence module directly: the
auto-recall-before-remove guard that keeps a roster removal from orphaning
an en_route mission lives in `roster.service.remove_drone`, not in
persistence, so reaching persistence from here would silently skip it (see
02-03-PLAN.md task 2's import-boundary test). Only actions that actually
succeeded are echoed back in `missions` / `roster_changes` — failures are
collected into `errors` so the operator (and the model, on the next turn)
sees what went wrong.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints

from app.db import Database
from app.missions import service as missions_service
from app.missions.models import MissionError
from app.roster import service as roster_service
from app.roster.models import RosterError
from app.telemetry import TelemetryCache, TelemetrySource

from . import llm, repository
from .context import build_fleet_context
from .llm import LLMError, MissionAction, RosterChange, generate_reply

HISTORY_LIMIT = 20
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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
            await roster_service.add_drone(db, source, change.drone_id)
        else:
            await roster_service.remove_drone(db, source, change.drone_id)
    except RosterError as exc:
        return None, f"Could not {change.action} {change.drone_id}: {exc.reason}."
    return {"drone_id": change.drone_id, "action": change.action}, None


def _extract_reason(error_message: str) -> str:
    """Pull the trailing service `reason` key off a formatted error string
    (see _execute_mission/_execute_roster_change above), e.g.
    "...: unknown_drone." -> "unknown_drone"."""
    return error_message.rsplit(": ", 1)[-1].rstrip(".")


def create_chat_router(
    db: Database, cache: TelemetryCache, source: TelemetrySource | None = None
) -> APIRouter:
    """Create the flight-director chat router with its dependencies bound (no globals)."""
    router = APIRouter(prefix="/api", tags=["chat"])

    @router.post("/chat")
    async def chat(request: ChatRequest):
        fleet_context = await build_fleet_context(db, cache)
        history = await repository.get_recent_messages(db, limit=HISTORY_LIMIT)

        start_time = time.monotonic()
        try:
            reply = await generate_reply(fleet_context, history, request.message)
        except LLMError as exc:
            raise HTTPException(
                status_code=502, detail={"reason": exc.reason, "detail": str(exc)}
            ) from exc
        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Both loops execute strictly sequentially — one await per action
        # against live state, never a pre-validated batch — so a later
        # action correctly fails once an earlier one has consumed the
        # budget or changed drone eligibility.
        executed_missions: list[dict] = []
        mission_errors: list[str] = []
        for action in reply.missions:
            executed, failure = await _execute_mission(db, cache, action)
            if executed is not None:
                executed_missions.append(executed)
            if failure is not None:
                mission_errors.append(failure)

        executed_roster: list[dict] = []
        roster_errors: list[str] = []
        for change in reply.roster_changes:
            executed, failure = await _execute_roster_change(db, source, change)
            if executed is not None:
                executed_roster.append(executed)
            if failure is not None:
                roster_errors.append(failure)

        await repository.append_message(db, "user", request.message, actions=None)
        await repository.append_message(
            db,
            "assistant",
            reply.message,
            actions={"missions": executed_missions, "roster_changes": executed_roster},
        )

        # Token counts require the provider's usage object; plan 02 left
        # generate_reply returning only the parsed reply, so both are
        # recorded as None here rather than widening that signature in this
        # plan. Never include the api key, request headers, the message
        # text, or provider call arguments in this or any other log line.
        reason_keys = [_extract_reason(error) for error in mission_errors + roster_errors]
        logger.info(
            "chat turn: elapsed_ms=%.1f prompt_tokens=%s completion_tokens=%s "
            "executed=%d failed=%d reasons=%s mock_mode=%s",
            elapsed_ms,
            None,
            None,
            len(executed_missions) + len(executed_roster),
            len(mission_errors) + len(roster_errors),
            reason_keys,
            llm.mock_mode_enabled(),
        )

        return {
            "message": reply.message,
            "missions": executed_missions,
            "roster_changes": executed_roster,
            "errors": mission_errors + roster_errors,
        }

    return router
