"""Tests for the fleet roster API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.roster import create_roster_router
from app.telemetry import TelemetrySource


class FakeSource(TelemetrySource):
    def __init__(self) -> None:
        self.drone_ids: list[str] = []

    async def start(self, drone_ids: list[str]) -> None:
        self.drone_ids = list(drone_ids)

    async def stop(self) -> None:
        pass

    async def add_drone(self, drone_id: str) -> None:
        self.drone_ids.append(drone_id)

    async def remove_drone(self, drone_id: str) -> None:
        self.drone_ids.remove(drone_id)

    def get_drone_ids(self) -> list[str]:
        return list(self.drone_ids)


def _client(db, cache, source: TelemetrySource | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_roster_router(db, cache, source))
    return TestClient(app)


class TestListRoster:
    def test_returns_seeded_fleet(self, db, cache):
        client = _client(db, cache)
        response = client.get("/api/roster")
        assert response.status_code == 200
        drones = response.json()["drones"]
        assert len(drones) == 10
        assert drones[0]["drone_id"] == "FALCON-01"
        assert "added_at" in drones[0]

    def test_merges_latest_telemetry(self, db, cache):
        cache.update("FALCON-01", battery_pct=88.5, altitude_m=120.0, speed_kmh=42.0, status="idle")
        client = _client(db, cache)
        entry = next(
            d for d in client.get("/api/roster").json()["drones"] if d["drone_id"] == "FALCON-01"
        )
        assert entry["battery_pct"] == 88.5
        assert entry["altitude_m"] == 120.0
        assert entry["speed_kmh"] == 42.0
        assert entry["status"] == "idle"

    def test_omits_telemetry_when_no_reading(self, db, cache):
        client = _client(db, cache)
        entry = client.get("/api/roster").json()["drones"][0]
        assert entry.keys() == {"drone_id", "added_at"}


class TestAddDrone:
    def test_adds_drone(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={"drone_id": "FALCON-11"})
        assert response.status_code == 201
        assert response.json()["drone_id"] == "FALCON-11"
        drone_ids = [d["drone_id"] for d in client.get("/api/roster").json()["drones"]]
        assert "FALCON-11" in drone_ids

    def test_duplicate_returns_409(self, db, cache):
        client = _client(db, cache)
        response = client.post("/api/roster", json={"drone_id": "FALCON-01"})
        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "drone_already_tracked"

    def test_rejects_empty_drone_id(self, db, cache):
        client = _client(db, cache)
        assert client.post("/api/roster", json={"drone_id": ""}).status_code == 422

    def test_registers_with_telemetry_source(self, db, cache):
        source = FakeSource()
        client = _client(db, cache, source)
        client.post("/api/roster", json={"drone_id": "FALCON-11"})
        assert source.get_drone_ids() == ["FALCON-11"]

    def test_duplicate_does_not_touch_telemetry_source(self, db, cache):
        source = FakeSource()
        client = _client(db, cache, source)
        client.post("/api/roster", json={"drone_id": "FALCON-01"})
        assert source.get_drone_ids() == []


class TestRemoveDrone:
    def test_removes_drone(self, db, cache):
        client = _client(db, cache)
        response = client.delete("/api/roster/FALCON-01")
        assert response.status_code == 204
        drone_ids = [d["drone_id"] for d in client.get("/api/roster").json()["drones"]]
        assert "FALCON-01" not in drone_ids

    def test_unknown_drone_returns_404(self, db, cache):
        client = _client(db, cache)
        response = client.delete("/api/roster/GHOST-01")
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "unknown_drone"

    def test_deregisters_from_telemetry_source(self, db, cache):
        source = FakeSource()
        source.drone_ids = ["FALCON-01"]
        client = _client(db, cache, source)
        client.delete("/api/roster/FALCON-01")
        assert source.get_drone_ids() == []
