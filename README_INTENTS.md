# Intent Selection & Assignment - Complete Solution

## ✅ Problem Solved
Users can now successfully **select and assign intents** through the Admin Dashboard's "Intent Assignments" tab.

## 📊 Current System Status

```
Database:
├── 48 Blueprint Intents (site_id=0) - Ready to assign
├── 1 Client Intent (site_id=1) - Already assigned
└── 1 Template (fallback) 

Templates:
├── 31 Intent Template Files
└── 48 Intents across all templates

Coverage:
├── Core Intents (greetings, goodbye, help, etc.)
├── Hospital Intents (pricing, visiting hours)
├── Business Intents (HR, payroll, invoices, etc.)
├── Action Intents (workflow-enabled tasks)
├── Handoff Intents (emergency, escalation, etc.)
└── Custom Intent Types (info, action, LEAD, HUMAN)
```

## 🛠️ Solution Components

### 1. **manage_blueprints.py** - Smart Blueprint Manager
Auto-loads intents from template files with support for updates.

**Usage:**
```bash
# Initial setup
python manage_blueprints.py

# Reload after template changes  
python manage_blueprints.py --force
```

**Features:**
- ✅ Auto-detects 31 template JSON files
- ✅ Creates/updates 39-48 blueprints automatically
- ✅ Preserves client-specific intents (never deleted)
- ✅ Idempotent (safe to run multiple times)
- ✅ Provides detailed creation/update summary

### 2. **intent_helper.py** - Management Tool
Shows system status and helps troubleshoot.

**Usage:**
```bash
python intent_helper.py              # Show everything
python intent_helper.py blueprints   # List all blueprints
python intent_helper.py clients      # Show client sites
python intent_helper.py client <id>  # Show client's intents
python intent_helper.py sync         # Check template sync
```

### 3. **db_init_blueprints.py** - Quick Setup (Fallback)
Direct database initialization with 6 default intents.

**Usage:**
```bash
python db_init_blueprints.py
```

## 🔄 Workflow: Upload Changes Through Portal

### Scenario 1: Update Template File
```
1. Edit: intent_templates/hospital_intents.json
2. Commit: git add, git commit
3. Deploy: Pull changes to server
4. Sync: python manage_blueprints.py --force
5. Result: Blueprint updates, all clients using it now have new phrases
```

### Scenario 2: User Uploads Intent via Portal
```
1. Client Admin creates new intent in Dashboard
2. System creates: intents.site_id = <CLIENT_SITE_ID>
3. Result: This intent is now client-specific only
4. Other clients: Still use their assigned blueprints
```

### Scenario 3: Add New Blueprint from Portal
```
1. Super Admin creates blueprint in "Blueprint CRUD"
2. System creates: intents.site_id = 0
3. Step 3: Blueprint now appears in "Add Intent" dropdowns
4. Step 4: Can assign to any client
```

## 🚀 How Intent Assignment Works

```
Super Admin Dashboard → Intent Assignments Tab
                    ↓
            Select Client Site
                    ↓
         Click "+ Add Intent"
                    ↓
    GET /admin/api/super/blueprints
    (Retrieves intents where site_id=0)
                    ↓
         Dropdown shows all blueprints
                    ↓
       User selects intent + clicks Assign
                    ↓
    POST /admin/api/super/sites/<id>/assign-intent
    (Creates copy with client's site_id)
                    ↓
     Intent now assigned to this client
```

## 📝 Key Concepts

### **Blueprint Intents** (site_id = 0)
- Template/master copies
- Managed via template files
- Updated with `python manage_blueprints.py --force`
- Assigned to multiple clients
- Changes don't affect existing client copies

### **Client Intents** (site_id > 0)
- Client-specific customizations
- Created when assigning blueprint OR uploading via portal
- Fully independent from blueprints
- Can be edited without affecting others
- Each client has their own copy

### **Intent Templates** (intent_templates/*.json)
- Declarative source of truth
- Version control friendly
- 31 files covering multiple business domains
- Loaded automatically by manage_blueprints.py

## 📋 Intent Types Available

| Type | Purpose | Example |
|------|---------|---------|
| `info` | Informational response | GREETING, PRICING, BUSINESS_HOURS |
| `action` | Triggers workflow | TASK_CREATION, COMMAND_MODIFY |
| `LEAD` | Lead capture form | CLIENT_INQUIRY, LEAD_CAPTURE |
| `HUMAN` | Human handoff | EMERGENCY_HELP, ESCALATION_REQUEST |

## 🔍 Verification Steps

### 1. Check Blueprint Count
```bash
sqlite3 instance/chatbot.db "SELECT COUNT(*) FROM intents WHERE site_id=0;"
```
Expected: 39+ (depending on templates)

### 2. Verify Templates Loaded
```bash
python intent_helper.py check
```
Expected: 31 files, 48 intents

### 3. Check Admin Dashboard
1. Login as Super Admin
2. Go: Intent Assignments tab
3. Select any client site
4. Click: + Add Intent button
5. Verify: Dropdown lists all blueprints

### 4. Full System Status
```bash
python intent_helper.py
```
Shows complete inventory and sync status

## 🐛 Troubleshooting

### Issue: "Add Intent" dropdown is empty
```bash
# Verify blueprints exist
sqlite3 instance/chatbot.db "SELECT COUNT(*) FROM intents WHERE site_id=0;"

# Reload from templates
python manage_blueprints.py --force

# Clear browser cache (Ctrl+Shift+Delete)
# Reload dashboard
```

### Issue: Lost custom intent after --force
Client intents (site_id > 0) are NEVER affected by `--force`. Check:
```bash
sqlite3 instance/chatbot.db \
  "SELECT intent_name FROM intents WHERE site_id=<YOUR_CLIENT_ID>;"
```

### Issue: Template changes not syncing
```bash
# Reload with force
python manage_blueprints.py --force

# Check sync status
python intent_helper.py sync

# Review changes
git diff intent_templates/
```

## 📚 Documentation Files

1. **INTENT_ASSIGNMENT_FIX.md** - Original problem & solution
2. **INTENT_MANAGEMENT_GUIDE.md** - Complete workflows
3. **README.md** (this file) - System overview
4. **intent_helper.py** - Diagnostic tool
5. **manage_blueprints.py** - Blueprint manager
6. **db_init_blueprints.py** - Emergency setup

## 🎯 Next Steps

1. ✅ Run: `python manage_blueprints.py` (if not done)
2. ✅ Login to Admin Dashboard
3. ✅ Test Intent Assignment workflow:
   - Go to Intent Assignments
   - Select client
   - Click + Add Intent
   - Choose blueprint from dropdown
   - Click Assign Intent
4. ✅ Verify client sees new intent

## 💾 Backup Recommendations

Before running `--force` on production:
```bash
# Backup database
cp instance/chatbot.db instance/chatbot.db.backup

# Run update
python manage_blueprints.py --force

# If issues, restore
cp instance/chatbot.db.backup instance/chatbot.db
```

## 📞 Support

For issues:
1. Check: `python intent_helper.py`
2. Check docs: `INTENT_MANAGEMENT_GUIDE.md`
3. Review: `git log intent_templates/`
4. Database: `sqlite3 instance/chatbot.db`
