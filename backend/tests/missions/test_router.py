"""Tests for the mission dispatch/recall/status API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.missions import MissionQueue, create_missions_router

from .conftest import seed_telemetry


def _client(db, cache, queue: MissionQueue | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(create_missions_router(db, cache, queue if queue is not None else MissionQueue()))
    return TestClient(app)


class TestGetFleetStatus:
    def test_returns_budget_and_empty_missions(self, db, cache):
        client = _client(db, cache)
        response = client.get("/api/fleet")
        assert response.status_code == 200
        body = response.json()
        assert body["energy_budget_kwh"] == 500.0
        assert body["remaining_kwh"] == 500.0
        assert body["active_mission_count"] == 0
        assert body["missions"] == []


class TestLaunchMission:
    def test_launch_with_explicit_drone(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)
        response = client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.2}
        )
        assert response.status_code == 201
        body = response.json()
        assert body["drone_id"] == "FALCON-01"
        assert body["status"] == "en_route"
        assert "eta_minutes" in body

    def test_launch_unknown_drone_returns_404(self, db, cache):
        client = _client(db, cache)
        response = client.post(
            "/api/fleet/missions", json={"drone_id": "GHOST-01", "zone": "Riverside", "distance_km": 4.2}
        )
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "unknown_drone"

    def test_launch_insufficient_budget_returns_422(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)
        response = client.post(
            "/api/fleet/missions",
            json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 1000.0},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "insufficient_budget"

    def test_launch_drone_already_en_route_returns_409(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)
        client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.2}
        )
        response = client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Downtown", "distance_km": 2.0}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "drone_already_en_route"

    def test_launch_offline_drone_returns_409(self, db, cache):
        seed_telemetry(cache, "FALCON-01", status="offline")
        client = _client(db, cache)
        response = client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.2}
        )
        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "drone_unavailable"

    def test_auto_assign_dispatches_eligible_drone(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=90.0)
        client = _client(db, cache)
        response = client.post("/api/fleet/missions", json={"zone": "Riverside", "distance_km": 4.2})
        assert response.status_code == 201
        assert response.json()["drone_id"] == "FALCON-01"

    def test_auto_assign_queues_when_no_drone_eligible(self, db, cache):
        queue = MissionQueue()
        client = _client(db, cache, queue)
        response = client.post("/api/fleet/missions", json={"zone": "Riverside", "distance_km": 4.2})
        assert response.status_code == 202
        body = response.json()
        assert body["reason"] == "queued"
        assert body["cause"] == "no_eligible_drone"
        assert len(queue.pending()) == 1

    def test_rejects_non_positive_distance(self, db, cache):
        client = _client(db, cache)
        response = client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 0}
        )
        assert response.status_code == 422


class TestRecallMission:
    def test_recall_active_mission(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)
        client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.2}
        )
        response = client.delete("/api/fleet/missions/FALCON-01")
        assert response.status_code == 200
        assert response.json()["status"] == "recalled"

    def test_recall_with_no_active_mission_returns_404(self, db, cache):
        client = _client(db, cache)
        response = client.delete("/api/fleet/missions/FALCON-01")
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "no_active_mission"


class TestFleetHistory:
    def test_returns_snapshot_after_launch(self, db, cache):
        seed_telemetry(cache, "FALCON-01")
        client = _client(db, cache)
        client.post(
            "/api/fleet/missions", json={"drone_id": "FALCON-01", "zone": "Riverside", "distance_km": 4.2}
        )
        response = client.get("/api/fleet/history")
        assert response.status_code == 200
        assert len(response.json()["snapshots"]) == 1

    def test_empty_when_no_activity(self, db, cache):
        client = _client(db, cache)
        response = client.get("/api/fleet/history")
        assert response.json()["snapshots"] == []


class TestMissionQueueEndpoint:
    def test_lists_pending_entries(self, db, cache):
        queue = MissionQueue()
        client = _client(db, cache, queue)
        client.post("/api/fleet/missions", json={"zone": "Riverside", "distance_km": 4.2})
        response = client.get("/api/fleet/missions/queue")
        assert response.status_code == 200
        body = response.json()
        assert len(body["pending"]) == 1
        assert body["failed"] == []
