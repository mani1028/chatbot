# 🔌 FALLBACK REDUCTION INTEGRATION GUIDE

## Overview

This guide shows how to integrate the fallback reduction optimization into your existing intent detection flow.

**New Components:**
- `FallbackOptimizer` - Core orchestration
- `PhraseExpansion` - Auto-training
- Admin API routes - Unknown management

---

## Step 1: Register Admin API Blueprint

**File:** `app.py`

Add these lines in `create_app()`:

```python
# At top with other imports
from routes.unknown_intent_admin import unknown_intent_bp

# In create_app() after other blueprints
app.register_blueprint(unknown_intent_bp)
```

This exposes:
- `GET /admin/api/unknown/unmapped` - List unknowns
- `POST /admin/api/unknown/map` - Map unknown to intent
- `GET /admin/api/unknown/stats` - View fallback stats
- `GET /admin/api/unknown/intent-metrics` - Intent performance

---

## Step 2: Integrate Into Intent Detection Flow

The integration point is in your chat route handler. This is typically in `routes/chat_routes.py`

**Current flow:**

```python
def process_message(user_message, site_id):
    # Detect intent
    intent_result = detect_intent(user_message, site_id)
    
    # If UNKNOWN, call LLM
    if intent_result['intent_name'] == 'UNKNOWN':
        llm_response = call_llm(user_message)
        return llm_response
    
    return intent_result['response']
```

**Optimized flow:**

```python
from services.fallback_optimizer import get_optimizer
from core.phrase_expansion import PhraseExpansion

def process_message(user_message, site_id, session_id, conversation_id=None):
    optimizer = get_optimizer()
    
    # STEP 1: Detect intent
    intent_result = detect_intent(user_message, site_id)
    confidence = intent_result['confidence']
    
    # STEP 2: MEDIUM CONFIDENCE → Try Clarifying Questions (Intent Boosting)
    if intent_result.get('intent_name') != 'UNKNOWN':
        # Check confidence classification
        from config import classify_confidence
        conf_class = classify_confidence(confidence)
        
        if conf_class == 'MEDIUM':
            # Try intent-specific clarification
            intent = Intent.query.get(intent_result['intent_id'])
            clarifying_q = optimizer.generate_clarifying_questions(
                intent,
                user_message,
                site_id
            )
            
            if clarifying_q:
                # Return clarifying question instead of generic suggestion
                return {
                    'intent_name': intent_result['intent_name'],
                    'response': clarifying_q,
                    'is_clarification': True
                }
    
    # STEP 3: LOW CONFIDENCE or UNKNOWN → Check Throttle
    if intent_result['intent_name'] == 'UNKNOWN' or confidence < 0.55:
        should_throttle, reason = optimizer.should_throttle_fallback(
            site_id,
            session_id,
            confidence
        )
        
        if should_throttle:
            # Return safe template (saves LLM call)
            return {
                'intent_name': 'UNKNOWN',
                'response': "I'm having trouble understanding. Could you rephrase or be more specific?",
                'confidence': confidence,
                'throttled': True
            }
    
    # STEP 4: UNKNOWN → Apply Confidence Weighting, then LLM
    if intent_result['intent_name'] == 'UNKNOWN':
        # Log unknown for admin mapping
        unknown_log = optimizer.record_fallback_event(
            site_id,
            session_id,
            user_message,
            fallback_type='llm'
        )
        
        # Call LLM and store response
        llm_response = call_llm(user_message)
        unknown_log.llm_response = llm_response
        db.session.commit()
        
        return {
            'intent_name': 'UNKNOWN',
            'response': llm_response,
            'confidence': 0.0,
            'unknown_log_id': unknown_log.id
        }
    
    # STEP 5: HIGH CONFIDENCE → Apply Weighting, Execute
    intent = Intent.query.get(intent_result.get('intent_id'))
    if intent:
        # Apply confidence weighting based on success history
        effective_confidence = optimizer.get_effective_confidence(
            intent,
            confidence,
            site_id
        )
        
        # Record detection for metrics
        weight = IntentConfidenceWeight.get_or_create(site_id, intent.id)
        weight.record_detection()
        db.session.commit()
        
        return {
            'intent_name': intent_result['intent_name'],
            'response': intent_result['response'],
            'confidence': effective_confidence,
            'intent_id': intent.id
        }
    
    # Fallback
    unknown_log = optimizer.record_fallback_event(
        site_id,
        session_id,
        user_message,
        fallback_type='confidence'
    )
    return {
        'intent_name': 'UNKNOWN',
        'response': random.choice(FALLBACK_MESSAGES),
        'confidence': confidence
    }
```

---

## Step 3: Track Intent Outcomes

When an intent leads to a successful resolution or escalation, record it:

**On Success:**

```python
@app.route('/api/feedback/success', methods=['POST'])
def record_intent_success():
    data = request.get_json()
    intent_id = data.get('intent_id')
    site_id = data.get('site_id')
    
    optimizer = get_optimizer()
    optimizer.record_intent_success(intent_id, site_id)
    
    return jsonify({'success': True})
```

**On Escalation:**

```python
@app.route('/api/feedback/escalation', methods=['POST'])
def record_escalation():
    data = request.get_json()
    intent_id = data.get('intent_id')
    site_id = data.get('site_id')
    
    optimizer = get_optimizer()
    optimizer.record_intent_escalation(intent_id, site_id)
    
    return jsonify({'success': True})
```

**On User Correction:**

When user says "No" to clarification question:

```python
@app.route('/api/feedback/correction', methods=['POST'])
def record_user_correction():
    data = request.get_json()
    intent_id = data.get('intent_id')  # The intent that was corrected
    site_id = data.get('site_id')
    
    optimizer = get_optimizer()
    optimizer.record_user_correction(intent_id, site_id)
    
    return jsonify({'success': True})
```

---

## Step 4: Admin Dashboard Integration

### Display Unmapped Unknowns

```javascript
// Fetch top unknown messages
fetch('/admin/api/unknown/unmapped?limit=20', {
    headers: {
        'X-Admin-ID': adminId
    }
})
.then(r => r.json())
.then(data => {
    // Display data.unknowns
    // Each has: message, count, sample_log_id
});
```

### Admin Maps Unknown → Intent

```javascript
// Admin clicks to map "what's my balance?" to billing_inquiry
fetch('/admin/api/unknown/map', {
    method: 'POST',
    headers: {
        'X-Admin-ID': adminId,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        unknown_log_id: 123,
        intent_id: 456,
        auto_train_phrases: true
    })
})
.then(r => r.json())
.then(data => {
    if (data.success) {
        alert('Mapped and trained! System will now recognize this message.');
    }
});
```

### View Fallback Statistics

```javascript
fetch('/admin/api/unknown/stats', {
    headers: { 'X-Admin-ID': adminId }
})
.then(r => r.json())
.then(data => {
    // data.stats = {
    //     total_fallbacks: 150,
    //     mapped_count: 130,
    //     coverage: 0.867,
    //     by_type: { llm: 100, throttle: 30, ... }
    // }
});
```

### View Intent Performance Metrics

```javascript
fetch('/admin/api/unknown/intent-metrics', {
    headers: { 'X-Admin-ID': adminId }
})
.then(r => r.json())
.then(data => {
    // data.metrics = [
    //     {
    //         intent_id: 1,
    //         total_detections: 50,
    //         success_rate: 0.92,
    //         confidence_multiplier: 1.1
    //     },
    //     ...
    // ]
});
```

---

## Step 5: Create Database Migrations

Run these in your app context:

```python
python
>>> from app import app
>>> from database import db
>>> from models import UnknownIntentLog, ConfidenceThrottle, IntentConfidenceWeight
>>> 
>>> with app.app_context():
...     db.create_all()
...     print("Tables created!")
```

Or create explicit migration files if using Flask-Migrate.

---

## Implementation Checklist

- [ ] Add new models to `models/__init__.py` (already done)
- [ ] Register unknown_intent_bp in `app.py`
- [ ] Update chat route handler with optimization flow
- [ ] Add success/escalation feedback endpoints
- [ ] Create admin UI to view unmapped unknowns
- [ ] Create database tables
- [ ] Test with sample messages
- [ ] Monitor fallback rate over 2 weeks

---

## Expected Outcomes (4 Week Timeline)

**Week 1:** Intent Boosting + Logging
- Fallback rate: 30% → 20%
- LLM calls: -25%

**Week 2:** Phrase Auto-Training begins
- Fallback rate: 20% → 15%
- LLM calls: -35% from baseline

**Week 3:** Throttling + Confidence Weighting
- Fallback rate: 15% → 8%
- LLM calls: -60% from baseline

**Week 4:** System self-tunes
- Fallback rate: 8% → 5%
- LLM calls: -80% from baseline
- System cost: 5× lower than today

---

## Debugging

### Check throttle status for a session

```python
from models import ConfidenceThrottle
throttle = ConfidenceThrottle.query.filter_by(
    site_id=1,
    session_id='session123'
).first()
print(f"Fallbacks in window: {throttle.fallback_count}")
```

### View unmapped unknowns

```python
from models import UnknownIntentLog
unmapped = UnknownIntentLog.query.filter(
    UnknownIntentLog.site_id == 1,
    UnknownIntentLog.mapped_to_intent_id == None
).all()
for u in unmapped:
    print(f"{u.message} - asked {UnknownIntentLog.query.filter_by(message=u.message).count()} times")
```

### Check intent confidence weight

```python
from models import IntentConfidenceWeight
weight = IntentConfidenceWeight.query.filter_by(
    site_id=1,
    intent_id=5
).first()
print(f"Success rate: {weight.success_rate}")
print(f"Confidence multiplier: {weight.confidence_multiplier}")
```
