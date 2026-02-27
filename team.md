# 🤖 ChatbotX SaaS Platform - Team Workflow

## 📂 Project Overview
ChatbotX is a multi-tenant AI chatbot platform. This document outlines the file structure and responsibilities for the development team.

---

## 👥 Team Roles & Domain Ownership

| Developer | Domain/Role                | Key Responsibilities & Areas                                                               |
|-----------|----------------------------|--------------------------------------------------------------------------------------------|
| Harika    | Super Admin (Platform)     | Super admin portal, site/tenant management, models, workflows, platform settings, super_dashboard.html |
| Meghan    | Client Admin & Widget      | Client admin portal, client dashboard, chat widget, services, all client-facing frontend, admin_dashboard.html, widget.js, style.css |
| Nandini   | AI & Intents               | Intent engine, intent templates, training data, import scripts, core/intent_engine.py, intent_templates/ |

**Summary:**
- Harika: Owns all super admin, platform, and backend model logic.
- Meghan: Owns all client admin, widget, and service/frontend logic.
- Nandini: Owns all AI, intent, and data import logic.

This division ensures clear ownership and efficient collaboration.

---

### 👩‍💻 1. Nandini - AI & Intents Specialist
**Responsibility:** Designing conversation flows, training data, and JSON templates.
**Key Directories:**
- `chatbot/intent_templates/` (Create new industry JSONs here)
- `chatbot/scripts/` (Scripts to import your JSONs into the DB)
- `chatbot/core/` (Logic for intent detection - *Read Only*)

**Your Workflow:**
1.  Create a new file (e.g., `travel_intents.json`) in `chatbot/intent_templates/`.
2.  Define intents, training phrases, and responses.
3.  Run the import script to test:
    ```bash
    python chatbot/scripts/import_intents.py chatbot/intent_templates/travel_intents.json --client 1
    ```

---

### 👩‍💻 2. Harika - Super Admin Portal
**Responsibility:** Tenant management, site creation, and platform-wide settings.
**Key Files:**
- `chatbot/templates/super_dashboard.html` (The UI for Super Admins)
- `chatbot/routes/admin_api.py` (Focus on `super_admin_required` routes)
- `chatbot/models/site.py` (Database structure for Sites)

**Your Workflow:**
1.  Login as Super Admin (`admin`/`admin123`).
2.  Work on the **"Create New Tenant"** form in `super_dashboard.html`.
3.  Ensure the "Import Template" feature connects correctly to Nandini's scripts.
4.  Manage global platform configurations.

---

### 👩‍💻 3. Meghan - Client Admin Portal & Widget
**Responsibility:** The dashboard where clients login, and the chat widget they embed on their sites.
**Key Files:**
- `chatbot/templates/admin_dashboard.html` (Client Dashboard UI)
- `chatbot/templates/branding_panel.html` (Branding settings form)
- `chatbot/static/widget/widget.js` (The actual Chat Widget logic)
- `chatbot/static/style.css` (Styling for the chat window)

**Your Workflow:**
1.  Login as a Client (e.g., `apollo_admin`/`123`).
2.  Improve the **"Configuration"** tab in `admin_dashboard.html`.
3.  Style the chat widget in `style.css` to ensure it looks good.
4.  Test the embed experience using `TEST_WIDGET.html`.

---

## 📂 Full Project Structure with Developer Assignments

```text
chatbot/
├── app.py                      # Main Entry Point (Shared: All)
├── config.py                   # Global Config (Shared: All)
├── database.py                 # DB Utilities (Shared: All)
├── DEPLOYMENT_STATUS.md        # Deployment Notes (Shared)
├── README.md                   # Project Overview (Shared)
├── requirements.txt            # Python Dependencies (Shared)
├── team.md                     # Team Workflow (Shared)
├── TEST_WIDGET.html            # Widget Test Page (Meghan)
│
├── core/                       # AI Engine (Nandini)
│   ├── intent_engine.py
│   ├── synonyms.py
│   ├── tokenizer.py
│   └── __pycache__/
│
├── instance/
│   └── chatbot.db              # SQLite DB (Local)
│
├── intent_templates/           # JSON Data (Nandini)
│   └── hospital_intents.json
│
├── models/                     # DB Models (Harika)
│   ├── chat_log.py
│   ├── file_manager.py
│   ├── intent.py
│   ├── plan.py
│   ├── platform_settings.py
│   ├── sector_template.py
│   ├── site.py
│   ├── __init__.py
│   └── __pycache__/
│
├── routes/                     # API Logic
│   ├── admin_api.py            # (Harika & Meghan)
│   ├── chat_routes.py          # (Meghan)
│   └── __pycache__/
│
├── scripts/                    # Utilities (Nandini)
│   ├── apply_migration.py
│   ├── import_intents.py
│   └── migrations/
│       ├── 001_add_workflow_clientconfig.sql
│       ├── 002_add_plan_limits.sql
│       ├── 003_add_plan_is_active.sql
│       ├── 004_add_site_status_email.sql
│       └── 005_create_file_tables.sql
│
├── services/                   # Service Layer (Meghan)
│   ├── chat_service.py
│   ├── file_service.py
│   ├── importer.py
│   ├── intent_service.py
│   ├── response_builder.py
│   └── __pycache__/
│
├── static/                     # Frontend Assets (Meghan)
│   ├── chat.js
│   ├── style.css
│   └── widget.js
│
├── templates/                  # HTML Views
│   ├── admin_dashboard.html    # (Meghan)
│   ├── admin_login.html        # (Meghan)
│   ├── chat.html               # (Meghan)
│   ├── landing.html            # (Meghan)
│   ├── super_dashboard.html    # (Harika)
│   ├── widget.html             # (Meghan)
│
├── workflows/                  # Workflow Handlers (Harika)
│   ├── handler.py
│   └── __pycache__/