# 🏗️ FALLBACK REDUCTION ARCHITECTURE

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER MESSAGE                                │
└────────────────────────────────────┬────────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   Intent Detection Engine       │
                    │  (Existing: token + embedding)  │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────────┐
                    │  Confidence & Classification       │
                    │  (HIGH / MEDIUM / LOW/UNKNOWN)     │
                    └────┬─────────────┬──────────┬───────┘
                         │             │          │
            ┌────────────▼──┐   ┌─────▼──────┐  ┌▼─────────────┐
            │   CONFIDENCE  │   │  CONFIDENCE│  │ CONFIDENCE   │
            │    >= 0.7     │   │ 0.55-0.69  │  │   < 0.55     │
            └────────┬──────┘   └─────┬──────┘  └┬─────────────┘
                     │                │         │
         ┌───────────▼──────────┐    │    ┌────▼──────────────────┐
         │  LAYER 1: BOOSTING   │    │    │  LAYER 2: THROTTLING  │
         │  Return generic      │    │    │  Check fallback freq  │
         │  "Is that right?"    │    │    │  in last 20 seconds   │
         └──────┬───────────────┘    │    └────┬──────────────────┘
                │                    │         │
         ┌──────▼───────────────────▼─────────▼──────────────────────┐
         │         LAYER 1: INTENT BOOSTING (Clarification)           │
         │                                                            │
         │  If MEDIUM confidence:                                     │
         │  - Generate intent-specific clarifying questions          │
         │  - Examples:                                               │
         │    • billing_inquiry → "Fee balance or payment options?"  │
         │    • refund_request → "Check status or start new?"        │
         │  - User selects option → New HIGH confidence message      │
         │  - Result: 40-60% reduction in fallback when combined     │
         │           with Layer 4                                     │
         └──────┬──────────────────────────────────────────────────────┘
                │
         ┌──────▼──────────────────────────────────────────────────────┐
         │      LAYER 2: CONFIDENCE THROTTLING (Prevent Storms)        │
         │                                                            │
         │  If fallback happened in last 20 seconds:                 │
         │  - Don't call LLM again                                   │
         │  - Return safe template: "Could you rephrase?"            │
         │  - Prevents cascading failures                            │
         │  - Result: 30% reduction in LLM calls                     │
         └──────┬──────────────────────────────────────────────────────┘
                │
         ┌──────▼──────────────────────────────────────────────────────┐
         │    LAYER 3: UNKNOWN LOGGING & LEARNING (Self-Training)      │
         │                                                            │
         │  When UNKNOWN occurs:                                     │
         │  - Log message to UnknownIntentLog                        │
         │  - Admin reviews top unknowns in dashboard                │
         │  - Admin maps: "what's balance?" → billing_inquiry        │
         │  - System auto-trains: adds phrase to intent_phrases      │
         │  - Result: 40-60% reduction in future fallbacks           │
         │    (once pattern is recognized)                           │
         └──────┬──────────────────────────────────────────────────────┘
                │
         ┌──────▼──────────────────────────────────────────────────────┐
         │   LAYER 4: CONFIDENCE WEIGHTING (Self-Tuning)               │
         │                                                            │
         │  Historical metrics per intent:                           │
         │  - Success rate: successful_resolutions / detections      │
         │  - Escalation rate: escalations / detections              │
         │  - User corrections: times user said "no"                 │
         │                                                            │
         │  Effective confidence = base_confidence × multiplier      │
         │                                                            │
         │  Examples:                                                 │
         │  - Intent X: 90% success → multiplier 1.1 (boost)         │
         │  - Intent Y: 30% escalation → multiplier 0.6 (reduce)     │
         │                                                            │
         │  Result: System auto-adjusts which intents to trust       │
         │          Fallback rate naturally decreases                │
         └──────┬──────────────────────────────────────────────────────┘
                │
                ▼
      ┌─────────────────────────┐
      │   RETURN RESPONSE       │
      │   + intent_name         │
      │   + response            │
      │   + confidence          │
      │   + metadata            │
      └─────────────────────────┘
```

---

## Data Flow: Admin Mapping to Self-Training

```
┌──────────────────────────────────────────────────────────────────┐
│ User says: "what's my owed amount?"                              │
│ System: No match → UNKNOWN → LLM called → Fallback logged        │
└───────────┬────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────┐
│ Admin Dashboard: Unknown Intent Manager                           │
│ Shows: "owed amount" - Asked 3 times (top unknown)               │
│ Admin: "I'll map this to billing_inquiry"                        │
└───────────┬────────────────────────────────────────────────────┘
            │
     ┌──────▼──────┐
     │   POST /admin/api/unknown/map
     │   {
     │     "unknown_log_id": 123,
     │     "intent_id": 456,
     │     "auto_train_phrases": true
     │   }
     └──────┬──────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────┐
│ FallbackOptimizer.map_unknown_to_intent()                        │
│ 1. Update unknown_log.mapped_to_intent_id = 456                  │
│ 2. Check: Does phrase already exist?                             │
│ 3. NO → Create new IntentPhrase record:                          │
│         phrase="what's my owed amount?"                          │
│         intent_id=456                                             │
│    Set: unknown_log.phrase_auto_trained=True                     │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│ Next User: "what's the owed amount?"                             │
│ Intent Engine: Matches new phrase → billing_inquiry detected     │
│ Result: HIGH CONFIDENCE → Direct answer (no fallback!)           │
│                                                                  │
│ Impact: Pattern recognized, fallback averted                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Confidence Weighting: The Self-Tuning Loop

```
           Intent Detected
                 │
      ┌──────────▼──────────┐
      │ Record Detection    │
      │ +1 to total_count   │
      └──────────┬──────────┘
                 │
       ┌─────────┴─────────┐
       │                   │
   Resolution            Escalation
       │                   │
   ┌───▼──────┐       ┌────▼────┐
   │ Success! │       │ Failed  │
   └───┬──────┘       └────┬────┘
       │                   │
   +1 success          +1 escalation
   recalc weight       recalc weight
       │                   │
   success_rate=       success_rate=
   0.9 (90%)           0.3 (30%)
       │                   │
   ┌───▼──────────┐   ┌────▼──────────┐
   │ multiplier   │   │ multiplier     │
   │ = 1.1 ↑      │   │ = 0.6 ↓        │
   │ (boost!)     │   │ (reduce)       │
   └───┬──────────┘   └────┬───────────┘
       │                   │
       ▼                   ▼
  Next detection:      Next detection:
  0.75 * 1.1 =        0.75 * 0.6 =
  0.825 (higher)      0.45 (lower)
  → More likely       → Less likely
```

---

## 4-Week Implementation Timeline

```
Week 1: Foundation
├─ Database models created ✅
├─ FallbackOptimizer service created ✅
├─ Admin API endpoints created ✅
├─ Integration guide written ✅
└─ Integrate app.py + chat_routes.py (4 hours)

Week 2: Intent Boosting + Logging
├─ Enable Layer 1 (clarifying questions)
├─ Enable Layer 2 (throttling)
├─ Admin begins reviewing unknowns
└─ Fallback: 30% → 20% expected

Week 3: Phrase Auto-Training
├─ Log 50-100 unknowns from production
├─ Admin maps top 30 to existing intents
├─ System auto-trains phrases
└─ Fallback: 20% → 15% expected

Week 4: Confidence Weighting
├─ Collect success/escalation data
├─ System fine-tunes multipliers
├─ Intents adjust confidence dynamically
└─ Fallback: 15% → 8% expected

Month 2+: Continuous Improvement
├─ Monitor metrics weekly
├─ Admin continues mapping unknowns
├─ System converges to 5% fallback
└─ LLM cost: 5× lower than baseline
```

---

## API Endpoints Summary

### Admin Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/api/unknown/unmapped` | GET | List top unknown messages |
| `/admin/api/unknown/map` | POST | Map unknown → intent |
| `/admin/api/unknown/batch-map` | POST | Bulk map unknowns |
| `/admin/api/unknown/stats` | GET | View fallback stats |
| `/admin/api/unknown/intent-metrics` | GET | View intent performance |
| `/admin/api/unknown/log/<id>` | GET | View specific unknown log |

### Feedback Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/api/feedback/success` | POST | Record intent success |
| `/admin/api/feedback/escalation` | POST | Record escalation |
| `/admin/api/feedback/correction` | POST | Record user correction |

---

## Database Schema

```
unknown_intent_logs
├─ id (PK)
├─ site_id (FK)
├─ conversation_id (FK)
├─ message (original user input)
├─ llm_response (if LLM called)
├─ fallback_type (llm / throttle / confidence)
├─ mapped_to_intent_id (FK, nullable)
├─ phrase_auto_trained (bool)
├─ created_at
├─ admin_mapped_at
└─ admin_mapped_by

confidence_throttles
├─ id (PK)
├─ site_id (FK)
├─ session_id (unique per session)
├─ fallback_count
├─ last_fallback_at
├─ window_start
├─ created_at
└─ updated_at

intent_confidence_weights
├─ id (PK)
├─ site_id (FK)
├─ intent_id (FK, unique per site)
├─ total_detections
├─ successful_resolutions
├─ escalations
├─ user_corrections
├─ success_rate (calculated)
├─ escalation_rate (calculated)
├─ confidence_multiplier (applied to base confidence)
├─ created_at
└─ last_updated
```

---

## Cost Impact Analysis

### Before Optimization

```
100 messages/day
30% fallback = 30 LLM calls
At $0.001/LLM call = $0.03/day
Monthly: $0.90
Annual: $10.80
```

### After Optimization (5% fallback)

```
100 messages/day
5% fallback = 5 LLM calls
At $0.001/LLM call = $0.005/day
Monthly: $0.15
Annual: $1.80
```

### Savings: 83% reduction in LLM costs

**For 10,000 messages/day:**
- Before: $900/month
- After: $150/month
- Savings: $750/month = $9,000/year

---

## Success Indicators

You'll know it's working when:

1. **Fallback Rate Drops**
   - Week 1: 30% → 25%
   - Week 2: 25% → 18%
   - Week 3: 18% → 10%
   - Week 4: 10% → 5%

2. **Admin Dashboard Improves**
   - Unmapped unknowns decrease
   - Mapped phrases increase
   - Coverage metric goes up

3. **Intent Confidence Weights Stabilize**
   - High performers: multiplier > 1.0
   - Low performers: multiplier < 0.8
   - System self-corrects naturally

4. **LLM Call Tracking**
   - First week: 30% reduction
   - Fourth week: 80% reduction

5. **Cost Decreases**
   - Visible in API billing
   - Per-message costs drop
   - Capacity increases without cost increase

---

## Monitoring Dashboard Essentials

Create a simple admin dashboard showing:

```
Fallback Reduction Dashboard
============================

┌─ Weekly Fallback Rate ──────────────┐
│ Week 1: 28%  ▓░░░░░░░░░░░░░░░░░░░░░ │
│ Week 2: 22%  ▓▓░░░░░░░░░░░░░░░░░░░░ │
│ Week 3: 15%  ▓▓▓░░░░░░░░░░░░░░░░░░░ │
│ Week 4: 8%   ▓▓▓▓░░░░░░░░░░░░░░░░░░ │
└─────────────────────────────────────┘

┌─ Top Unknown Messages ──────────────┐
│ "what's my balance?" - 12 times      │
│ "fees" - 8 times                    │
│ "refund status" - 6 times           │
│ "payment" - 5 times                 │
│ "not charged" - 5 times             │
└─────────────────────────────────────┘

┌─ Intent Performance ────────────────┐
│ billing_inquiry: ✓90% (mult: 1.1)   │
│ refund_request: ✓85% (mult: 1.0)   │
│ general_inquiry: ✗35% (mult: 0.5)  │
│ support_request: ✓92% (mult: 1.15) │
└─────────────────────────────────────┘

┌─ Mapping Progress ──────────────────┐
│ Total unknowns logged: 245           │
│ Mapped by admin: 201                │
│ Auto-trained phrases: 145            │
│ Coverage: 82%                        │
└─────────────────────────────────────┘
```

---

## Next Steps

1. **Integrate** (2 hours)
   - Modify 3 files (app.py, chat_routes.py, admin_api.py)
   - Run database migration

2. **Deploy** (30 min)
   - Push to staging
   - Test unmapped unknowns endpoint
   - Test mapping endpoint

3. **Monitor** (4 weeks)
   - Check fallback rate daily
   - Admin reviews unknowns weekly
   - Maps patterns as they emerge
   - Track cost reduction

4. **Iterate** (monthly)
   - Review intent performance
   - Adjust confidence thresholds
   - Optimize clarifying questions
   - Scale success patterns to other domains
