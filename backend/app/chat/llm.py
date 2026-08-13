"""LLM flight director: prompt construction, structured output, mock mode.

Calls LiteLLM -> OpenRouter with `openrouter/openai/gpt-oss-120b`, requesting
Cerebras as the inference provider. The model must answer with JSON matching
RESPONSE_SCHEMA; the reply is parsed into a FlightDirectorReply and the
proposed actions are executed (and validated) by the router.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .models import ChatMessage, LLMError

MODEL = "openrouter/openai/gpt-oss-120b"
PROVIDER_ROUTING = {"only": ["Cerebras"]}
TEMPERATURE = 0.2
MAX_TOKENS = 800

SYSTEM_PROMPT = """You are the SkyFleet flight director, an AI fleet operations assistant for a \
last-mile drone delivery fleet.

Your job:
- Analyze fleet battery health, mission load, and remaining energy budget.
- Suggest mission launches and recalls with brief, data-driven reasoning.
- Execute missions when the operator asks or agrees.
- Manage the fleet roster proactively (add or remove drones).
- Be concise. Cite concrete numbers from the fleet context.

Rules:
- Only dispatch drones that appear in the roster and are not already en route.
- A launch costs 0.8 kWh per km; never propose launches the remaining budget cannot cover.
- launch actions require both `zone` and `distance_km`; recall actions require only `drone_id`.
- Leave `missions` and `roster_changes` empty unless the operator wants action taken now.
- Your `message` must name every drone id and every action it takes, so a dispatcher reading
  only the transcript knows what executed.
- Always respond with valid JSON matching the required schema."""

RESPONSE_SCHEMA = {
    "name": "flight_director_reply",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "missions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drone_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["launch", "recall"]},
                        "zone": {"type": ["string", "null"]},
                        "distance_km": {"type": ["number", "null"]},
                    },
                    "required": ["drone_id", "action", "zone", "distance_km"],
                    "additionalProperties": False,
                },
            },
            "roster_changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "drone_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["add", "remove"]},
                    },
                    "required": ["drone_id", "action"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["message", "missions", "roster_changes"],
        "additionalProperties": False,
    },
}


class MissionAction(BaseModel):
    drone_id: str
    action: Literal["launch", "recall"]
    zone: str | None = None
    distance_km: float | None = None


class RosterChange(BaseModel):
    drone_id: str
    action: Literal["add", "remove"]


class FlightDirectorReply(BaseModel):
    message: str
    missions: list[MissionAction] = Field(default_factory=list)
    roster_changes: list[RosterChange] = Field(default_factory=list)


def mock_mode_enabled() -> bool:
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def parse_reply(raw: str) -> FlightDirectorReply:
    """Parse the model's JSON content. Raises LLMError if it is not usable."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LLMError(f"model returned non-JSON content: {raw!r}") from exc
    if not isinstance(payload, dict):
        raise LLMError(f"model returned a non-object payload: {raw!r}")
    payload.setdefault("missions", [])
    payload.setdefault("roster_changes", [])
    if payload["missions"] is None:
        payload["missions"] = []
    if payload["roster_changes"] is None:
        payload["roster_changes"] = []
    try:
        return FlightDirectorReply.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"model reply failed schema validation: {exc}") from exc


def build_messages(fleet_context: dict, history: list[ChatMessage], user_message: str) -> list[dict]:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current fleet context:\n{json.dumps(fleet_context)}"},
    ]
    messages.extend({"role": item.role, "content": item.content} for item in history)
    messages.append({"role": "user", "content": user_message})
    return messages


def mock_reply(fleet_context: dict, user_message: str) -> FlightDirectorReply:
    """Deterministic stand-in for the model, used when LLM_MOCK=true.

    Recognizes two keywords so E2E tests can exercise auto-execution:
    "recall" recalls the first active mission, "launch" launches the first
    idle roster drone to zone "Riverside" over 4.0 km. Anything else returns
    a plain status summary with no actions.
    """
    text = user_message.lower()
    remaining = fleet_context.get("remaining_kwh")
    roster = fleet_context.get("roster", [])
    active = fleet_context.get("active_missions", [])
    summary = (
        f"[mock] {len(roster)} drones on roster, {len(active)} en route, "
        f"{remaining} kWh remaining."
    )

    if "recall" in text and active:
        drone_id = active[0]["drone_id"]
        return FlightDirectorReply(
            message=f"{summary} Recalling {drone_id}.",
            missions=[MissionAction(drone_id=drone_id, action="recall")],
        )

    if "launch" in text:
        busy = {mission["drone_id"] for mission in active}
        idle = [drone["drone_id"] for drone in roster if drone["drone_id"] not in busy]
        if idle:
            return FlightDirectorReply(
                message=f"{summary} Launching {idle[0]} to Riverside.",
                missions=[
                    MissionAction(
                        drone_id=idle[0], action="launch", zone="Riverside", distance_km=4.0
                    )
                ],
            )

    return FlightDirectorReply(message=summary)


async def generate_reply(
    fleet_context: dict, history: list[ChatMessage], user_message: str
) -> FlightDirectorReply:
    """Ask the flight director for a structured reply (or the mock, if enabled).

    The real provider call is not wired yet — that lands in plan 02, replacing
    the single `raise` below with a `litellm.acompletion` call. The seam and
    its signature do not change.
    """
    if mock_mode_enabled():
        return mock_reply(fleet_context, user_message)

    raise LLMError("live LLM calls are not wired yet - set LLM_MOCK=true")
