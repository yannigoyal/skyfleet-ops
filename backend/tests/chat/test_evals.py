"""Reference-dataset replay harness: the phase's offline CI gate.

Fourteen canned LLM completions (see `fixtures/README.md` for the schema) replay through the real
`/api/chat` endpoint entirely offline: `LLM_MOCK=true` plus `stub_completion` install the fixture's
raw completion string in place of `litellm.acompletion`, and `app.chat.llm.mock_mode_enabled` is
monkeypatched to return `False` for the duration so the canned string flows through the real
`parse_reply` and the real service-layer execution path instead of the keyword-based `mock_reply`.
No network call happens anywhere in this module.

Each fixture pins what executed, what was refused (with a named drone, action, and reason key), and
what the database looks like afterwards -- the row-count and budget deltas -- so a regression in the
error-formatting, sequencing, or validation logic fails a specific, readable scenario rather than a
vague end-to-end assertion.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.chat import create_chat_router, llm
from app.missions import MissionQueue, create_missions_router
from app.missions import repository as missions_repository
from app.roster import create_roster_router
from app.telemetry import TelemetryCache

from .conftest import seed_telemetry

DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FIXTURES_DIR.glob("*.json"))
FIXTURE_IDS = [path.stem for path in FIXTURES]

# A malformed-completion error string must never leak an exception's internal
# representation -- these are the tells that it did.
TRACEBACK_MARKERS = ("Traceback (most recent call last)", 'File "', "raise ")


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text())


def _client(db, cache: TelemetryCache) -> TestClient:
    """Mount chat, missions, and roster routers on one app so fixture seeding
    and the chat request itself share the TestClient's event loop --
    Database's asyncio.Lock must not be first used from a different loop
    than the one serving the request (mirrors test_router.py::_client)."""
    app = FastAPI()
    app.include_router(create_chat_router(db, cache))
    app.include_router(create_missions_router(db, cache, MissionQueue()))
    app.include_router(create_roster_router(db, cache))
    return TestClient(app)


def _seed_fleet_telemetry(cache: TelemetryCache) -> None:
    for drone_id in DEFAULT_FLEET:
        seed_telemetry(cache, drone_id)


def _apply_seed(client: TestClient, seed: dict) -> None:
    for launch in seed.get("launch", []):
        response = client.post("/api/fleet/missions", json=launch)
        assert response.status_code == 201, response.text
    for drone_id in seed.get("roster_remove", []):
        response = client.delete(f"/api/roster/{drone_id}")
        assert response.status_code == 204, response.text


async def _row_counts(db) -> tuple[int, int]:
    missions = await db.fetchall("SELECT 1 FROM missions", ())
    chats = await db.fetchall("SELECT 1 FROM chat_messages", ())
    return len(missions), len(chats)


def _setup_scenario(db, cache, fixture: dict, stub_completion, monkeypatch) -> TestClient:
    """Force the real (non-mock) reply path and install the fixture's canned
    completion, seed the fleet and the fixture's `seed`, and return a client
    ready for the fixture's request."""
    monkeypatch.setattr(llm, "mock_mode_enabled", lambda: False)
    # generate_reply's real branch (the one that reaches stub_completion via
    # litellm.acompletion) short-circuits with LLMError before ever calling
    # acompletion if no API key is present -- a harmless placeholder here
    # since litellm.acompletion itself is monkeypatched and never inspects it.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-for-offline-replay")
    stub_completion(fixture["completion"])
    _seed_fleet_telemetry(cache)
    client = _client(db, cache)
    _apply_seed(client, fixture.get("seed", {}))
    return client


def test_fixtures_directory_is_populated():
    """Guards against a mis-globbed path making the whole gate pass vacuously."""
    assert len(FIXTURES) >= 11, FIXTURES


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=FIXTURE_IDS)
async def test_fixture_scenario(fixture_path, db, cache, mock_mode, stub_completion, monkeypatch):
    fixture = _load_fixture(fixture_path)
    client = _setup_scenario(db, cache, fixture, stub_completion, monkeypatch)

    pre_missions, pre_chats = await _row_counts(db)
    pre_remaining = await missions_repository.get_remaining_kwh(db)

    response = client.post("/api/chat", json={"message": fixture["user_message"]})

    expect = fixture["expect"]
    assert response.status_code == expect["status"]

    post_missions, post_chats = await _row_counts(db)
    post_remaining = await missions_repository.get_remaining_kwh(db)

    assert post_missions - pre_missions == expect["mission_row_delta"]
    assert post_chats - pre_chats == expect["chat_row_delta"]
    assert round(post_remaining - pre_remaining, 4) == expect["budget_delta_kwh"]

    if expect["status"] != 200:
        # An HTTPException body has a different shape ({"detail": {...}}) --
        # the malformed-completion fixtures assert only status and the three
        # deltas above (all zero: nothing executed, nothing persisted).
        return

    body = response.json()
    executed_missions = {(m["drone_id"], m["action"]) for m in body["missions"]}
    executed_roster = {(r["drone_id"], r["action"]) for r in body["roster_changes"]}
    expected_missions = {(m["drone_id"], m["action"]) for m in expect.get("missions", [])}
    expected_roster = {(r["drone_id"], r["action"]) for r in expect.get("roster_changes", [])}
    assert executed_missions == expected_missions
    assert executed_roster == expected_roster

    errors = body["errors"]
    error_contains = expect["error_contains"]
    assert len(errors) == len(error_contains)
    for error_text, required_substrings in zip(errors, error_contains):
        for substring in required_substrings:
            assert substring in error_text
        for marker in TRACEBACK_MARKERS:
            assert marker not in error_text

    for drone_id, status in expect.get("final_mission_status", {}).items():
        row = await db.fetchone(
            "SELECT status FROM missions WHERE drone_id = ? ORDER BY updated_at DESC LIMIT 1",
            (drone_id,),
        )
        assert row is not None, f"expected a missions row for {drone_id}"
        assert row["status"] == status

    if "final_active_mission_count" in expect:
        active_rows = await db.fetchall("SELECT 1 FROM missions WHERE status = 'en_route'", ())
        assert len(active_rows) == expect["final_active_mission_count"]


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=FIXTURE_IDS)
async def test_no_action_is_silently_dropped(fixture_path, db, cache, mock_mode, stub_completion, monkeypatch):
    """executed missions + executed roster changes + errors == actions proposed.

    Skips the two fixtures whose completions are deliberately malformed
    (non-JSON, or JSON that fails schema validation) -- those never reach
    action execution, so there is nothing to count on the response side, and
    the failure is proven instead by test_fixture_scenario's 502/zero-delta
    assertions above.
    """
    fixture = _load_fixture(fixture_path)
    if fixture["expect"]["status"] != 200:
        pytest.skip(f"{fixture_path.stem}: completion is deliberately malformed, no action count applies")
        return

    client = _setup_scenario(db, cache, fixture, stub_completion, monkeypatch)
    response = client.post("/api/chat", json={"message": fixture["user_message"]})
    assert response.status_code == 200

    proposed = json.loads(fixture["completion"])
    proposed_count = len(proposed.get("missions") or []) + len(proposed.get("roster_changes") or [])

    body = response.json()
    executed_count = len(body["missions"]) + len(body["roster_changes"])
    assert executed_count + len(body["errors"]) == proposed_count
