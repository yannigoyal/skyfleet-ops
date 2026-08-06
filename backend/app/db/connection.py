"""Lazy-initializing, thread-safe SQLite wrapper.

A single sqlite3.Connection (WAL mode, check_same_thread=False) guarded by
an asyncio.Lock. SQLite is single-writer regardless of how we slice it, so
serializing all access behind one lock is not a bottleneck at this scale —
and it makes multi-statement operations (see `transaction()`) trivially
atomic, which mission dispatch relies on to enforce the energy budget and
one-active-mission-per-drone rules under concurrent requests.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from .schema import SCHEMA_SQL
from .seed import seed_if_empty

T = TypeVar("T")


class Database:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._conn = conn
        return self._conn

    def ensure_initialized(self) -> None:
        """Create tables and seed default data if this is a fresh database.

        Synchronous — intended to be called once at startup before the event
        loop is serving requests, matching the "no manual migration step"
        requirement in PLAN.md section 7.
        """
        conn = self._connect()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        seed_if_empty(conn)

    async def execute(self, sql: str, params: tuple = ()) -> None:
        async with self._lock:
            await asyncio.to_thread(self._execute_sync, sql, params)

    def _execute_sync(self, sql: str, params: tuple) -> None:
        conn = self._connect()
        conn.execute(sql, params)
        conn.commit()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        async with self._lock:
            return await asyncio.to_thread(self._fetchall_sync, sql, params)

    def _fetchall_sync(self, sql: str, params: tuple) -> list[sqlite3.Row]:
        return self._connect().execute(sql, params).fetchall()

    async def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = await self.fetchall(sql, params)
        return rows[0] if rows else None

    async def transaction(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run `fn(conn)` synchronously under the write lock, inside one SQLite
        transaction. `fn` may issue multiple statements and raise to abort —
        the transaction is rolled back and the exception propagates.
        """
        async with self._lock:
            return await asyncio.to_thread(self._transaction_sync, fn)

    def _transaction_sync(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        conn = self._connect()
        try:
            result = fn(conn)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
