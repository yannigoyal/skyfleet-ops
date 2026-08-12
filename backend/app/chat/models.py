"""Data models for flight-director conversation history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CHAT_ROLES = ("user", "assistant")


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A stored chat turn — mirrors a row in the `chat_messages` table.

    `actions` holds the raw JSON string of executed missions/roster changes
    for assistant turns, and is None for operator turns.
    """

    id: str
    operator_id: str
    role: str
    content: str
    actions: str | None
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "actions": self.actions,
            "created_at": self.created_at,
        }
