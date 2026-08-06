"""In-memory mission assignment queue with retry/backoff bookkeeping.

Auto-assigned launches (no explicit drone_id) that can't be dispatched
immediately — no eligible drone, or insufficient budget right now — land
here instead of failing outright. The scheduler (see scheduler.py) retries
them with exponential backoff until one succeeds or MAX_ASSIGNMENT_ATTEMPTS
is exhausted, at which point the request moves to `failed` for inspection.

This queue never touches the database — mission rows only exist once a
request is actually dispatched, so a queued/failed request has no `missions`
table representation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace
from threading import Lock
from typing import Any

MAX_ASSIGNMENT_ATTEMPTS = 5
RETRY_BACKOFF_BASE_SECONDS = 2.0
RETRY_BACKOFF_MAX_SECONDS = 60.0


@dataclass
class QueuedMission:
    """A launch request awaiting drone assignment."""

    id: str
    zone: str
    distance_km: float
    preferred_drone_id: str | None
    queued_at: float
    attempts: int = 0
    last_error: str | None = None
    next_attempt_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "zone": self.zone,
            "distance_km": self.distance_km,
            "preferred_drone_id": self.preferred_drone_id,
            "queued_at": self.queued_at,
            "attempts": self.attempts,
            "last_error": self.last_error,
        }


class MissionQueue:
    """Thread-safe in-memory queue of pending mission-assignment requests."""

    def __init__(self) -> None:
        self._pending: dict[str, QueuedMission] = {}
        self._failed: dict[str, QueuedMission] = {}
        self._lock = Lock()

    def enqueue(
        self, zone: str, distance_km: float, preferred_drone_id: str | None = None
    ) -> QueuedMission:
        with self._lock:
            entry = QueuedMission(
                id=str(uuid.uuid4()),
                zone=zone,
                distance_km=distance_km,
                preferred_drone_id=preferred_drone_id,
                queued_at=time.time(),
            )
            self._pending[entry.id] = entry
            return entry

    def due(self, now: float | None = None) -> list[QueuedMission]:
        """Snapshot of queued requests whose backoff window has elapsed."""
        now = now if now is not None else time.time()
        with self._lock:
            return [entry for entry in self._pending.values() if entry.next_attempt_at <= now]

    def remove(self, mission_id: str) -> None:
        with self._lock:
            self._pending.pop(mission_id, None)

    def record_failure(self, mission_id: str, error: str) -> QueuedMission | None:
        """Record a failed assignment attempt. Moves to `failed` after max attempts."""
        with self._lock:
            entry = self._pending.get(mission_id)
            if entry is None:
                return None
            entry.attempts += 1
            entry.last_error = error
            if entry.attempts >= MAX_ASSIGNMENT_ATTEMPTS:
                self._pending.pop(mission_id, None)
                self._failed[mission_id] = entry
            else:
                backoff = min(
                    RETRY_BACKOFF_BASE_SECONDS * (2 ** (entry.attempts - 1)),
                    RETRY_BACKOFF_MAX_SECONDS,
                )
                entry.next_attempt_at = time.time() + backoff
            return replace(entry)

    def pending(self) -> list[QueuedMission]:
        with self._lock:
            return list(self._pending.values())

    def failed(self) -> list[QueuedMission]:
        with self._lock:
            return list(self._failed.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._pending)
