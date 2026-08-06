"""Tests for the in-memory mission assignment queue."""

from __future__ import annotations

from app.missions.queue import MAX_ASSIGNMENT_ATTEMPTS, MissionQueue


class TestEnqueue:
    def test_enqueue_adds_pending_entry(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        assert entry.zone == "Riverside"
        assert entry.distance_km == 4.2
        assert entry.attempts == 0
        assert len(queue) == 1

    def test_enqueue_with_preferred_drone(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2, preferred_drone_id="FALCON-01")
        assert entry.preferred_drone_id == "FALCON-01"

    def test_entries_get_unique_ids(self):
        queue = MissionQueue()
        first = queue.enqueue("Riverside", 4.2)
        second = queue.enqueue("Downtown", 2.0)
        assert first.id != second.id


class TestDue:
    def test_new_entry_is_immediately_due(self):
        queue = MissionQueue()
        queue.enqueue("Riverside", 4.2)
        assert len(queue.due()) == 1

    def test_backed_off_entry_not_due_yet(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        queue.record_failure(entry.id, "no drone")
        assert queue.due(now=entry.next_attempt_at - 1) == []

    def test_backed_off_entry_due_after_window(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        queue.record_failure(entry.id, "no drone")
        due = queue.due(now=entry.next_attempt_at + 1)
        assert len(due) == 1


class TestRecordFailure:
    def test_increments_attempts_and_records_error(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        updated = queue.record_failure(entry.id, "no drone")
        assert updated.attempts == 1
        assert updated.last_error == "no drone"

    def test_backoff_grows_with_each_failure(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        first = queue.record_failure(entry.id, "err")
        second = queue.record_failure(entry.id, "err")
        assert second.next_attempt_at > first.next_attempt_at

    def test_moves_to_failed_after_max_attempts(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        for _ in range(MAX_ASSIGNMENT_ATTEMPTS):
            queue.record_failure(entry.id, "err")
        assert len(queue.pending()) == 0
        assert len(queue.failed()) == 1
        assert queue.failed()[0].attempts == MAX_ASSIGNMENT_ATTEMPTS

    def test_unknown_id_returns_none(self):
        queue = MissionQueue()
        assert queue.record_failure("does-not-exist", "err") is None


class TestRemove:
    def test_remove_clears_pending_entry(self):
        queue = MissionQueue()
        entry = queue.enqueue("Riverside", 4.2)
        queue.remove(entry.id)
        assert len(queue) == 0

    def test_remove_unknown_id_is_a_noop(self):
        queue = MissionQueue()
        queue.remove("does-not-exist")
        assert len(queue) == 0
