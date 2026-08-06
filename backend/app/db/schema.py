"""SQLite schema definitions — mirrors database/schema.sql (PLAN.md section 7)."""

from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS operator_profile (
    id TEXT PRIMARY KEY DEFAULT 'default',
    energy_budget_kwh REAL NOT NULL DEFAULT 500.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fleet_roster (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT 'default',
    drone_id TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (operator_id, drone_id)
);

CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT 'default',
    drone_id TEXT NOT NULL,
    zone TEXT NOT NULL,
    distance_km REAL NOT NULL,
    energy_cost_kwh REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('en_route', 'delivered', 'recalled')),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mission_log (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT 'default',
    drone_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('launch', 'recall')),
    zone TEXT,
    energy_cost_kwh REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_snapshots (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT 'default',
    remaining_kwh REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_missions_drone ON missions (drone_id);
CREATE INDEX IF NOT EXISTS idx_mission_log_drone ON mission_log (drone_id);
CREATE INDEX IF NOT EXISTS idx_budget_snapshots_recorded_at ON budget_snapshots (recorded_at);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages (created_at);
"""
