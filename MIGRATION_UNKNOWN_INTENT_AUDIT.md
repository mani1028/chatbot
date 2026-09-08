# Database Migration: Unknown Intent Audit Trail

**Date:** March 9, 2026  
**Task:** Upgrade `unknown_intent_logs` table with comprehensive audit fields for admin mapping.

## Overview

The `UnknownIntentLog` model has been enhanced with full audit trail support to enable:
- Complete mapping history (who mapped what, when)
- Automatic phrase training tracking
- Resolution status monitoring
- Advanced fallback analytics

## Schema Changes

### New Columns Added to `unknown_intent_logs` table

| Column | Type | Nullable | Default | Purpose |
|--------|------|----------|---------|---------|
| `llm_response` | TEXT | ✓ | NULL | The fallback response shown to the user |
| `fallback_type` | VARCHAR(50) | ✗ | 'llm' | Why fallback occurred: 'llm', 'throttle', 'confidence' |
| `resolved` | BOOLEAN | ✓ | False | Has admin mapped this? |
| `mapped_intent_id` | INTEGER | ✓ | NULL | Target intent ID (FK to intent table) |
| `mapped_by` | INTEGER | ✓ | NULL | Admin ID who mapped it |
| `mapped_at` | DATETIME | ✓ | NULL | When mapping occurred |
| `phrase_auto_trained` | BOOLEAN | ✓ | False | Was message auto-added as phrase? |

### Indexes Added

```sql
CREATE INDEX idx_site_unresolved ON unknown_intent_logs(site_id, resolved);
CREATE INDEX idx_fallback_type ON unknown_intent_logs(fallback_type);
```

## Auto-Migration

If using SQLAlchemy with automatic table creation, the new columns will be created automatically on next app startup:

```bash
python app.py
```

SQLAlchemy will detect the model changes and alter the table.

## Manual Migration (if needed)

If you need to manually apply these changes to an existing database:

```sql
-- Add new columns
ALTER TABLE unknown_intent_logs ADD COLUMN llm_response TEXT NULL;
ALTER TABLE unknown_intent_logs ADD COLUMN fallback_type VARCHAR(50) DEFAULT 'llm' NOT NULL;
ALTER TABLE unknown_intent_logs ADD COLUMN resolved BOOLEAN DEFAULT FALSE;
ALTER TABLE unknown_intent_logs ADD COLUMN mapped_intent_id INTEGER NULL;
ALTER TABLE unknown_intent_logs ADD COLUMN mapped_by INTEGER NULL;
ALTER TABLE unknown_intent_logs ADD COLUMN mapped_at DATETIME NULL;
ALTER TABLE unknown_intent_logs ADD COLUMN phrase_auto_trained BOOLEAN DEFAULT FALSE;

-- Add indexes for performance
CREATE INDEX idx_site_unresolved ON unknown_intent_logs(site_id, resolved);
CREATE INDEX idx_fallback_type ON unknown_intent_logs(fallback_type);
```

## Backward Compatibility

- **Existing rows:** Will have NULL for new fields (safe)
- **Reading old logs:** `to_dict(include_admin_fields=False)` returns new-field-free response
- **API:** No breaking changes; audit fields optional in responses

## New Endpoints

### 1. Get Unknown Intent Manager UI
```
GET /admin/unknown-intent-manager
```
Returns: HTML page for one-click mapping with suggestions

### 2. List Unmapped Unknowns (Enhanced)
```
GET /admin/api/unknown/unmapped?limit=50
```
Returns: Unknowns with similarity_suggestions using embedding cache

### 3. Get Single Log with Audit Trail
```
GET /admin/api/unknown/log/<id>
```
Returns: Full log with mapped_by, mapped_at, phrase_auto_trained, similarity_suggestions

### 4. Get Available Intents for Mapping
```
GET /admin/api/intents
```
Returns: List of intents for selection modal

### 5. Map Unknown to Intent (Updated)
```
POST /admin/api/unknown/map
Body: {
  "unknown_log_id": 123,
  "intent_id": 456,
  "auto_train_phrases": true
}
```
Now sets: mapped_intent_id, mapped_by, mapped_at, phrase_auto_trained, resolved=true

## Updated Code Files

### Models
- `models/unknown_intent_log.py` — Enhanced schema + `to_dict()` method

### Services
- `services/fallback_optimizer.py` — Updated `record_fallback_event()` and `map_unknown_to_intent()` to populate audit fields

### Routes
- `routes/unknown_intent_admin.py` — Enhanced endpoints + semantic similarity suggestions

### App
- `app.py` — Registered `unknown_intent_bp` blueprint

### Templates
- `templates/unknown_intent_manager.html` — NEW admin UI for one-click mapping

## Next Steps

1. **Start app** (triggers auto-migration)
   ```bash
   python app.py
   ```

2. **Access the UI**
   - Admin dashboard → Unknown Intent Manager
   - URL: `http://localhost:5000/admin/unknown-intent-manager`

3. **Test the flow**
   - Trigger unknown intents in chat
   - Review in Unknown Intent Manager
   - Map to intents with one click
   - Auto-train phrases

## Rollback

If you need to rollback:

```sql
-- Drop indexes
DROP INDEX IF EXISTS idx_site_unresolved ON unknown_intent_logs;
DROP INDEX IF EXISTS idx_fallback_type ON unknown_intent_logs;

-- Drop columns
ALTER TABLE unknown_intent_logs DROP COLUMN llm_response;
ALTER TABLE unknown_intent_logs DROP COLUMN fallback_type;
ALTER TABLE unknown_intent_logs DROP COLUMN resolved;
ALTER TABLE unknown_intent_logs DROP COLUMN mapped_intent_id;
ALTER TABLE unknown_intent_logs DROP COLUMN mapped_by;
ALTER TABLE unknown_intent_logs DROP COLUMN mapped_at;
ALTER TABLE unknown_intent_logs DROP COLUMN phrase_auto_trained;
```

Then revert model and code changes.

## Questions?

Refer to the comprehensive documentation:
- [CONTACT_AGENT_FEATURE.md](CONTACT_AGENT_FEATURE.md) for similar audit patterns
- [README_FEATURES.md](README_FEATURES.md#fallback-optimization) for fallback system overview
- Code comments in `services/fallback_optimizer.py` for implementation details
