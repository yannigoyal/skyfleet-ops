"""Gated live smoke tests for the real OpenRouter/Cerebras flight-director call.

Deselected by default (`pyproject.toml`'s `addopts = "-m 'not live'"`) and
skipped outright when `OPENROUTER_API_KEY` is absent, even if explicitly
selected. This is the one-time executed evidence that the extra_body-nested
schema (CHAT-08) actually reaches the provider, rather than being asserted
from documentation alone. Run manually during phase verification:

    cd backend && uv run --extra dev pytest -m live tests/chat/test_live_smoke.py -v -s
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.chat.context import build_fleet_context
from app.chat.llm import FlightDirectorReply, generate_reply

from .conftest import seed_telemetry

DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]


def _load_dotenv_if_needed() -> None:
    """Populate OPENROUTER_API_KEY from the project root .env, with a small

    local KEY=VALUE parser rather than a dotenv dependency. No-op if the key
    is already set (including explicitly set empty, to keep the "no key"
    acceptance check honest) or the file is absent. Never prints the value.
    """
    if os.environ.get("OPENROUTER_API_KEY"):
        return
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_if_needed()

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("OPENROUTER_API_KEY"),
        reason="live CHAT-08 smoke test requires a real OPENROUTER_API_KEY",
    ),
]


async def _fleet_context(db, cache) -> dict:
    for drone_id in DEFAULT_FLEET:
        seed_telemetry(cache, drone_id)
    return await build_fleet_context(db, cache)


async def test_live_explicit_launch_instruction(db, cache):
    """L1 - explicit launch instruction. Also checks the proposed action."""
    context = await _fleet_context(db, cache)

    start = time.monotonic()
    reply = await generate_reply(context, [], "Launch FALCON-03 to Riverside, 4.2 km.")
    elapsed_ms = (time.monotonic() - start) * 1000

    print(f"\n[L1] elapsed_ms={elapsed_ms:.0f}")
    print(reply.model_dump_json())

    assert isinstance(reply, FlightDirectorReply)
    assert reply.message
    launches = [m for m in reply.missions if m.action == "launch"]
    assert any(m.drone_id == "FALCON-03" for m in launches)


async def test_live_open_ended_analysis(db, cache):
    """L2 - open-ended fleet-analysis question."""
    context = await _fleet_context(db, cache)

    start = time.monotonic()
    reply = await generate_reply(context, [], "How is fleet battery health looking right now?")
    elapsed_ms = (time.monotonic() - start) * 1000

    print(f"\n[L2] elapsed_ms={elapsed_ms:.0f}")
    print(reply.model_dump_json())

    assert isinstance(reply, FlightDirectorReply)
    assert reply.message


async def test_live_ambiguous_request(db, cache):
    """L3 - ambiguous/underspecified request; the highest-signal prompt for

    catching a regression back to prompt-only JSON compliance.
    """
    context = await _fleet_context(db, cache)

    start = time.monotonic()
    reply = await generate_reply(context, [], "Send something to Riverside.")
    elapsed_ms = (time.monotonic() - start) * 1000

    print(f"\n[L3] elapsed_ms={elapsed_ms:.0f}")
    print(reply.model_dump_json())

    assert isinstance(reply, FlightDirectorReply)
    assert reply.message
