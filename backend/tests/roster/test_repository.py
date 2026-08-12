"""Tests for fleet roster persistence."""

from __future__ import annotations

import asyncio

import pytest

from app.roster import repository
from app.roster.models import DroneAlreadyTrackedError, RosterEntry, UnknownDroneError


class TestListRoster:
    async def test_returns_seeded_fleet(self, db):
        drone_ids = await repository.list_roster(db)
        assert len(drone_ids) == 10
        assert drone_ids[0] == "FALCON-01"
        assert drone_ids[-1] == "FALCON-10"

    async def test_entries_expose_added_at(self, db):
        entries = await repository.list_roster_entries(db)
        assert len(entries) == 10
        assert entries[0].drone_id == "FALCON-01"
        assert entries[0].added_at

    async def test_ignores_other_operators(self, db):
        await repository.add_drone(db, "GHOST-01", operator_id="other")
        assert "GHOST-01" not in await repository.list_roster(db)
        assert "GHOST-01" not in [e.drone_id for e in await repository.list_roster_entries(db)]


class TestAddDrone:
    async def test_adds_drone_to_roster(self, db):
        entry = await repository.add_drone(db, "FALCON-11")
        assert entry.drone_id == "FALCON-11"
        assert "FALCON-11" in await repository.list_roster(db)

    async def test_rejects_duplicate(self, db):
        with pytest.raises(DroneAlreadyTrackedError) as exc_info:
            await repository.add_drone(db, "FALCON-01")
        assert exc_info.value.drone_id == "FALCON-01"
        assert exc_info.value.reason == "drone_already_tracked"

    async def test_duplicate_does_not_grow_roster(self, db):
        with pytest.raises(DroneAlreadyTrackedError):
            await repository.add_drone(db, "FALCON-01")
        assert len(await repository.list_roster(db)) == 10


class TestRemoveDrone:
    async def test_removes_drone(self, db):
        await repository.remove_drone(db, "FALCON-01")
        assert "FALCON-01" not in await repository.list_roster(db)

    async def test_rejects_unknown_drone(self, db):
        with pytest.raises(UnknownDroneError) as exc_info:
            await repository.remove_drone(db, "GHOST-01")
        assert exc_info.value.reason == "unknown_drone"

    async def test_remove_then_readd(self, db):
        await repository.remove_drone(db, "FALCON-01")
        await repository.add_drone(db, "FALCON-01")
        assert "FALCON-01" in await repository.list_roster(db)


class TestConcurrentDuplicateAdd:
    async def test_only_one_row_survives_overlapping_add(self, db):
        """The UNIQUE (operator_id, drone_id) constraint, not application-level
        checking, is what enforces single-row semantics under overlap."""
        results = await asyncio.gather(
            repository.add_drone(db, "FALCON-11"),
            repository.add_drone(db, "FALCON-11"),
            return_exceptions=True,
        )
        successes = [r for r in results if isinstance(r, RosterEntry)]
        failures = [r for r in results if isinstance(r, DroneAlreadyTrackedError)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert (await repository.list_roster(db)).count("FALCON-11") == 1
