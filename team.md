# 🤖 ChatbotX SaaS Platform - Team Workflow

## 📂 Project Overview
ChatbotX is a multi-tenant AI chatbot platform. This document outlines the file structure and responsibilities for the development team.

---

## 👥 Team Roles & Responsibilities

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

## 📂 Master File Structure

```text
chatbot/
├── app.py                      # Main Entry Point (Shared)
├── config.py                   # Global Config (Shared)
│
├── core/                       # AI Engine (Nandini's Domain)
│   ├── intent_engine.py
│   ├── tokenizer.py
│   └── synonyms.py
│
├── intent_templates/           # JSON Data (Nandini's Workspace)
│   ├── hospital_intents.json
│   └── travel_intents.json
│
├── routes/                     # API Logic
│   ├── admin_api.py            # (Harika & Meghan overlap here)
│   └── chat_routes.py          # (Meghan - Widget APIs)
│
├── static/                     # Frontend Assets
│   ├── style.css               # (Meghan - Styling)
│   └── widget/
│       └── widget.js           # (Meghan - Widget Logic)
│
├── templates/                  # HTML Views
│   ├── super_dashboard.html    # (Harika's Workspace)
│   ├── admin_dashboard.html    # (Meghan's Workspace)
│   ├── branding_panel.html     # (Meghan's Workspace)
│   ├── admin_login.html
│   └── widget.html
│
└── scripts/                    # Utilities
    └── import_intents.py       # (Nandini's Tool)