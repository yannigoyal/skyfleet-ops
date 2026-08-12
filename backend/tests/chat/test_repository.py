"""Tests for chat history persistence."""

from __future__ import annotations

import json

from app.chat import repository


class TestAppendMessage:
    async def test_stores_user_message(self, db):
        message = await repository.append_message(db, "user", "fleet status?")
        assert message.role == "user"
        assert message.content == "fleet status?"
        assert message.actions is None
        assert message.created_at

    async def test_stores_assistant_actions_json(self, db):
        actions = json.dumps({"missions": [{"drone_id": "FALCON-03", "action": "launch"}]})
        await repository.append_message(db, "assistant", "Launched FALCON-03.", actions)
        stored = await repository.get_recent_messages(db)
        assert json.loads(stored[0].actions)["missions"][0]["drone_id"] == "FALCON-03"


class TestGetRecentMessages:
    async def test_empty_by_default(self, db):
        assert await repository.get_recent_messages(db) == []

    async def test_returns_chronological_order(self, db):
        for i in range(3):
            await repository.append_message(db, "user", f"message {i}")
        contents = [m.content for m in await repository.get_recent_messages(db)]
        assert contents == ["message 0", "message 1", "message 2"]

    async def test_limit_keeps_most_recent(self, db):
        for i in range(5):
            await repository.append_message(db, "user", f"message {i}")
        contents = [m.content for m in await repository.get_recent_messages(db, limit=2)]
        assert contents == ["message 3", "message 4"]

    async def test_ignores_other_operators(self, db):
        await repository.append_message(db, "user", "other fleet", operator_id="other")
        assert await repository.get_recent_messages(db) == []
