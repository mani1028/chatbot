-- Migration: add plans.is_active column
-- Run with: python scripts/apply_migration.py scripts/migrations/003_add_plan_is_active.sql

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

ALTER TABLE plans ADD COLUMN is_active INTEGER DEFAULT 1;

COMMIT;
PRAGMA foreign_keys=ON;
