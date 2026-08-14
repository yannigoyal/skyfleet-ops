"""End-to-end tests for the AI flight-director chat endpoint."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.chat import create_chat_router, llm, repository
from app.chat.models import ChatMessage
from app.db import Database
from app.missions import MissionQueue, create_missions_router
from app.missions import repository as missions_repository
from app.roster import create_roster_router
from app.telemetry import TelemetryCache, TelemetrySource

from .conftest import FakeSource, seed_telemetry

DEFAULT_FLEET = [f"FALCON-{i:02d}" for i in range(1, 11)]

CHAT_PACKAGE_DIR = Path(__file__).resolve().parents[2] / "app" / "chat"


def _client(db, cache, source: TelemetrySource | None = None) -> TestClient:
    """Mount both the chat and missions routers on one app so a chat-issued
    launch runs inside the TestClient's own event loop — Database's
    asyncio.Lock must not be first used from a different loop than the one
    serving the request."""
    app = FastAPI()
    app.include_router(create_chat_router(db, cache, source))
    app.include_router(create_missions_router(db, cache, MissionQueue()))
    return TestClient(app)


def _client_with_roster(db, cache, source: TelemetrySource | None = None) -> TestClient:
    """Mount the roster and missions routers (the manual side of the
    differential — no chat router involved)."""
    app = FastAPI()
    app.include_router(create_roster_router(db, cache, source))
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

    async def test_mock_launch_dispatches_the_drone_the_operator_named(self, db, cache, mock_mode):
        """UAT regression: the message names FALCON-03, which is not the first
        idle roster drone. The mock used to substitute the roster-order default,
        so the operator watched a drone they never asked for leave the pad."""
        _seed_fleet_telemetry(cache)
        client = _client(db, cache)

        response = client.post("/api/chat", json={"message": "Launch FALCON-03 to Riverside"})

        assert response.status_code == 200
        body = response.json()
        assert body["errors"] == []
        assert [mission["drone_id"] for mission in body["missions"]] == ["FALCON-03"]

        fleet_body = client.get("/api/fleet").json()
        assert [mission["drone_id"] for mission in fleet_body["missions"]] == ["FALCON-03"]

    async def test_mock_recall_targets_the_drone_the_operator_named(self, db, cache, mock_mode):
        """The recall counterpart: two drones en route, and the message names
        the second. Recalling active[0] would ground the wrong one."""
        _seed_fleet_telemetry(cache)
        client = _client(db, cache)
        for drone_id in ("FALCON-01", "FALCON-03"):
            launch = client.post(
                "/api/fleet/missions",
                json={"drone_id": drone_id, "zone": "Riverside", "distance_km": 4.0},
            )
            assert launch.status_code == 201

        response = client.post("/api/chat", json={"message": "Recall FALCON-03"})

        assert response.status_code == 200
        body = response.json()
        assert body["errors"] == []
        assert [mission["drone_id"] for mission in body["missions"]] == ["FALCON-03"]

        fleet_body = client.get("/api/fleet").json()
        assert [mission["drone_id"] for mission in fleet_body["missions"]] == ["FALCON-01"]

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


def _mock_reply(monkeypatch, reply: llm.FlightDirectorReply) -> None:
    """Force generate_reply's mock branch to return an exact, hand-built
    reply instead of depending on mock_reply's keyword heuristics."""
    monkeypatch.setattr(llm, "mock_reply", lambda fleet_context, user_message: reply)


class TestRecall:
    async def test_recall_moves_mission_to_terminal_state(self, db, cache, mock_mode, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)

        launch = client.post(
            "/api/fleet/missions",
            json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.0},
        )
        assert launch.status_code == 201

        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Recalling FALCON-01.",
                missions=[llm.MissionAction(drone_id="FALCON-01", action="recall")],
            ),
        )

        response = client.post("/api/chat", json={"message": "recall it"})

        assert response.status_code == 200
        body = response.json()
        assert body["errors"] == []
        assert body["missions"] == [{"drone_id": "FALCON-01", "action": "recall"}]

        fleet_body = client.get("/api/fleet").json()
        assert fleet_body["active_mission_count"] == 0

    async def test_recall_with_no_active_mission_returns_readable_error(
        self, db, cache, mock_mode, monkeypatch
    ):
        client = _client(db, cache)
        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Recalling FALCON-01.",
                missions=[llm.MissionAction(drone_id="FALCON-01", action="recall")],
            ),
        )

        response = client.post("/api/chat", json={"message": "recall it"})

        assert response.status_code == 200
        body = response.json()
        assert body["missions"] == []
        assert len(body["errors"]) == 1
        assert "FALCON-01" in body["errors"][0]
        assert "no_active_mission" in body["errors"][0]


class TestRosterChanges:
    async def test_add_new_drone_creates_row_and_registers_source(
        self, db, cache, mock_mode, monkeypatch
    ):
        source = FakeSource()
        client = _client(db, cache, source)
        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Adding FALCON-11.",
                roster_changes=[llm.RosterChange(drone_id="FALCON-11", action="add")],
            ),
        )

        response = client.post("/api/chat", json={"message": "add FALCON-11"})

        assert response.status_code == 200
        body = response.json()
        assert body["errors"] == []
        assert body["roster_changes"] == [{"drone_id": "FALCON-11", "action": "add"}]
        assert "FALCON-11" in source.get_drone_ids()

        rows = await db.fetchall(
            "SELECT drone_id FROM fleet_roster WHERE drone_id = ?", ("FALCON-11",)
        )
        assert len(rows) == 1

    async def test_add_duplicate_drone_returns_readable_error(
        self, db, cache, mock_mode, monkeypatch
    ):
        client = _client(db, cache)
        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Adding FALCON-01.",
                roster_changes=[llm.RosterChange(drone_id="FALCON-01", action="add")],
            ),
        )

        response = client.post("/api/chat", json={"message": "add FALCON-01"})

        assert response.status_code == 200
        body = response.json()
        assert body["roster_changes"] == []
        assert len(body["errors"]) == 1
        assert "FALCON-01" in body["errors"][0]
        assert "drone_already_tracked" in body["errors"][0]

    async def test_remove_tracked_drone_deletes_row_and_deregisters(
        self, db, cache, mock_mode, monkeypatch
    ):
        source = FakeSource()
        source.drone_ids = ["FALCON-01"]
        client = _client(db, cache, source)
        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Removing FALCON-01.",
                roster_changes=[llm.RosterChange(drone_id="FALCON-01", action="remove")],
            ),
        )

        response = client.post("/api/chat", json={"message": "remove FALCON-01"})

        assert response.status_code == 200
        body = response.json()
        assert body["errors"] == []
        assert body["roster_changes"] == [{"drone_id": "FALCON-01", "action": "remove"}]
        assert source.get_drone_ids() == []

        rows = await db.fetchall(
            "SELECT drone_id FROM fleet_roster WHERE drone_id = ?", ("FALCON-01",)
        )
        assert rows == []

    async def test_remove_untracked_drone_returns_readable_error(
        self, db, cache, mock_mode, monkeypatch
    ):
        client = _client(db, cache)
        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Removing GHOST-01.",
                roster_changes=[llm.RosterChange(drone_id="GHOST-01", action="remove")],
            ),
        )

        response = client.post("/api/chat", json={"message": "remove GHOST-01"})

        assert response.status_code == 200
        body = response.json()
        assert body["roster_changes"] == []
        assert len(body["errors"]) == 1
        assert "GHOST-01" in body["errors"][0]
        assert "unknown_drone" in body["errors"][0]

    async def test_remove_drone_with_active_mission_recalls_first(
        self, db, cache, mock_mode, monkeypatch
    ):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)

        launch = client.post(
            "/api/fleet/missions",
            json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.0},
        )
        assert launch.status_code == 201

        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Removing FALCON-01.",
                roster_changes=[llm.RosterChange(drone_id="FALCON-01", action="remove")],
            ),
        )

        response = client.post("/api/chat", json={"message": "remove FALCON-01"})

        assert response.status_code == 200
        assert response.json()["errors"] == []

        rows = await db.fetchall(
            "SELECT id FROM missions WHERE drone_id = ? AND status = 'en_route'", ("FALCON-01",)
        )
        assert rows == []


class TestSequentialExecution:
    async def test_second_launch_fails_when_first_exhausts_budget(
        self, db, cache, mock_mode, monkeypatch
    ):
        seed_telemetry(cache, "FALCON-01")
        seed_telemetry(cache, "FALCON-02")
        client = _client(db, cache)

        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Launching two drones.",
                missions=[
                    llm.MissionAction(
                        drone_id="FALCON-01", action="launch", zone="Riverside", distance_km=600.0
                    ),
                    llm.MissionAction(
                        drone_id="FALCON-02", action="launch", zone="Downtown", distance_km=30.0
                    ),
                ],
            ),
        )

        response = client.post("/api/chat", json={"message": "launch two drones"})

        assert response.status_code == 200
        body = response.json()
        assert len(body["missions"]) == 1
        assert body["missions"][0]["drone_id"] == "FALCON-01"
        assert len(body["errors"]) == 1
        assert "FALCON-02" in body["errors"][0]
        assert "insufficient_budget" in body["errors"][0]

        fleet_body = client.get("/api/fleet").json()
        assert fleet_body["remaining_kwh"] == 20.0


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

    async def test_over_max_length_returns_422_and_writes_nothing(self, db, cache, mock_mode):
        client = _client(db, cache)
        response = client.post("/api/chat", json={"message": "a" * 4001})
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


class TestRosterServiceParity:
    """D2: chat-issued and manual roster removal must leave identical state.

    Each half runs against its own freshly initialised Database (separate
    tmp_path subdirectories) so neither side can see the other's rows —
    a true differential, not two assertions against shared state.
    """

    async def test_chat_and_manual_removal_leave_identical_state(
        self, tmp_path, mock_mode, monkeypatch
    ):
        # Side A: remove FALCON-01 through a chat-issued roster change.
        db_a = Database(tmp_path / "side_a" / "skyfleet.db")
        db_a.ensure_initialized()
        cache_a = TelemetryCache()
        _seed_fleet_telemetry(cache_a)
        client_a = _client(db_a, cache_a)

        launch_a = client_a.post(
            "/api/fleet/missions",
            json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.0},
        )
        assert launch_a.status_code == 201

        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Removing FALCON-01.",
                roster_changes=[llm.RosterChange(drone_id="FALCON-01", action="remove")],
            ),
        )
        chat_response = client_a.post("/api/chat", json={"message": "remove FALCON-01"})
        assert chat_response.status_code == 200
        assert chat_response.json()["errors"] == []

        # Side B: remove FALCON-01 through the manual DELETE endpoint.
        db_b = Database(tmp_path / "side_b" / "skyfleet.db")
        db_b.ensure_initialized()
        cache_b = TelemetryCache()
        _seed_fleet_telemetry(cache_b)
        client_b = _client_with_roster(db_b, cache_b)

        launch_b = client_b.post(
            "/api/fleet/missions",
            json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.0},
        )
        assert launch_b.status_code == 201

        delete_response = client_b.delete("/api/roster/FALCON-01")
        assert delete_response.status_code == 204

        # Compare final state, A against B, so a divergence in either
        # direction fails.
        roster_a = [r["drone_id"] for r in await db_a.fetchall(
            "SELECT drone_id FROM fleet_roster ORDER BY drone_id", ()
        )]
        roster_b = [r["drone_id"] for r in await db_b.fetchall(
            "SELECT drone_id FROM fleet_roster ORDER BY drone_id", ()
        )]
        assert roster_a == roster_b

        en_route_a = await missions_repository.list_active_drone_ids(db_a)
        en_route_b = await missions_repository.list_active_drone_ids(db_b)
        assert en_route_a == en_route_b == set()

        status_a = [r["status"] for r in await db_a.fetchall(
            "SELECT status FROM missions WHERE drone_id = ?", ("FALCON-01",)
        )]
        status_b = [r["status"] for r in await db_b.fetchall(
            "SELECT status FROM missions WHERE drone_id = ?", ("FALCON-01",)
        )]
        assert status_a == status_b

        remaining_a = await missions_repository.get_remaining_kwh(db_a)
        remaining_b = await missions_repository.get_remaining_kwh(db_b)
        assert remaining_a == remaining_b

        db_a.close()
        db_b.close()

    async def test_chat_removal_recalls_the_active_mission(self, db, cache, mock_mode, monkeypatch):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)

        launch = client.post(
            "/api/fleet/missions",
            json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.0},
        )
        assert launch.status_code == 201

        _mock_reply(
            monkeypatch,
            llm.FlightDirectorReply(
                message="Removing FALCON-01.",
                roster_changes=[llm.RosterChange(drone_id="FALCON-01", action="remove")],
            ),
        )
        response = client.post("/api/chat", json={"message": "remove FALCON-01"})
        assert response.status_code == 200
        assert response.json()["errors"] == []

        assert await missions_repository.get_active_mission_for_drone(db, "FALCON-01") is None

        row = await db.fetchone(
            "SELECT status FROM missions WHERE drone_id = ?", ("FALCON-01",)
        )
        assert row["status"] != "en_route"


class TestImportBoundary:
    """Structural checks that fail at import-statement level before any
    behavioural divergence could occur."""

    def test_chat_router_reaches_domains_only_through_services(self):
        source_path = CHAT_PACKAGE_DIR / "router.py"
        tree = ast.parse(source_path.read_text())

        mods: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                mods.add(base)
                mods.update(f"{base}.{alias.name}" for alias in node.names)

        forbidden_prefixes = ("app.roster.repository", "app.missions.repository")
        bad = sorted(m for m in mods if m.startswith(forbidden_prefixes))
        assert not bad, f"chat/router.py must not import domain persistence modules, found: {bad}"
        assert "app.roster.service" in mods
        assert "app.missions.service" in mods

    def test_chat_package_writes_only_its_own_table(self):
        forbidden_tables = ("MISSIONS", "MISSION_LOG", "BUDGET_SNAPSHOTS", "FLEET_ROSTER")
        found_chat_messages_write = False

        for path in CHAT_PACKAGE_DIR.rglob("*.py"):
            content = path.read_text().upper()
            for table in forbidden_tables:
                assert f"INSERT INTO {table}" not in content, f"{path} inserts into {table}"
                assert f"UPDATE {table} " not in content, f"{path} updates {table}"
                assert f"DELETE FROM {table}" not in content, f"{path} deletes from {table}"
            if "INSERT INTO CHAT_MESSAGES" in content:
                found_chat_messages_write = True

        assert found_chat_messages_write, "expected chat/repository.py to still write chat_messages"
