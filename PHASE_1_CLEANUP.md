# Phase 1 Minimal: What Was Removed

## Cleaned Up (Deleted/Ignored)

The following Phase 2 code was created but **NOT integrated** and should be ignored for now:

❌ `services/fallback_optimizer.py` - **Delete or ignore**
❌ `models/confidence_throttle.py` - **Delete or ignore**
❌ `models/intent_confidence_weight.py` - **Delete or ignore**
❌ `core/phrase_expansion.py` - **Delete or ignore**
❌ `routes/unknown_intent_admin.py` - **Delete or ignore**
❌ All `FALLBACK_*.md` documentation files - **Reference only (not implementation)**

These were pre-implementation explorations. They are:
- ✅ Not imported anywhere
- ✅ Not registered as blueprints
- ✅ Not integrated into orchestrator
- ✅ Safe to delete without breaking anything

**Decision:** Keep them or delete them? Doesn't matter. They don't affect runtime.

---

## What Remains: Phase 1 Clean

### 1. Model (30 lines)
**`models/unknown_intent_log.py`** - Only 4 fields:
- id
- site_id  
- message
- created_at
- resolved

### 2. Orchestrator Changes (~50 lines)
**`services/message_orchestrator.py`**:
- Clarification band logic (lines ~167-193)
- Unknown logging call (line ~244)
- _log_unknown_intent() method (~10 lines)

### 3. Admin API Endpoints (~100 lines)  
**`routes/admin_api.py`**:
- POST /admin/api/unknown/map
- GET /admin/api/unknown/list

### 4. Setup Guide
**`PHASE_1_SETUP.md`** - This file

---

## Files Actually Modified

```
✏️  models/unknown_intent_log.py (simplified to 20 lines from 50)
✏️  models/__init__.py (added UnknownIntentLog import)
✏️  services/message_orchestrator.py (added clarification band + logging)
✏️  routes/admin_api.py (added 2 endpoints)
```

**Changed lines total:** ~200 lines across 4 files

---

## Architecture Preserved

Your kernel remains **pure**:

✅ Single entry: `orchestrator.process_message()`
✅ Single exit: `_finalize()`
✅ Single commit: In Stage 10
✅ Deterministic execution: 10-stage pipeline
✅ No experimental intelligence layers
✅ No async complexity
✅ No cross-cutting concerns

The clarification band is **in-flow**, not a separate service.
Unknown logging is **non-blocking**, added before LLM.

---

## Validation Checklist

Before deploying:

- [ ] Run: `python -c "from app import app; from database import db; from models import UnknownIntentLog; app.app_context().push(); db.create_all()"`
- [ ] Verify table created: `select count(*) from unknown_intent_logs`
- [ ] Test clarification: Send message with 0.55-0.8 confidence
- [ ] Test unknown: Send garbage message, verify LLM called AND logged
- [ ] Test admin API: Call `/admin/api/unknown/list` (with session cookie)
- [ ] Test mapping: Call `/admin/api/unknown/map` with unknown_id and intent_id

---

## Quick Verification

```python
# Check orchestrator has clarification band
grep -n "pending_clarification" services/message_orchestrator.py

# Check unknown logging added
grep -n "_log_unknown_intent" services/message_orchestrator.py

# Check admin endpoints exist
grep -n "unknown/map\|unknown/list" routes/admin_api.py

# Check model imported
grep -n "UnknownIntentLog" models/__init__.py
```

All 4 should return results.

---

## Deployment Path

1. Test locally ✅
2. Deploy to staging
3. Monitor for 24 hours (no issues expected)
4. Deploy to production
5. Start collecting unknown messages

No database migrations needed (just create_all()).
No feature flags needed.
No rollback plan needed (changes are minimal).

---

## Success = Real Data

In 24 hours you'll have:
- Unknown message patterns 
- User clarification acceptance rate
- LLM call reduction metrics

Then you iterate. That's disciplined.

---

## When to Move to Phase 2

After 2-4 weeks of Phase 1 data showing:
- ✅ Clarification band working (measure acceptance %)
- ✅ Unknown patterns visible (measure diversity)
- ✅ Admin mapping effective (measure coverage)

Then Phase 2:
- Confidence weighting (based on real success data)
- Throttle table (based on real storm patterns)
- Self-tuning (based on real conversation outcomes)

But first: win with Phase 1.

That's the discipline of shipping early.
