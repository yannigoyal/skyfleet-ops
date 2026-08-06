"""Tests for the mission scheduler background-task tick logic.

Each loop (run_assignment_scheduler, run_delivery_scheduler,
run_budget_snapshot_loop) is a thin `while True: sleep; tick()` wrapper —
these tests exercise the tick functions directly so nothing here waits on
real sleeps.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.missions import repository, scheduler
from app.missions.queue import MAX_ASSIGNMENT_ATTEMPTS, MissionQueue

from .conftest import seed_telemetry


class TestProcessDueAssignments:
    async def test_dispatches_once_a_drone_becomes_eligible(self, db, cache):
        queue = MissionQueue()
        queue.enqueue("Riverside", 4.2)

        # No telemetry yet - nothing eligible, request stays queued with a
        # recorded failure and backoff.
        await scheduler.process_due_assignments(db, cache, queue)
        assert len(queue.pending()) == 1
        assert queue.pending()[0].attempts == 1

        # A drone comes online - next tick should dispatch and drain the queue.
        seed_telemetry(cache, "FALCON-01", battery_pct=90.0)
        await scheduler.process_due_assignments(db, cache, queue, now=float("inf"))
        assert len(queue.pending()) == 0
        active = await repository.list_active_missions(db)
        assert len(active) == 1
        assert active[0].drone_id == "FALCON-01"

    async def test_respects_preferred_drone(self, db, cache):
        seed_telemetry(cache, "FALCON-01", battery_pct=40.0)
        seed_telemetry(cache, "FALCON-02", battery_pct=95.0)
        queue = MissionQueue()
        queue.enqueue("Riverside", 4.2, preferred_drone_id="FALCON-01")

        await scheduler.process_due_assignments(db, cache, queue)
        active = await repository.list_active_missions(db)
        assert active[0].drone_id == "FALCON-01"

    async def test_gives_up_after_max_attempts(self, db, cache):
        queue = MissionQueue()
        queue.enqueue("Riverside", 4.2)

        for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
            await scheduler.process_due_assignments(db, cache, queue, now=float("inf"))

        assert len(queue.pending()) == 0
        assert len(queue.failed()) == 1
        assert await repository.list_active_missions(db) == []

    async def test_not_due_yet_is_left_untouched(self, db, cache):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        queue.record_failure(entry.id, "no drone")  # sets a future next_attempt_at

        await scheduler.process_due_assignments(db, cache, queue, now=entry.next_attempt_at - 1)
        assert queue.pending()[0].attempts == 1  # unchanged - not retried


class TestDeliverOverdueMissions:
    async def test_marks_overdue_missions_delivered(self, db):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        await db.execute(
            "INSERT INTO missions "
            "(id, operator_id, drone_id, zone, distance_km, energy_cost_kwh, status, updated_at) "
            "VALUES (?, 'default', 'FALCON-01', 'Riverside', 4.2, 3.36, 'en_route', ?)",
            (str(uuid.uuid4()), past),
        )
        delivered = await scheduler.deliver_overdue_missions(db, cruise_speed_kmh=40.0)
        assert len(delivered) == 1

        row = await db.fetchone("SELECT status FROM missions WHERE drone_id = 'FALCON-01'")
        assert row["status"] == "delivered"

    async def test_no_op_when_nothing_overdue(self, db):
        delivered = await scheduler.deliver_overdue_missions(db, cruise_speed_kmh=40.0)
        assert delivered == []


class TestRecordBudgetSnapshot:
    async def test_records_a_snapshot(self, db):
        await scheduler.record_budget_snapshot(db)
        snapshots = await repository.list_budget_snapshots(db)
        assert len(snapshots) == 1
        assert snapshots[0]["remaining_kwh"] == 500.0
