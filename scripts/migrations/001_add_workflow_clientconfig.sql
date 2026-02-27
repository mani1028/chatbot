-- Migration: add new columns to intents and create workflows + client_config tables
-- Run with sqlite3 or the provided apply_migration.py script


-- Add sector column to intents
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'intents' AND COLUMN_NAME = 'sector')
    ALTER TABLE intents ADD sector NVARCHAR(255);
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'intents' AND COLUMN_NAME = 'confidence_threshold')
    ALTER TABLE intents ADD confidence_threshold FLOAT DEFAULT 0.7;

-- Create workflows table
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'workflows')
BEGIN
    CREATE TABLE workflows (
        id INT IDENTITY(1,1) PRIMARY KEY,
        intent_id INT NOT NULL,
        function_name NVARCHAR(255) NOT NULL,
        FOREIGN KEY (intent_id) REFERENCES intents(id) ON DELETE CASCADE
    );
END;

-- Create client_config table
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'client_config')
BEGIN
    CREATE TABLE client_config (
        id INT IDENTITY(1,1) PRIMARY KEY,
        site_id INT NOT NULL,
        key NVARCHAR(255) NOT NULL,
        value NVARCHAR(MAX)
    );
END;
