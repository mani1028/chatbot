# MessageOrchestrator - Risk Assessment & Action Items

## Status: FUNCTIONAL BUT NOT PRODUCTION READY

The kernel works. All 10 stages execute. Responses are shaped correctly. But three issues remain before declaring production stability.

---

## ⚠️ ISSUE #1: Intent Detection Quality (Classification Failure)

### Observation
```
Test: "What are your hours?"
Expected: business_hours intent detected
Actual: UNKNOWN intent (triggered LLM fallback)
Confidence: 0.60
```

### Root Cause Analysis

The `business_hours` intent exists in DB with phrases INCLUDING "hours":
```json
{
  "name": "business_hours",
  "phrases": ["when are you open", "business hours", "what time do you close", 
              "are you open today", "working hours", "timings", "hours", ...],
  "confidence_threshold": 0.85
}
```

The message "What are your hours?" should match because:
- Contains exact word "hours" 
- Intent has phrase "hours"
- Should score 1.0 on token matching

**But actual flow:**
1. Pattern matching returns confidence < 0.65
2. Intent engine returns `{intent_name: 'UNKNOWN', confidence: 0.60}`
3. `intent_handle_message()` sees UNKNOWN→ calls LLM fallback
4. Returns: `{intent_name: 'UNKNOWN', text: 'Our hours...', confidence: 0.60}`

### Why is confidence < 0.65?

Possible causes (need investigation):
1. **Fuzzy token threshold too strict** (set to 80%)
   - "hours" exact match should work, but maybe compound phrases are penalized
   - Check: Does phrase "what time do you close" NOT match effectively?

2. **Phrase loading issue**
   - Intent DB object might not have phrases populated
   - Check: Does `business_hours.phrases` have items when loaded?

3. **Embedding similarity low**
   - Semantic scoring might be dragging down combined score
   - Check: Is embeddings enabled? What's the embedding similarity?

4. **Intent loading/site scope issue**
   - Intent might be site-scoped to wrong site
   - Check: `business_hours.site_id` == 0 (global) or == test_site_id

### Verification Commands

```python
# Check if intent exists and is accessible
bh = Intent.query.filter_by(intent_name="business_hours").first()
if bh:
    print(f"site_id: {bh.site_id} (0=global, 3=test site)")
    print(f"phrases: {len(bh.phrases)} loaded")
    for p in bh.phrases[:3]:
        print(f"  - {p.phrase}")
else:
    print("business_hours intent not found!")

# Check if detection is being scoped correctly
# Line 106 of core/intent_engine.py:
# intents = Intent.query.filter(or_(Intent.site_id == 0, Intent.site_id == site_id)).all()
# Is this returning business_hours?
```

### Action to Resolve

1. **Immediate**: Run diagnostic to check:
   - Does test site have access to business_hours intent? ✓ (global scope)
   - Are phrases loaded from DB? ? (need to verify)
   - What confidence score is calculated? ? (need debug logging)

2. **If phrases loaded**: Investigate scoring algorithm
   - Add temporary debug logging to pattern matching
   - Check if embedding similarity is the culprit
   - Consider lowering fuzzy threshold from 80 to 75-70

3. **If phrases NOT loaded**: Fix intent import/DB migration
   - Run migration to ensure IntentPhrase records created
   - Verify import scripts populated `intentphrases` table

**Impact Level**: HIGH - This is the #1 user-facing issue

---

## ✅ ISSUE #2: Logging Error (FIXED)

### Problem
```
ERROR: Failed to log unanswered question
'Entity namespace for "unanswered_questions" has no property "site_id"'
```

### Root Cause
`UnansweredQuestion` model missing `site_id` field, but code tried to use it:
```python
# In core/intent_engine.py line 265
q = UnansweredQuestion(question=message, site_id=site_id, ...)
```

### Fix Applied ✅
Added `site_id` field to model:
```python
site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False, index=True)
```

**File**: [models/unanswered_question.py](models/unanswered_question.py)

### Database Migration Required
```sql
ALTER TABLE unanswered_questions ADD COLUMN site_id INTEGER NOT NULL;
ALTER TABLE unanswered_questions ADD FOREIGN KEY (site_id) REFERENCES site(id);
CREATE INDEX idx_unanswered_questions_site_id ON unanswered_questions(site_id);
```

**Impact Level**: MEDIUM - Non-critical but affects logging integrity

---

## ✅ ISSUE #3: LLM Fallback Double Invocation (RESOLVED)

### Problem Discovered
LLM API was called **TWICE** for single message when intent was UNKNOWN:
- Call #1 (1.55s): From Stage 6 `intent_handle_message()` → internally called `llm_fallback()`
- Call #2 (1.87s): From Stage 8 `_run_llm()` → also called `llm_fallback()`
- **Total impact: 3.4+ seconds latency, 2x API charges**

### Root Cause Analysis
Two unconditional LLM entry points existed:
1. `intent_service.intent_handle_message()` contained embedded `llm_fallback()` logic
2. `orchestrator._run_llm()` independently decided to call `llm_fallback()`
3. No coordination between layers → both fired when intent was UNKNOWN

### Fix Applied ✅

**Created `detect_intent_only()` function** (services/intent_service.py, lines 177-224):
```python
def detect_intent_only(message: str, site_id: int, history: list = None) -> dict:
    """Pure intent detection WITHOUT LLM fallback."""
    # Calls detect_intent() and apply_context_awareness()
    # NOTE: DO NOT CALL LLM HERE - That is orchestrator's responsibility
    return result
```

**Refactored orchestrator Stage 6** (services/message_orchestrator.py, line 360):
```python
# BEFORE: result = intent_handle_message(message, thread.site_id, history)
# AFTER:  result = detect_intent_only(message, thread.site_id, history)
```

**Result**: Stage 6 now returns pure intent detection without triggering LLM

### Validation ✅

Instrumentation confirmed single invocation:
```
Test: "qwerty zxcvbn" (UNKNOWN intent)
  [!!!] LLM_CALLED_BY__RUN_LLM | site_id=3
  → Single LLM call from orchestrator only ✓
```

Test results:
```
Test 1 (Greeting):      1 LLM call (1.58s) ✓
Test 2 (Unknown):       1 LLM call (1.76s) ✓ (was 2 before)
Test 3 (Task):          1 LLM call (1.55s) ✓
```

### Impact Achieved
- **Cost**: 50% reduction in LLM API usage for UNKNOWN intents
- **Latency**: 1.8s instead of 3.4s (50% improvement)
- **Stability**: Central orchestrator control, no race conditions
- **Architecture**: Enforced principle: "LLM invocation in exactly one place"

**Impact Level**: ✅ CRITICAL ISSUE RESOLVED - No longer a production blocker

**Documentation**: See [ARCHITECTURAL_FIX_SUMMARY.md](ARCHITECTURAL_FIX_SUMMARY.md) and [DETAILED_CODE_CHANGES.md](DETAILED_CODE_CHANGES.md)

---

## Summary: What Works ✅ vs What Needs Work ⚠️

| Component | Status | Notes |
|-----------|--------|-------|
| Stage 1: Thread Loading | ✅ | Fixed initialization bug |
| Stage 2: Message Appending | ✅ | History tracked correctly |
| Stage 3: Rules | ✅ | Hard stops working |
| Stage 4: Context | ✅ | Frustration scoring runs |
| Stage 5: Workflow | ✅ | Booking workflow detected |
| **Stage 6: Intent Detection** | ⚠️ | Quality issues - confidence too low |
| Stage 7: Feature Gates | ✅ | Structure correct |
| **Stage 8: LLM Fallback** | ✅ | FIXED - Single invocation enforced |
| Stage 9: Analytics | ✅ | site_id field added (migration needed) |
| Stage 10: Finalize | ✅ | Persistence working |
| **Adapter Layer** | ✅ | Response schema correct |
| **HTTP Integration** | ✅ | No more crashes |

---

## Deployment Readiness

### Can Deploy to Staging?
**Maybe** - One critical issue resolved (LLM double invocation), but Intent quality must still be verified first.

### Resolved Issues ✅
- ✅ **ISSUE #3 FIXED**: LLM Double Invocation
  - Root cause: Two LLM entry points (intent_service and orchestrator)
  - Solution: Created `detect_intent_only()` for pure detection
  - Result: Single LLM invocation, 50% cost/latency improvement
  - See: [ARCHITECTURAL_FIX_SUMMARY.md](ARCHITECTURAL_FIX_SUMMARY.md)

### Remaining Issues ⚠️
- ⚠️ **ISSUE #1 PENDING**: Intent Quality (confidence too low)
  - business_hours intent scoring < 0.65 despite containing exact phrases
  - Hypothesis: Fuzzy threshold too strict or phrase loading issue
  - Action: Run diagnostic → adjust threshold → test

### Must Fix Before Staging
1. ⚠️ **URGENT**: Diagnose and fix business_hours detection (Issue #1)
2. ✅ **DONE**: Add site_id to UnansweredQuestion (run migration)
3. ✅ **DONE**: Verify no double LLM invocation (Issue #3 resolved)

### After These Fixes
Safe to deploy to staging with monitoring on:
- Intent detection confidence distribution
- LLM API usage (should be single call per message)
- Orchestrator Stage 6 execution times

---

## Next Steps

1. **COMPLETED**: Resolve LLM Double Invocation (Issue #3) ✅
   - Architectural fix applied and validated
   - Cost reduced by 50%, latency improved by 50%
   - All systems green for LLM invocation

2. **NOW**: Investigate Intent Quality (Issue #1)
   - Run diagnostic script to check phrase loading
   - Add debug logging to pattern matching
   - Determine if threshold needs adjustment

3. **Before Staging Deploy**: 
   - Run full booking workflow to completion
   - Verify intent confidence distribution is acceptable
   - Run database migrations for unanswered_questions

The system is **architecturally sound** (LLM invocation fixed) but needs **domain configuration verification** (intent quality) before production.

