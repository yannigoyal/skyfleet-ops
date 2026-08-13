"""End-to-end tests for the AI flight-director chat endpoint."""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.chat import create_chat_router, llm, repository
from app.chat.models import ChatMessage
from app.missions import MissionQueue, create_missions_router
from app.telemetry import TelemetrySource

from .conftest import seed_telemetry

DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]


def _client(db, cache, source: TelemetrySource | None = None) -> TestClient:
    """Mount both the chat and missions routers on one app so a chat-issued
    launch runs inside the TestClient's own event loop — Database's
    asyncio.Lock must not be first used from a different loop than the one
    serving the request."""
    app = FastAPI()
    app.include_router(create_chat_router(db, cache, source))
    app.include_router(create_missions_router(db, cache, MissionQueue()))
    return TestClient(app)


def _seed_fleet_telemetry(cache) -> None:
    for drone_id in DEFAULT_FLEET:
        seed_telemetry(cache, drone_id)


class TestChatTurn:
    async def test_mock_launch_executes_and_persists(self, db, cache, mock_mode):
        _seed_fleet_telemetry(cache)
        client = _client(db, cache)

        response = client.post("/api/chat", json={"message": "please launch a drone"})

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == {"message", "missions", "roster_changes", "errors"}
        assert len(body["missions"]) == 1
        assert body["missions"][0]["action"] == "launch"

        fleet_response = client.get("/api/fleet")
        assert fleet_response.status_code == 200
        fleet_body = fleet_response.json()
        assert fleet_body["active_mission_count"] == 1
        assert fleet_body["remaining_kwh"] < 500.0

        rows = await db.fetchall("SELECT * FROM chat_messages ORDER BY created_at, rowid", ())
        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[1]["role"] == "assistant"

        actions = json.loads(rows[1]["actions"])
        assert actions["missions"][0]["action"] == "launch"

    async def test_informational_message_executes_nothing(self, db, cache, mock_mode):
        _seed_fleet_telemetry(cache)
        client = _client(db, cache)

        response = client.post("/api/chat", json={"message": "how is the fleet doing?"})

        assert response.status_code == 200
        body = response.json()
        assert body["missions"] == []
        assert body["roster_changes"] == []
        assert body["errors"] == []

        rows = await db.fetchall("SELECT * FROM chat_messages", ())
        assert len(rows) == 2


class TestAppWiring:
    def test_chat_route_is_mounted(self):
        import app.main

        # Enumerate mounted paths via the OpenAPI schema rather than walking
        # app.routes directly: the installed FastAPI/Starlette version wraps
        # included routers in an internal _IncludedRouter object that does
        # not expose a `.path` attribute at the top level (matches
        # tests/roster/test_router.py::TestAppWiring's established pattern).
        paths = set(app.main.app.openapi()["paths"].keys())
        assert "/api/chat" in paths


class TestMessageValidation:
    async def test_empty_string_returns_422_and_writes_nothing(self, db, cache, mock_mode):
        client = _client(db, cache)
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 422
        assert await db.fetchall("SELECT * FROM chat_messages", ()) == []

    async def test_whitespace_only_returns_422_and_writes_nothing(self, db, cache, mock_mode):
        client = _client(db, cache)
        response = client.post("/api/chat", json={"message": "   "})
        assert response.status_code == 422
        assert await db.fetchall("SELECT * FROM chat_messages", ()) == []

    async def test_missing_field_returns_422_and_writes_nothing(self, db, cache, mock_mode):
        client = _client(db, cache)
        response = client.post("/api/chat", json={})
        assert response.status_code == 422
        assert await db.fetchall("SELECT * FROM chat_messages", ()) == []

    async def test_multibyte_message_round_trips(self, db, cache, mock_mode):
        _seed_fleet_telemetry(cache)
        client = _client(db, cache)
        original = "café résumé 你好世界 status check 🚀🛰️"

        response = client.post("/api/chat", json={"message": original})

        assert response.status_code == 200

        rows = await db.fetchall(
            "SELECT * FROM chat_messages WHERE role = 'user' ORDER BY created_at, rowid", ()
        )
        assert rows[-1]["content"] == original

        history = await repository.get_recent_messages(db, limit=20)
        user_turns = [message for message in history if message.role == "user"]
        assert user_turns[-1].content == original


class TestHistoryReplay:
    async def test_second_turn_sees_first_turns_rows(self, db, cache, mock_mode):
        _seed_fleet_telemetry(cache)
        client = _client(db, cache)

        first = client.post("/api/chat", json={"message": "fleet status please"})
        assert first.status_code == 200
        second = client.post("/api/chat", json={"message": "anything else to report?"})
        assert second.status_code == 200

        rows = await db.fetchall("SELECT * FROM chat_messages", ())
        assert len(rows) == 4

    def test_build_messages_orders_system_history_then_user(self):
        history = [
            ChatMessage(
                id="1", operator_id="default", role="user", content="hi", actions=None, created_at="t1"
            ),
            ChatMessage(
                id="2",
                operator_id="default",
                role="assistant",
                content="hello",
                actions=None,
                created_at="t2",
            ),
        ]
        fleet_context = {"remaining_kwh": 500.0}

        messages = llm.build_messages(fleet_context, history, "new message")

        assert messages[0] == {"role": "system", "content": llm.SYSTEM_PROMPT}
        assert messages[1]["role"] == "system"
        assert "remaining_kwh" in messages[1]["content"]
        assert messages[2] == {"role": "user", "content": "hi"}
        assert messages[3] == {"role": "assistant", "content": "hello"}
        assert messages[4] == {"role": "user", "content": "new message"}
