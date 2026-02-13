-- Migration: add plan limits columns
-- Run with: python scripts/apply_migration.py scripts/migrations/002_add_plan_limits.sql

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

ALTER TABLE plans ADD COLUMN max_intents INTEGER DEFAULT 50;
ALTER TABLE plans ADD COLUMN max_monthly_chats INTEGER DEFAULT 1000;

COMMIT;
PRAGMA foreign_keys=ON;
