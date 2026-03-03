# Phase 2 Frontend Integration Guide

## Overview
Phase 2 frontend modifications add plan-based feature control, context awareness (frustration/confusion detection), and escalation to human support. All modifications maintain backward compatibility.

---

## Frontend Files Modified

### 1. **static/widget.js** (Enterprise Chat Widget)
**New Features:**
- Plan-based feature gating (Free/Pro/Enterprise)
- Context indicator display (frustration/confusion alerts)
- Scalable escalation button
- Auto-escalation offer when user is frustrated

**Key Changes:**
- Added `siteFeatures` object tracking plan and enabled features
- Added `updateContextIndicator()` - shows frustration/confusion level with color coding
- Added `escalateToHuman()` - connects to human agent via API
- Added `showEscalationOffer()` - displays escalation offer buttons
- Updated `sendMessage()` to handle `context_analysis` from API response

**New Variables:**
```javascript
let siteFeatures = {
    plan: 'free',                    // free, pro, enterprise
    analytics_enabled: false,
    context_engine_enabled: false,
    escalation_enabled: false,
    compression_enabled: false
};
```

**New Functions:**
```javascript
escalateToHuman()        // POST /api/escalate
updateContextIndicator() // Updates UI with frustration/confusion indicators
showEscalationOffer()    // Shows escalation option buttons
```

---

### 2. **static/chat.js** (Demo Page Chat)
**New Features:**
- Plan-based feature visibility
- Context indicator display
- Inline escalation button

**Key Changes:**
- Added `siteFeatures` tracking
- Added `initFeatures()` - fetches site plan from `/api/site-features`
- Updated `appendMessage()` to display context metadata when available
- Added `escalate()` function for demo page escalation

---

### 3. **static/style.css** (Styling)
**New CSS Classes:**
- `.context-indicator` - Status bar showing frustration/confusion
- `.widget-escalate` - Escalation button in footer
- `.escalation-offer` - Escalation yes/no button pair
- `.escalation-yes`, `.escalation-no` - Individual offer buttons
- `.plan-badge` - Display site's current plan
- `.feature-locked` - Visual indicator for unavailable features
- Animations: `@keyframes pulse` for indicator animation

**Dark Mode Support:** All new styles include dark mode variants

---

## Required Backend API Endpoints

### 1. **GET /api/site-features**
Fetch site's plan and enabled features.

**Parameters:**
```
site_key: string (query param)
```

**Response:**
```json
{
  "site_id": 1,
  "plan": "pro",
  "analytics_enabled": true,
  "context_engine_enabled": true,
  "escalation_enabled": true,
  "compression_enabled": true,
  "workflow_limit": 3,
  "max_custom_workflows": 0,
  "monthly_api_calls": 10000
}
```

**Plan Tiers:**
| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| Workflows | 1 | 3 | Unlimited |
| Analytics | ❌ | ✅ | ✅ |
| Context Engine | ❌ | ✅ | ✅ |
| Escalation | ❌ | ✅ | ✅ |
| Custom Workflows | ❌ | ❌ | ✅ |
| API Calls/month | 5,000 | 50,000 | Unlimited |

---

### 2. **POST /api/chat**
Send message and receive response with Phase 2 context data.

**Request:**
```json
{
  "message": "string",
  "site_key": "string",
  "session_id": "string (optional)",
  "include_context": true
}
```

**Response (with Phase 2 data):**
```json
{
  "reply": "Bot message text",
  "workflow_state": "collecting_email",
  "workflow_type": "booking",
  "collected_data": {
    "name": "John",
    "email": "john@example.com"
  },
  "intent_name": "book_appointment",
  "context_analysis": {
    "frustration_level": 0.45,
    "confusion_level": 0.2,
    "intent_drift": null,
    "should_escalate": false,
    "escalation_reason": null,
    "detected_patterns": ["quick_responses"],
    "recommendation": "continue"
  },
  "error": null
}
```

**Key Fields:**
- `frustration_level`: 0-1.0 (0 = calm, 1 = high frustration)
- `confusion_level`: 0-1.0 (0 = clear, 1 = confused)
- `should_escalate`: boolean - auto-recommend human agent
- `escalation_reason`: string - reason for escalation (e.g., "high_frustration", "repeated_unknown_intents")

---

### 3. **POST /api/escalate**
Initiate human agent handoff.

**Request:**
```json
{
  "site_key": "string",
  "session_id": "string",
  "reason": "string (optional)"
}
```

**Response:**
```json
{
  "status": "escalated",
  "agent_queue_position": 1,
  "estimated_wait": "2 minutes",
  "session_id": "string",
  "handoff_id": "string"
}
```

---

### 4. **GET /api/widget-settings** (Updated)
Fetch widget configuration. **Now includes plan data.**

**Parameters:**
```
site_key: string (query param)
```

**Response:**
```json
{
  "primary_color": "#6366f1",
  "bot_name": "AlinaX",
  "theme_mode": "light",
  "initial_message": "Hello! How can I help?",
  "preserve_chat_history": true,
  "plan": "pro",
  "context_engine_enabled": true,
  "escalation_enabled": true
}
```

---

## Integration Checklist

### Backend Tasks
- [ ] Implement `/api/site-features` endpoint
- [ ] Update `/api/chat` to return `context_analysis` from ContextEngine
- [ ] Implement `/api/escalate` endpoint
- [ ] Update `/api/widget-settings` to include plan data
- [ ] Add Site model field: `workflow_plan` (free/pro/enterprise)
- [ ] Add Site model field: `features_enabled` (JSON)\
- [ ] Create SiteWorkflowControl integration in route handlers
- [ ] Create FeatureGate integration for gradual rollouts

### Frontend Tasks
- [x] Update `widget.js` with Phase 2 features
- [x] Update `chat.js` with context support
- [x] Add Phase 2 CSS styles
- [x] Add escalation UI components
- [x] Add context indicator displays

### Testing Tasks
- [ ] Test `/api/site-features` returns correct plan data
- [ ] Test escalation button appears only for Pro/Enterprise
- [ ] Test context indicator shows on frustration > 0.6
- [ ] Test auto-escalation offer triggers appropriately
- [ ] Test Dark mode for all new components
- [ ] Test responsive design on mobile (widget at 280px width)
- [ ] Test WebSocket escalation handoff

---

## Implementation Priority

### Phase 2.1 - High Priority (Required for Release)
1. Implement `/api/site-features` endpoint
2. Update `/api/chat` to include `context_analysis`
3. Add `SiteWorkflowControl` model to Site
4. Test context indicator display

### Phase 2.2 - Medium Priority (Recommended)
1. Implement `/api/escalate` endpoint
2. Create escalation routing to agents
3. Set up WebSocket for agent messages
4. Update admin panel to manage features/plan

### Phase 2.3 - Lower Priority (Nice to Have)
1. Feature gate rollout UI in admin
2. Analytics dashboard displaying context metrics
3. A/B testing workflow versions
4. Custom workflow upload in admin

---

## Code Examples

### Example 1: Using Plan-Based Features in Flask Route

```python
from services.multi_tenant_control import get_site_control

@routes.post('/api/chat')
def chat():
    site_key = request.json.get('site_key')
    message = request.json.get('message')
    
    # Get site and check plan
    site = Site.query.filter_by(api_key=site_key).first()
    site_control = get_site_control(site.id)
    
    # Check if context engine is enabled for this site
    if site_control.is_feature_enabled('context_engine'):
        from services.context_engine import ContextAnalyzer
        context_analyzer = ContextAnalyzer()
        thread = ...  # get conversation thread
        context_data = context_analyzer.analyze_full_context(thread)
        response['context_analysis'] = {
            'frustration_level': context_data['frustration'],
            'confusion_level': context_data['confusion'],
            'should_escalate': context_data['should_escalate']
        }
    
    return response
```

### Example 2: Feature Gate in Frontend

```javascript
// Check if feature is enabled before showing UI
async function initFeatures() {
    const res = await fetch(`/api/site-features?site_key=${SITE_KEY}`);
    const data = await res.json();
    
    // Only show escalation button if enabled
    if (data.escalation_enabled) {
        document.querySelector('.widget-escalate').style.display = 'block';
    }
}
```

### Example 3: Auto-Escalation Logic

```python
# In /api/chat route, after getting bot response:
if site_control.is_feature_enabled('context_engine'):
    context_analysis = context_engine.analyze(thread, message)
    if context_analysis['frustration'] > 0.7:
        response['context_analysis']['should_escalate'] = True
        response['context_analysis']['escalation_reason'] = 'high_frustration'
        # Frontend will automatically show escalation offer
```

---

## Migration Notes

### Backward Compatibility
- All new fields are optional in API responses
- Frontend checks for feature existence before using
- Legacy sites without Plan model default to 'free' plan
- Existing chat functionality works without Phase 2 features

### Database Changes Required
```sql
-- Add to Site model
ALTER TABLE site ADD COLUMN workflow_plan VARCHAR(20) DEFAULT 'free';
ALTER TABLE site ADD COLUMN features_enabled JSON DEFAULT '{}';

-- Add to ConversationThread (from Phase 2)
CREATE TABLE conversation_thread (
    id INTEGER PRIMARY KEY,
    site_id INTEGER,
    session_id VARCHAR(50),
    workflow_type VARCHAR(50),
    current_step VARCHAR(100),
    short_term_messages JSON,
    structured_data JSON,
    workflow_status VARCHAR(20),
    completion_score FLOAT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

---

## Performance Considerations

1. **Context Analysis** - Runs on every message, optimize keyword matching
2. **Token Compression** - Saves ~70% on LLM calls, reduces API costs
3. **Feature Gating** - Uses in-memory flags, no DB lookup needed
4. **Caching** - Cache site features for 5 minutes

---

## Troubleshooting

### Context Indicator Not Showing
- Check `/api/site-features` returns `context_engine_enabled: true`
- Verify frustration_level in response is > 0.6
- Check browser console for JavaScript errors

### Escalation Button Not Appearing
- Verify site plan is 'pro' or 'enterprise'
- Check `/api/site-features` returns `escalation_enabled: true`
- Ensure CSS loaded (check style.css includes Phase 2 styles)

### Auto-Escalate Not Triggering
- Verify feature gate is enabled in backend
- Check ContextEngine is returning `should_escalate: true`
- Verify frontend sees `context_analysis` in response

---

## Support

For Phase 2 frontend integration help, see:
- [PHASE_2_COMPLETE.md](PHASE_2_COMPLETE.md) - Backend components
- [Widget.js Code](static/widget.js) - Frontend source
- [Chat.js Code](static/chat.js) - Demo page source
