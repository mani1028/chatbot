#!/usr/bin/env python3
"""
Phase 1 Synthetic Simulation - 1000 Messages with Weighted Distribution

Generates realistic Phase 1 metrics data to validate analytics infrastructure
and measure impact before Phase 2 decisions.

Distribution Strategy:
- 40% HIGH confidence (>0.8) → no clarification
- 35% LOW confidence (<0.55) → no clarification  
- 25% MID confidence (0.55-0.8) → clarification triggered
  - Of triggered: 60% confirmed, 40% denied
- 10% with workflow active (prevents clarification)
- 5-10% concurrent batches (20 parallel each)
"""

import sqlite3
import uuid
import random
import time
from datetime import datetime, timedelta
import json
import os

db_path = os.path.join(os.path.dirname(__file__), 'instance', 'chatbot.db')

# Configuration
TOTAL_MESSAGES = 1000
TENANT_ID = 1
SITE_ID = 1
DEFAULT_SESSION_ID = str(uuid.uuid4())

# Distribution weights
CONFIDENCE_DISTRIBUTION = {
    'HIGH': 0.40,      # >0.8, no clarification needed
    'LOW': 0.35,       # <0.55, no clarification possible
    'MID': 0.25        # 0.55-0.8, triggers clarification
}

# Clarification outcomes (for MID confidence)
CLARIFICATION_OUTCOMES = {
    'confirmed': 0.60,
    'denied': 0.40
}

# Workflow interference
WORKFLOW_ACTIVE_RATE = 0.10
CONCURRENT_BATCH_SIZE = 20
CONCURRENT_BATCH_RATE = 0.08  # 8% of messages are concurrent

# Intent names for simulation
INTENT_NAMES = [
    'order_inquiry', 'billing_question', 'account_access', 
    'product_feature', 'complaint', 'scheduling', 'refund_request',
    'technical_support', 'subscription_change', 'general_inquiry'
]


def generate_confidence():
    """Generate confidence score based on weighted distribution."""
    roll = random.random()
    
    if roll < CONFIDENCE_DISTRIBUTION['HIGH']:
        return random.uniform(0.80, 1.0), 'HIGH'
    elif roll < CONFIDENCE_DISTRIBUTION['HIGH'] + CONFIDENCE_DISTRIBUTION['LOW']:
        return random.uniform(0.0, 0.55), 'LOW'
    else:
        return random.uniform(0.55, 0.80), 'MID'


def should_trigger_clarification(confidence_band, workflow_active):
    """Determine if clarification should be triggered."""
    # Only MID band triggers clarification, and only if no workflow active
    if confidence_band == 'MID' and not workflow_active:
        return True
    return False


def get_clarification_outcome():
    """Get confirmation/denial outcome for triggered clarification."""
    return 'confirmed' if random.random() < CLARIFICATION_OUTCOMES['confirmed'] else 'denied'


def create_metrics_record(message_index, session_id, confidence, confidence_band, 
                         intent_name, workflow_active, llm_called, 
                         clarification_triggered, clarification_outcome=None):
    """Create a single Phase1Metrics record."""
    
    # Simulate response timing
    if llm_called:
        llm_response_time_ms = random.randint(500, 2000)
        total_response_time_ms = random.randint(600, 2100)
    else:
        llm_response_time_ms = None
        total_response_time_ms = random.randint(50, 300)
    
    timestamp = datetime.utcnow() - timedelta(
        seconds=random.randint(0, 3600)  # Last hour
    )
    
    return {
        'tenant_id': TENANT_ID,
        'site_id': SITE_ID,
        'session_id': session_id,
        'message_id': str(uuid.uuid4()),
        'timestamp': timestamp.isoformat(),
        'intent_name': intent_name,
        'intent_confidence': confidence,
        'confidence_band': confidence_band,
        'clarification_triggered': clarification_triggered,
        'clarification_message': f"Did you mean '{intent_name.replace('_', ' ').title()}'?" if clarification_triggered else None,
        'clarification_confirmed': clarification_outcome == 'confirmed' if clarification_triggered else False,
        'clarification_denied': clarification_outcome == 'denied' if clarification_triggered else False,
        'llm_called': llm_called,
        'llm_response_time_ms': llm_response_time_ms,
        'workflow_active': workflow_active,
        'workflow_type': 'order_workflow' if workflow_active else None,
        'total_response_time_ms': total_response_time_ms,
        'phase_version': '1.0.0',
        'execution_trace_summary': 'intent_detected → ' + ('clarification_band_triggered' if clarification_triggered else 'intent_confirmed')
    }


def insert_metrics_batch(cursor, records):
    """Batch insert metrics records."""
    insert_sql = """
    INSERT INTO phase1_metrics (
        tenant_id, site_id, session_id, message_id, timestamp,
        intent_name, intent_confidence, confidence_band,
        clarification_triggered, clarification_message,
        clarification_confirmed, clarification_denied,
        llm_called, llm_response_time_ms,
        workflow_active, workflow_type, total_response_time_ms,
        phase_version, execution_trace_summary, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    for record in records:
        cursor.execute(insert_sql, (
            record['tenant_id'],
            record['site_id'],
            record['session_id'],
            record['message_id'],
            record['timestamp'],
            record['intent_name'],
            record['intent_confidence'],
            record['confidence_band'],
            record['clarification_triggered'],
            record['clarification_message'],
            record['clarification_confirmed'],
            record['clarification_denied'],
            record['llm_called'],
            record['llm_response_time_ms'],
            record['workflow_active'],
            record['workflow_type'],
            record['total_response_time_ms'],
            record['phase_version'],
            record['execution_trace_summary'],
            datetime.utcnow().isoformat()
        ))


def run_simulation():
    """Run 1000-message simulation with weighted distribution."""
    print("=" * 80)
    print("PHASE 1 ANALYTICS SIMULATION - 1000 Messages")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Clear existing data (for clean runs)
        cursor.execute("DELETE FROM phase1_metrics WHERE phase_version = '1.0.0'")
        conn.commit()
        print("\n✓ Cleared existing simulation data")
        
        # Statistics tracking
        stats = {
            'total': 0,
            'high_confidence': 0,
            'low_confidence': 0,
            'mid_confidence': 0,
            'clarification_triggered': 0,
            'clarification_confirmed': 0,
            'clarification_denied': 0,
            'llm_called': 0,
            'workflow_active': 0,
            'total_response_time_ms': 0,
            'total_llm_response_time_ms': 0,
            'non_clarification_with_llm': 0
        }
        
        # Generate messages in batches
        batch_records = []
        batch_size = 50
        
        print(f"\nGenerating {TOTAL_MESSAGES} synthetic messages...")
        print("Distribution: 40% HIGH, 35% LOW, 25% MID")
        print("Clarification rate: ~25% (only MID band without workflow)")
        
        for msg_index in range(TOTAL_MESSAGES):
            # Create new session every 50 messages to simulate different users
            if msg_index % 50 == 0:
                session_id = str(uuid.uuid4())
            
            # Generate intent and confidence
            confidence, confidence_band = generate_confidence()
            intent_name = random.choice(INTENT_NAMES)
            
            # Determine workflow state
            workflow_active = random.random() < WORKFLOW_ACTIVE_RATE
            
            # Determine clarification
            clarification_triggered = should_trigger_clarification(confidence_band, workflow_active)
            clarification_outcome = get_clarification_outcome() if clarification_triggered else None
            
            # Determine if LLM should be called
            # LLM is called for LOW confidence OR if clarification is denied
            llm_called = (confidence_band == 'LOW' or 
                         (clarification_triggered and clarification_outcome == 'denied'))
            
            # Create record
            record = create_metrics_record(
                msg_index,
                session_id,
                confidence,
                confidence_band,
                intent_name,
                workflow_active,
                llm_called,
                clarification_triggered,
                clarification_outcome
            )
            
            batch_records.append(record)
            
            # Update stats
            stats['total'] += 1
            if confidence_band == 'HIGH':
                stats['high_confidence'] += 1
            elif confidence_band == 'LOW':
                stats['low_confidence'] += 1
                stats['llm_called'] += 1
            else:
                stats['mid_confidence'] += 1
            
            if workflow_active:
                stats['workflow_active'] += 1
            
            if clarification_triggered:
                stats['clarification_triggered'] += 1
                if clarification_outcome == 'confirmed':
                    stats['clarification_confirmed'] += 1
                else:
                    stats['clarification_denied'] += 1
                    stats['llm_called'] += 1
            elif confidence_band != 'LOW':
                if llm_called:
                    stats['non_clarification_with_llm'] += 1
                    stats['llm_called'] += 1
            
            stats['total_response_time_ms'] += record['total_response_time_ms']
            if record['llm_response_time_ms']:
                stats['total_llm_response_time_ms'] += record['llm_response_time_ms']
            
            # Batch insert
            if len(batch_records) >= batch_size:
                insert_metrics_batch(cursor, batch_records)
                conn.commit()
                print(f"  ✓ Inserted {msg_index + 1}/{TOTAL_MESSAGES} messages", end='\r')
                batch_records = []
        
        # Insert remaining records
        if batch_records:
            insert_metrics_batch(cursor, batch_records)
            conn.commit()
        
        print(f"  ✓ Inserted {TOTAL_MESSAGES}/{TOTAL_MESSAGES} messages           ")
        
        # Generate analytics
        print("\n" + "=" * 80)
        print("PHASE 1 ANALYTICS RESULTS")
        print("=" * 80)
        
        # Query calculated metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(CASE WHEN confidence_band = 'HIGH' THEN 1 END) as high_conf,
                COUNT(CASE WHEN confidence_band = 'MID' THEN 1 END) as mid_conf,
                COUNT(CASE WHEN confidence_band = 'LOW' THEN 1 END) as low_conf,
                COUNT(CASE WHEN clarification_triggered THEN 1 END) as clarification_count,
                COUNT(CASE WHEN clarification_confirmed THEN 1 END) as confirmed_count,
                COUNT(CASE WHEN clarification_denied THEN 1 END) as denied_count,
                COUNT(CASE WHEN llm_called THEN 1 END) as llm_count,
                COUNT(CASE WHEN workflow_active THEN 1 END) as workflow_count,
                ROUND(AVG(total_response_time_ms), 2) as avg_response_ms,
                ROUND(AVG(CASE WHEN llm_called THEN llm_response_time_ms END), 2) as avg_llm_ms
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
        """)
        
        result = cursor.fetchone()
        total, high, mid, low, clarif, confirmed, denied, llm_count, workflows, avg_response, avg_llm = result
        
        # Calculate KPIs
        trigger_rate = (clarif / total * 100) if total > 0 else 0
        confirmation_rate = (confirmed / clarif * 100) if clarif > 0 else 0
        llm_reduction = ((total - llm_count) / total * 100) if total > 0 else 0
        
        # Output results
        print("\nKEY PERFORMANCE INDICATORS:")
        print(f"  Clarification Trigger Rate:  {trigger_rate:6.2f}% ({clarif}/{total} messages)")
        print(f"  Confirmation Rate:            {confirmation_rate:6.2f}% ({confirmed}/{clarif} triggered)")
        print(f"  Denial Rate:                  {100-confirmation_rate:6.2f}% ({denied}/{clarif} triggered)")
        print(f"  LLM Reduction:                {llm_reduction:6.2f}% ({total - llm_count} avoided)")
        
        print("\nCONFIDENCE BAND DISTRIBUTION:")
        print(f"  HIGH (>0.80):                 {high:4d} ({high/total*100:5.1f}%)")
        print(f"  MID  (0.55-0.80):             {mid:4d} ({mid/total*100:5.1f}%)")
        print(f"  LOW  (<0.55):                 {low:4d} ({low/total*100:5.1f}%)")
        
        print("\nPERFORMANCE METRICS:")
        print(f"  Avg Response Time (all):      {avg_response:8.2f} ms")
        print(f"  Avg LLM Response Time:        {avg_llm:8.2f} ms")
        print(f"  Workflow Active:              {workflows:4d} ({workflows/total*100:5.1f}%)")
        
        print("\nPHASE 2 READINESS ASSESSMENT:")
        print("-" * 80)
        
        # Readiness checks
        checks = []
        
        if trigger_rate < 5:
            checks.append("❌ TRIGGER RATE TOO LOW (<5%) - Model too confident")
        elif trigger_rate > 40:
            checks.append("❌ TRIGGER RATE TOO HIGH (>40%) - Model too weak")
        else:
            checks.append("✅ TRIGGER RATE OPTIMAL (5-40%)")
        
        if confirmation_rate < 40:
            checks.append("❌ CONFIRMATION RATE TOO LOW (<40%) - UX needs improvement")
        else:
            checks.append("✅ CONFIRMATION RATE HEALTHY (>40%)")
        
        if llm_reduction < 20:
            checks.append("⚠️  LLM REDUCTION LOW (<20%) - Phase 1 impact limited")
        else:
            checks.append("✅ LLM REDUCTION SIGNIFICANT (>20%)")
        
        for check in checks:
            print(f"  {check}")
        
        print("\nRECOMMENDED NEXT STEPS:")
        print("-" * 80)
        
        if trigger_rate < 5:
            print("  1. Increase confidence band range (0.50-0.80)")
            print("  2. Train intent model on edge cases")
            print("  3. Re-run simulation and re-evaluate")
        elif trigger_rate > 40:
            print("  1. Decrease confidence band range (0.60-0.75)")
            print("  2. Improve intent detection training")
            print("  3. Re-run simulation and re-evaluate")
        else:
            print("  1. Phase 1 parameters are optimal")
            print("  2. Proceed to Phase 2 cost-aware tuning")
            print("  3. Track real-world confirmation rates in production")
        
        if confirmation_rate < 40:
            print("  •  Improve clarification message clarity")
            print("  •  Test UX variations (question phrasing)")
            print("  •  Gather user feedback sessions")
        
        if llm_reduction < 20:
            print("  •  Schedule Phase 2 memory boosting strategy")
            print("  •  Implement confidence auto-tuning")
        
        # Export summary to CSV
        csv_path = 'phase1_metrics_export.csv'
        cursor.execute("""
            SELECT 
                message_id, timestamp, intent_name, intent_confidence, confidence_band,
                clarification_triggered, clarification_confirmed, clarification_denied,
                llm_called, llm_response_time_ms, workflow_active,
                total_response_time_ms, phase_version
            FROM phase1_metrics
            WHERE phase_version = '1.0.0'
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        print(f"\n✓ Exported sample to {csv_path}")
        
        conn.close()
        print("\n" + "=" * 80)
        print("Simulation Complete")
        print("=" * 80)
        
    except Exception as e:
        print(f"✗ Simulation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_simulation()
