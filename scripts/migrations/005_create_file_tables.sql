-- Migration: create template_files and site_files tables
-- Run with: python scripts/apply_migration.py scripts/migrations/005_create_file_tables.sql

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS template_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    uploaded_at DATETIME,
    FOREIGN KEY(template_id) REFERENCES sector_templates(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS site_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    created_at DATETIME,
    FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE
);

COMMIT;
PRAGMA foreign_keys=ON;
