"""SQLite-backed persistence for flight-director chat history."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from app.db import Database

from .models import ChatMessage

DEFAULT_OPERATOR_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_message(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        operator_id=row["operator_id"],
        role=row["role"],
        content=row["content"],
        actions=row["actions"],
        created_at=row["created_at"],
    )


async def append_message(
    db: Database,
    role: str,
    content: str,
    actions_json: str | None = None,
    operator_id: str = DEFAULT_OPERATOR_ID,
) -> ChatMessage:
    message = ChatMessage(
        id=str(uuid.uuid4()),
        operator_id=operator_id,
        role=role,
        content=content,
        actions=actions_json,
        created_at=_now(),
    )
    await db.execute(
        "INSERT INTO chat_messages (id, operator_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            message.id,
            message.operator_id,
            message.role,
            message.content,
            message.actions,
            message.created_at,
        ),
    )
    return message


async def get_recent_messages(
    db: Database, limit: int = 20, operator_id: str = DEFAULT_OPERATOR_ID
) -> list[ChatMessage]:
    """The last `limit` messages, oldest first — ready to replay as LLM history."""
    rows = await db.fetchall(
        "SELECT * FROM chat_messages WHERE operator_id = ? "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (operator_id, limit),
    )
    return [_row_to_message(row) for row in reversed(rows)]
