"""Tests for roster models and validation error types."""

from __future__ import annotations

from app.roster.models import (
    DroneAlreadyTrackedError,
    RosterEntry,
    RosterError,
    UnknownDroneError,
)


class TestRosterEntry:
    def test_to_dict_shape(self):
        entry = RosterEntry(
            id="r1",
            operator_id="default",
            drone_id="FALCON-01",
            added_at="2026-01-01T00:00:00+00:00",
        )
        data = entry.to_dict()
        assert set(data.keys()) == {"drone_id", "added_at"}
        assert data["drone_id"] == "FALCON-01"
        assert data["added_at"] == "2026-01-01T00:00:00+00:00"


class TestRosterErrors:
    def test_base_reason_defaults(self):
        assert RosterError().reason == "roster_error"

    def test_reason_codes(self):
        assert DroneAlreadyTrackedError("FALCON-01").reason == "drone_already_tracked"
        assert UnknownDroneError("FALCON-01").reason == "unknown_drone"

    def test_subclasses_of_roster_error(self):
        assert isinstance(DroneAlreadyTrackedError("FALCON-01"), RosterError)
        assert isinstance(UnknownDroneError("FALCON-01"), RosterError)

    def test_carries_drone_id(self):
        assert DroneAlreadyTrackedError("FALCON-01").drone_id == "FALCON-01"
        assert UnknownDroneError("FALCON-02").drone_id == "FALCON-02"
