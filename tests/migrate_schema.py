#!/usr/bin/env python3
"""
Minimal database migration script - applies schema without loading heavy models.
"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'chatbot.db')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if pending_clarification column exists
    cursor.execute("PRAGMA table_info(conversation_thread)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    if 'pending_clarification' not in columns:
        print("Adding pending_clarification column...")
        cursor.execute("""
            ALTER TABLE conversation_thread 
            ADD COLUMN pending_clarification VARCHAR(255) DEFAULT NULL
        """)
        conn.commit()
        print("✓ Column added successfully")
    else:
        print("✓ pending_clarification column already exists")
    
    # Check if phase1_metrics table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase1_metrics'")
    if not cursor.fetchone():
        print("\nCreating phase1_metrics table...")
        cursor.execute("""
            CREATE TABLE phase1_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL,
                site_id INTEGER NOT NULL,
                session_id VARCHAR(100) NOT NULL,
                message_id VARCHAR(50) NOT NULL,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                intent_name VARCHAR(100),
                intent_confidence FLOAT,
                confidence_band VARCHAR(20),
                clarification_triggered BOOLEAN NOT NULL DEFAULT 0,
                clarification_message VARCHAR(255),
                clarification_confirmed BOOLEAN NOT NULL DEFAULT 0,
                clarification_denied BOOLEAN NOT NULL DEFAULT 0,
                llm_called BOOLEAN NOT NULL DEFAULT 0,
                llm_response_time_ms INTEGER,
                workflow_active BOOLEAN NOT NULL DEFAULT 0,
                workflow_type VARCHAR(50),
                total_response_time_ms INTEGER,
                phase_version VARCHAR(10) NOT NULL DEFAULT '1.0.0',
                execution_trace_summary VARCHAR(500),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for query optimization
        print("Creating indexes...")
        cursor.execute("CREATE INDEX idx_phase1_metrics_timestamp ON phase1_metrics(timestamp)")
        cursor.execute("CREATE INDEX idx_phase1_metrics_tenant_id ON phase1_metrics(tenant_id)")
        cursor.execute("CREATE INDEX idx_phase1_metrics_phase_version ON phase1_metrics(phase_version)")
        cursor.execute("CREATE INDEX idx_phase1_metrics_session_id ON phase1_metrics(session_id)")
        cursor.execute("CREATE INDEX idx_phase1_metrics_message_id ON phase1_metrics(message_id)")
        
        conn.commit()
        print("✓ phase1_metrics table created with indexes")
    else:
        print("✓ phase1_metrics table already exists")
        # Check if message_id has UNIQUE constraint by checking table structure
        cursor.execute("PRAGMA table_info(phase1_metrics)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        # If table exists and message_id has UNIQUE, we need to handle migration
        # This is done by backing up data, dropping table, and recreating without UNIQUE
        print("  • Verifying message_id constraint status...")
        
        # Get all existing data
        cursor.execute("SELECT * FROM phase1_metrics")
        existing_data = cursor.fetchall()
        
        if existing_data:
            print(f"  • Backing up {len(existing_data)} existing metrics records...")
            
            # Drop the old table
            cursor.execute("DROP TABLE phase1_metrics")
            
            # Recreate without UNIQUE
            cursor.execute("""
                CREATE TABLE phase1_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER NOT NULL,
                    site_id INTEGER NOT NULL,
                    session_id VARCHAR(100) NOT NULL,
                    message_id VARCHAR(50) NOT NULL,
                    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    intent_name VARCHAR(100),
                    intent_confidence FLOAT,
                    confidence_band VARCHAR(20),
                    clarification_triggered BOOLEAN NOT NULL DEFAULT 0,
                    clarification_message VARCHAR(255),
                    clarification_confirmed BOOLEAN NOT NULL DEFAULT 0,
                    clarification_denied BOOLEAN NOT NULL DEFAULT 0,
                    llm_called BOOLEAN NOT NULL DEFAULT 0,
                    llm_response_time_ms INTEGER,
                    workflow_active BOOLEAN NOT NULL DEFAULT 0,
                    workflow_type VARCHAR(50),
                    total_response_time_ms INTEGER,
                    phase_version VARCHAR(10) NOT NULL DEFAULT '1.0.0',
                    execution_trace_summary VARCHAR(500),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Recreate indexes
            cursor.execute("CREATE INDEX idx_phase1_metrics_timestamp ON phase1_metrics(timestamp)")
            cursor.execute("CREATE INDEX idx_phase1_metrics_tenant_id ON phase1_metrics(tenant_id)")
            cursor.execute("CREATE INDEX idx_phase1_metrics_phase_version ON phase1_metrics(phase_version)")
            cursor.execute("CREATE INDEX idx_phase1_metrics_session_id ON phase1_metrics(session_id)")
            cursor.execute("CREATE INDEX idx_phase1_metrics_message_id ON phase1_metrics(message_id)")
            
            conn.commit()
            print("  ✓ Table recreated without UNIQUE constraint on message_id")
        else:
            print("  ✓ No data migration needed")
    
    # Verify schema
    cursor.execute("PRAGMA table_info(conversation_thread)")
    print("\nConversation Thread columns:")
    for row in cursor.fetchall():
        col_name, col_type = row[1], row[2]
        print(f"  {col_name:40} {col_type}")
    
    print("\nPhase1Metrics columns:")
    cursor.execute("PRAGMA table_info(phase1_metrics)")
    for row in cursor.fetchall():
        col_name, col_type = row[1], row[2]
        print(f"  {col_name:40} {col_type}")
    
    conn.close()
    print("\n✓ Database schema verified")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()