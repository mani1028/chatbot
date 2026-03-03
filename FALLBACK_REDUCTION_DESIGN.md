# 🎯 FALLBACK RATE REDUCTION OPTIMIZATION PLAN

## Current State
- Fallback rate: ~30%
- Triggers: Messages land in UNKNOWN classification
- Cost impact: Every fallback = LLM call
- Capacity: LLM bottleneck under concurrency

---

## Strategy: 4-Layer Optimization

### Layer 1: Intent Boosting (Clarification Questions)
**When:** Confidence 0.55–0.7 (currently returns "I think you're asking...")
**Action:** Smarter clarifying questions specific to the ambiguous context

```python
# Current behavior:
"I think you're asking about billing_inquiry. Is that right?"

# Optimized behavior:
"Did you want to know about:
  1. Invoice details?
  2. Payment options?
  3. Fee structure?"
```

### Layer 2: Phrase Auto-Training (Admin Mapping)
**When:** Admin maps UNKNOWN → existing intent
**Action:** Auto-append phrase to intent_phrases table

```python
Admin action:
  User said: "what's my owed amount"
  Admin maps to: billing_inquiry
  System auto-adds: "owed amount" to billing_inquiry phrases

Result:
  Next time user says "owed amount" → detected directly, no LLM
```

### Layer 3: Fallback Throttling (Prevent Storms)
**When:** Same session triggers fallback in last 20 seconds
**Action:** Return safe template instead of calling LLM again

```python
Session fallback count in last 20 seconds: 2
Next message low confidence? 
  → Don't call LLM
  → Return: "I'm having trouble understanding. Could you rephrase?"
```

### Layer 4: Confidence Threshold Tuning (Per-Intent)
**When:** Intent has low success rate historically
**Action:** Reduce its triggering confidence, requiring more explicit match

```python
Intent: billing_inquiry
  Base confidence: 0.8
  Success weight: 0.7 (70% of escalations resolved within this intent)
  Effective threshold: 0.8 × 0.7 = 0.56

Intent: refund_request
  Base confidence: 0.8
  Success weight: 0.5 (50% fail - customer frustrated)
  Effective threshold: 0.8 × 0.5 = 0.40 → raises to 0.75
```

---

## Expected Impact

| Phase | Change | Fallback Rate | LLM Calls |
|-------|--------|---------------|-----------|
| Current | Baseline | 30% | 100% |
| Layer 1 | Intent Boosting | 20% | 67% |
| Layer 2 | Phrase Auto-Training (2 weeks) | 15% | 50% |
| Layer 3 | Throttling + Weighting | 8% | 27% |
| Target | Full Optimization | 5% | 20% |

---

## Implementation Order

### Week 1: Model Creation + Logging
- [ ] `UnknownIntentLog` table
- [ ] `ConfidenceThrottle` table
- [ ] `IntentConfidenceWeight` table
- [ ] Update intent_engine to log unknowns + throttle

### Week 1: Intent Boosting Layer
- [ ] `FallbackOptimizer.generate_clarifying_questions()`
- [ ] Modify MEDIUM confidence response
- [ ] Add context-aware question generation

### Week 2: Phrase Auto-Training
- [ ] Admin API endpoint: `/admin/api/unknown/map`
- [ ] Auto-append logic to IntentPhrase
- [ ] Track "newly trained phrases"

### Week 2: Throttling + Weighting
- [ ] Session-level throttle check
- [ ] Intent success weight calculation
- [ ] Effective confidence scoring

---

## Database Schema

### Table 1: UnknownIntentLog
```sql
unknown_intent_logs:
  id (PK)
  site_id (FK)
  message (original user input)
  llm_response (if called)
  mapped_to_intent (nullable - when admin maps it)
  created_at
  admin_mapped_at (nullable)
```

### Table 2: ConfidenceThrottle
```sql
confidence_throttles:
  id (PK)
  conversation_id (FK)
  fallback_count (in last 20 seconds)
  last_fallback_at
  site_id
```

### Table 3: IntentConfidenceWeight
```sql
intent_confidence_weights:
  id (PK)
  intent_id (FK)
  success_rate (0.0-1.0)
  escalation_count
  successful_resolution_count
  last_updated
```

---

## Code Components To Create

1. **models/unknown_intent_log.py** - Data model
2. **models/confidence_throttle.py** - Session throttle tracking
3. **models/intent_confidence_weight.py** - Success metrics
4. **services/fallback_optimizer.py** - Core optimization engine
5. **routes/unknown_intent_admin.py** - Admin mapping API
6. **core/phrase_expansion.py** - Auto-training logic

---

## Success Metrics

- Fallback rate drops to <8% (from 30%)
- LLM calls reduce by 3-4×
- Admin time investment: ~30 min/week initial, then 10 min/week
- Cumulative time to 5% fallback: ~4 weeks
