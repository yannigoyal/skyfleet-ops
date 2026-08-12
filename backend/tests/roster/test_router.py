"""End-to-end tests for the fleet roster API."""

from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.roster import create_roster_router, repository
from app.roster import service as roster_service
from app.roster.models import RosterEntry
from app.telemetry import TelemetrySource

from .conftest import FakeSource, seed_telemetry


def _client(db, cache, source: TelemetrySource | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_roster_router(db, cache, source))
    return TestClient(app)


class TestListRoster:
    def test_returns_seeded_fleet_in_drone_id_order(self, db, cache):
        client = _client(db, cache)
        response = client.get("/api/roster")
        assert response.status_code == 200
        drones = response.json()["drones"]
        assert len(drones) == 10
        assert [d["drone_id"] for d in drones] == sorted(d["drone_id"] for d in drones)
        assert drones[0]["drone_id"] == "FALCON-01"

    def test_merges_latest_telemetry(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=88.5, status="idle")
        client = _client(db, cache)
        entry = next(
            d for d in client.get("/api/roster").json()["drones"] if d["drone_id"] == "FALCON-01"
        )
        assert entry["battery_pct"] == 88.5
        assert entry["altitude_m"] == 100.0
        assert entry["speed_kmh"] == 40.0
        assert entry["status"] == "idle"


class TestAddDrone:
    def test_adds_drone_and_lists_it(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={"drone_id": "FALCON-11"})
        assert response.status_code == 201
        assert response.json()["drone_id"] == "FALCON-11"

        drone_ids = [d["drone_id"] for d in client.get("/api/roster").json()["drones"]]
        assert "FALCON-11" in drone_ids

    def test_registers_with_telemetry_source(self, db, cache):
        source = FakeSource()
        client = _client(db, cache, source)
        client.post("/api/roster", json={"drone_id": "FALCON-11"})
        assert source.get_drone_ids() == ["FALCON-11"]

    def test_duplicate_returns_409(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={"drone_id": "FALCON-01"})
        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "drone_already_tracked"

    def test_rejects_empty_drone_id(self, db, cache):
        client = _client(db, cache)
        assert client.post("/api/roster", json={"drone_id": ""}).status_code == 422


class TestRemoveDrone:
    def test_first_delete_returns_204_and_drone_disappears(self, db, cache):
        client = _client(db, cache)
        response = client.delete("/api/roster/FALCON-01")
        assert response.status_code == 204

        drone_ids = [d["drone_id"] for d in client.get("/api/roster").json()["drones"]]
        assert "FALCON-01" not in drone_ids

    def test_second_delete_returns_404_unknown_drone(self, db, cache):
        client = _client(db, cache)
        client.delete("/api/roster/FALCON-01")
        response = client.delete("/api/roster/FALCON-01")
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "unknown_drone"

    def test_deregisters_from_a_working_source(self, db, cache):
        source = FakeSource()
        source.drone_ids = ["FALCON-01"]
        client = _client(db, cache, source)
        response = client.delete("/api/roster/FALCON-01")
        assert response.status_code == 204
        assert source.get_drone_ids() == []


class TestAppWiring:
    def test_roster_route_mounted_and_telemetry_source_is_singleton(self):
        import app.main

        # Enumerate mounted paths via the OpenAPI schema rather than walking
        # app.routes directly: the installed FastAPI/Starlette version wraps
        # included routers in an internal _IncludedRouter object that does
        # not expose a `.path` attribute at the top level.
        paths = set(app.main.app.openapi()["paths"].keys())
        assert "/api/roster" in paths
        assert isinstance(app.main.telemetry_source, TelemetrySource)


class TestAddDroneErrors:
    def test_duplicate_returns_409_and_roster_still_lists_ten(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={"drone_id": "FALCON-01"})
        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "drone_already_tracked"
        assert len(client.get("/api/roster").json()["drones"]) == 10

    def test_empty_drone_id_returns_422_and_roster_unchanged(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={"drone_id": ""})
        assert response.status_code == 422
        assert len(client.get("/api/roster").json()["drones"]) == 10

    def test_missing_drone_id_returns_422_and_roster_unchanged(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={})
        assert response.status_code == 422
        assert len(client.get("/api/roster").json()["drones"]) == 10

    def test_delete_unknown_drone_returns_404(self, db, cache):
        client = _client(db, cache)
        response = client.delete("/api/roster/GHOST-01")
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "unknown_drone"


class TestTelemetryMerge:
    def test_no_telemetry_key_set_is_exactly_drone_id_and_added_at(self, db, cache):
        client = _client(db, cache)
        entry = next(
            d for d in client.get("/api/roster").json()["drones"] if d["drone_id"] == "FALCON-01"
        )
        assert set(entry.keys()) == {"drone_id", "added_at"}

    def test_with_telemetry_key_set_adds_exactly_four_fields(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)
        entry = next(
            d for d in client.get("/api/roster").json()["drones"] if d["drone_id"] == "FALCON-01"
        )
        assert set(entry.keys()) == {
            "drone_id",
            "added_at",
            "battery_pct",
            "altitude_m",
            "speed_kmh",
            "status",
        }

    async def test_other_operator_drone_absent_from_response(self, db, cache):
        await repository.add_drone(db, "GHOST-01", operator_id="other")
        client = _client(db, cache)
        drone_ids = [d["drone_id"] for d in client.get("/api/roster").json()["drones"]]
        assert "GHOST-01" not in drone_ids


class TestLayering:
    def test_post_and_delete_delegate_to_service(self, db, cache, monkeypatch):
        calls: dict[str, str] = {}

        async def fake_add_drone(db_arg, source_arg, drone_id):
            calls["add"] = drone_id
            return RosterEntry(id="x", operator_id="default", drone_id=drone_id, added_at="now")

        async def fake_remove_drone(db_arg, source_arg, drone_id):
            calls["remove"] = drone_id

        monkeypatch.setattr(roster_service, "add_drone", fake_add_drone)
        monkeypatch.setattr(roster_service, "remove_drone", fake_remove_drone)

        client = _client(db, cache)

        add_response = client.post("/api/roster", json={"drone_id": "FALCON-11"})
        assert add_response.status_code == 201
        assert calls["add"] == "FALCON-11"

        delete_response = client.delete("/api/roster/FALCON-11")
        assert delete_response.status_code == 204
        assert calls["remove"] == "FALCON-11"

    def test_roster_submodules_import_cleanly(self):
        for name in ("models", "service", "repository", "router"):
            importlib.import_module(f"app.roster.{name}")
