"""Tests for POST /api/chat: auto-execution, failure handling, persistence."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.chat import create_chat_router, repository
from app.chat.llm import FlightDirectorReply, LLMError, MissionAction, RosterChange
from app.missions import repository as missions_repository

from .conftest import seed_telemetry


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def _client(db, cache, source=None) -> TestClient:
    app = FastAPI()
    app.include_router(create_chat_router(db, cache, source))
    return TestClient(app)


def _stub_reply(monkeypatch, reply):
    async def _fake(fleet_context, history, user_message):
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr("app.chat.router.generate_reply", _fake)


class TestChatEndpoint:
    def test_plain_message_returns_message_only(self, db, cache):
        response = _client(db, cache).post("/api/chat", json={"message": "status report"})
        assert response.status_code == 200
        body = response.json()
        assert body["message"].startswith("[mock]")
        assert "missions" not in body
        assert "roster_changes" not in body

    def test_empty_message_rejected(self, db, cache):
        assert _client(db, cache).post("/api/chat", json={"message": ""}).status_code == 422

    def test_llm_failure_returns_502(self, db, cache, monkeypatch):
        _stub_reply(monkeypatch, LLMError("provider down"))
        response = _client(db, cache).post("/api/chat", json={"message": "hi"})
        assert response.status_code == 502
        assert response.json()["detail"]["reason"] == "llm_unavailable"

    def test_persists_user_and_assistant_turns(self, db, cache):
        _client(db, cache).post("/api/chat", json={"message": "  status  "})
        messages = _sync(repository.get_recent_messages(db))
        assert [message.role for message in messages] == ["user", "assistant"]
        assert messages[0].content == "status"
        assert messages[0].actions is None
        assert messages[1].actions is None


class TestMissionAutoExecution:
    def test_successful_launch_appears_in_response_and_db(self, db, cache, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Dispatching FALCON-01.",
                missions=[
                    MissionAction(
                        drone_id="FALCON-01", action="launch", zone="Riverside", distance_km=4.0
                    )
                ],
            ),
        )
        response = _client(db, cache).post("/api/chat", json={"message": "launch"})
        body = response.json()
        assert body["missions"] == [
            {
                "drone_id": "FALCON-01",
                "action": "launch",
                "zone": "Riverside",
                "distance_km": 4.0,
            }
        ]
        active = _sync(missions_repository.list_active_missions(db))
        assert [mission.drone_id for mission in active] == ["FALCON-01"]

    def test_successful_recall(self, db, cache, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        _sync(missions_repository.create_mission(db, "FALCON-01", "Riverside", 4.0, 3.2))
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Recalling.",
                missions=[MissionAction(drone_id="FALCON-01", action="recall")],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "recall"}).json()
        assert body["missions"] == [{"drone_id": "FALCON-01", "action": "recall"}]
        assert _sync(missions_repository.list_active_missions(db)) == []

    def test_unknown_drone_reported_in_message_not_arrays(self, db, cache, monkeypatch):
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Dispatching GHOST-99.",
                missions=[
                    MissionAction(
                        drone_id="GHOST-99", action="launch", zone="Riverside", distance_km=4.0
                    )
                ],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "launch"}).json()
        assert "missions" not in body
        assert "unknown_drone" in body["message"]

    def test_insufficient_budget_reported_in_message(self, db, cache, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Dispatching.",
                missions=[
                    MissionAction(
                        drone_id="FALCON-01", action="launch", zone="Far", distance_km=10000.0
                    )
                ],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "launch"}).json()
        assert "missions" not in body
        assert "insufficient_budget" in body["message"]

    def test_launch_without_zone_is_rejected(self, db, cache, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Dispatching.",
                missions=[MissionAction(drone_id="FALCON-01", action="launch")],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "launch"}).json()
        assert "missions" not in body
        assert "missing zone or distance" in body["message"]

    def test_recall_without_active_mission_is_rejected(self, db, cache, monkeypatch):
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Recalling.",
                missions=[MissionAction(drone_id="FALCON-01", action="recall")],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "recall"}).json()
        assert "missions" not in body
        assert "no_active_mission" in body["message"]

    def test_partial_success_returns_only_executed_actions(self, db, cache, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Dispatching two.",
                missions=[
                    MissionAction(
                        drone_id="FALCON-01", action="launch", zone="Riverside", distance_km=4.0
                    ),
                    MissionAction(
                        drone_id="GHOST-99", action="launch", zone="Riverside", distance_km=4.0
                    ),
                ],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "launch"}).json()
        assert [mission["drone_id"] for mission in body["missions"]] == ["FALCON-01"]
        assert "GHOST-99" in body["message"]


class TestRosterAutoExecution:
    def test_add_and_persisted_actions_json(self, db, cache, monkeypatch):
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Adding FALCON-11.",
                roster_changes=[RosterChange(drone_id="FALCON-11", action="add")],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "add a drone"}).json()
        assert body["roster_changes"] == [{"drone_id": "FALCON-11", "action": "add"}]

        assistant = _sync(repository.get_recent_messages(db))[-1]
        assert json.loads(assistant.actions) == {
            "missions": [],
            "roster_changes": [{"drone_id": "FALCON-11", "action": "add"}],
        }

    def test_duplicate_add_reported_in_message(self, db, cache, monkeypatch):
        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Adding.",
                roster_changes=[RosterChange(drone_id="FALCON-01", action="add")],
            ),
        )
        body = _client(db, cache).post("/api/chat", json={"message": "add"}).json()
        assert "roster_changes" not in body
        assert "drone_already_tracked" in body["message"]

    def test_remove_notifies_telemetry_source(self, db, cache, monkeypatch):
        removed: list[str] = []

        class _Source:
            async def add_drone(self, drone_id):
                pass

            async def remove_drone(self, drone_id):
                removed.append(drone_id)

        _stub_reply(
            monkeypatch,
            FlightDirectorReply(
                message="Removing.",
                roster_changes=[RosterChange(drone_id="FALCON-01", action="remove")],
            ),
        )
        body = _client(db, cache, _Source()).post("/api/chat", json={"message": "remove"}).json()
        assert body["roster_changes"] == [{"drone_id": "FALCON-01", "action": "remove"}]
        assert removed == ["FALCON-01"]


def _sync(coro):
    import asyncio

    return asyncio.run(coro)
