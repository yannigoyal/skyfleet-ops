"""Tests for flight-director chat history persistence."""

from __future__ import annotations

import sqlite3

import pytest

from app.chat import repository


class TestAppendMessage:
    async def test_user_turn_has_null_actions(self, db):
        message = await repository.append_message(db, "user", "hi")

        assert message.actions is None
        assert message.operator_id == "default"
        assert len(message.id) == 36  # UUID4 string form

        rows = await db.fetchall("SELECT * FROM chat_messages WHERE id = ?", (message.id,))
        assert rows[0]["actions"] is None
        assert rows[0]["created_at"] == message.created_at

    async def test_assistant_actions_round_trip_as_dict(self, db):
        actions = {"missions": [{"drone_id": "FALCON-01", "action": "launch"}], "roster_changes": []}
        message = await repository.append_message(db, "assistant", "done", actions=actions)

        assert message.actions == actions

        stored = await repository.get_recent_messages(db, limit=1)
        assert stored[0].actions == actions
        assert isinstance(stored[0].actions, dict)

    async def test_invalid_role_rejected_by_check_constraint(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            await repository.append_message(db, "system", "not a valid role")


class TestGetRecentMessages:
    async def test_empty_table_returns_empty_list(self, db):
        assert await repository.get_recent_messages(db) == []

    async def test_limit_keeps_most_recent_n_oldest_first(self, db):
        for i in range(5):
            await repository.append_message(db, "user", f"message {i}")

        recent = await repository.get_recent_messages(db, limit=3)

        assert [m.content for m in recent] == ["message 2", "message 3", "message 4"]

    async def test_same_timestamp_tiebreak_preserves_insertion_order(self, db, monkeypatch):
        monkeypatch.setattr(repository, "_now", lambda: "2026-01-01T00:00:00+00:00")

        await repository.append_message(db, "user", "first")
        await repository.append_message(db, "assistant", "second")

        recent = await repository.get_recent_messages(db, limit=20)

        assert [m.content for m in recent] == ["first", "second"]
