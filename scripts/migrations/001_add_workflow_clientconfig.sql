-- Migration: add new columns to intents and create workflows + client_config tables
-- Run with sqlite3 or the provided apply_migration.py script

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- Add sector column to intents (if not exists). SQLite supports ADD COLUMN.
ALTER TABLE intents ADD COLUMN sector TEXT;
ALTER TABLE intents ADD COLUMN confidence_threshold FLOAT DEFAULT 0.7;

-- Create workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    intent_id INTEGER NOT NULL,
    function_name TEXT NOT NULL,
    FOREIGN KEY(intent_id) REFERENCES intents(id) ON DELETE CASCADE
);

-- Create client_config table
CREATE TABLE IF NOT EXISTS client_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    key TEXT NOT NULL,
    value TEXT
);

COMMIT;
PRAGMA foreign_keys=ON;
