# 🤖 AI-Powered Multi-Tenant Chatbot SaaS Platform

**Status**: ✅ Core Features | 🔄 Advanced Features In Progress

A production-ready Flask-based SaaS chatbot platform with multi-tenancy, AI intent detection, semantic search, LLM fallback, and comprehensive admin/super-admin dashboards.

---

## 📊 Quick Feature Status

| Category | Status | Details |
|----------|--------|---------|
| **Chat & Intent** | ✅ Complete | Multi-tenant chat, intent detection, confidence scoring |
| **LLM Fallback** | ✅ Complete | OpenAI integration working (with free alternatives available) |
| **Admin Dashboard** | ✅ Complete | 7 tabs: Intents, Logs, Branding, Analytics, Settings, Channels, Usage |
| **Super Admin** | ✅ Partial | Dashboard complete + **Intent Assignments fully working** |
| **Security** | ✅ Complete | Domain whitelisting, role-based access, SQL injection prevention |
| **Blueprint CRUD** | ⚠️ Partial | View works, Create/Edit/Delete UI "coming soon" |
| **Vector Search** | ✅ Complete | ChromaDB integration for semantic search |
| **Analytics** | ✅ Complete | Usage tracking, message counts, charts |

**For detailed feature inventory with implementation status, see [README_FEATURES.md](README_FEATURES.md)**

---

## 🚀 Quick Start (5 Minutes)

### 1. Setup
```bash
git clone <repo> && cd chatbot
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure
Create `.env`:
```dotenv
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
DATABASE_URL=sqlite:///chatbot.db
OPENAI_API_KEY=sk-proj-YOUR_KEY  # Or use free alternatives (see below)
```

### 3. Initialize
```bash
python app.py  # Creates DB, then CTRL+C
python scripts/init_site.py  # Create tenant
python scripts/import_intents.py intent_templates/hospital_intents.json --client 1
```

### 4. Run
```bash
python app.py
# Admin: http://localhost:5000/admin/login (admin/admin123)
# Chat: http://localhost:5000
```

---

## 💰 Free LLM Alternatives (No Billing Required)

| Option | Best For | Setup |
|--------|----------|-------|
| **OpenRouter** ⭐ RECOMMENDED | Multiple models, generous free tier | `OPENROUTER_API_KEY` from openrouter.ai |
| **Google Gemini** | Fast, reliable free tier | `GOOGLE_API_KEY` from ai.google.dev |
| **Hugging Face** | Open-source models, self-hosting | `HF_API_KEY` from huggingface.co |

[See full integration examples in README_FEATURES.md](README_FEATURES.md#-free-ai-api-integration-options)

---

## 🎯 Key Features

### Core Capabilities
- ✅ Intent detection with fuzzy matching & confidence scoring
- ✅ LLM-powered fallback for complex queries  
- ✅ Semantic search via ChromaDB vector database
- ✅ Multi-tenant architecture with complete isolation
- ✅ Domain whitelisting & security decorators
- ✅ Conversation history tracking

### Admin Interfaces
- **Client Admin** (`/admin`) - 7 tabs for intent/branding/analytics management
- **Super Admin** (`/super-admin`) - Platform-wide management including:
  - Blueprint intent viewing & distribution
  - Intent assignment across client sites
  - Admin user management (UI in progress)
  - Platform settings & configuration

### API Endpoints
```
POST   /api/chat                    Chat API (requires site_id)
GET    /api/chat/history            Conversation history
GET    /admin/api/super/blueprints  Get template intents
POST   /admin/api/super/sites/{id}/assign-intent   Assign intent to client
DELETE /admin/api/super/sites/{id}/intents/{name}  Remove intent
[... 50+ admin/super-admin endpoints]
```

### Data Models (17+ models)
Site, Intent, IntentPhrase, ChatLog, User, Admin, ClientConfig, Webhook, Booking, Announcement, Form, Usage, Plan, Billing, and more.

---

## 📁 Project Structure

```
chatbot/
├── app.py                    # Flask entry point
├── config.py & .env         # Configuration
├── requirements.txt         # Dependencies
├── core/                    # Intent detection engine
├── models/                  # SQLAlchemy ORM (17+ models)
├── routes/                  # API endpoints (chat, admin, super-admin)
├── services/                # Business logic (chat, intent, LLM, search)
├── scripts/                 # CLI utilities
├── templates/               # Admin dashboards & chat UI
├── static/                  # Frontend assets (JS, CSS)
├── intent_templates/        # 30+ pre-built intent packs
└── instance/chatbot.db      # SQLite database
```

---

## 🛠️ Common Tasks

### Create New Intent Pack
```bash
# Edit JSON following schema in intent_templates/hospital_intents.json
python scripts/import_intents.py intent_templates/yourfile.json --client 1
```

### Assign Blueprint Intent to Client
1. Super Admin → Intent Assignments tab
2. Select client site
3. Click "Add Intent"
4. Choose blueprint → Confirm
5. Intent copied with all phrases

### Update Client Configuration
```python
from app import app
from models.client_config import ClientConfig
db.session.query(ClientConfig).filter_by(
    site_id=1, key='consultation_price'
).first().value = "500"
db.session.commit()
```

### Check System Health
```bash
python verify_intent_endpoints.py     # Full verification
python scripts/quick_test_llm.py       # LLM connectivity
```

---

## ⚠️ Known Limitations

- Blueprint create/edit UI not available (use CLI import scripts)
- Admin user CRUD UI in progress (database/CLI available)
- No real-time collaboration features
- Mobile app not built yet

---

## 🔒 Production Checklist

- [ ] Change SECRET_KEY in config.py
- [ ] Set strong ADMIN_PASSWORD
- [ ] Use HTTPS (Nginx reverse proxy)
- [ ] Switch to PostgreSQL (production DB)
- [ ] Add rate limiting
- [ ] Enable request logging
- [ ] Set up automated backups
- [ ] Use Gunicorn (not Flask dev server)

[Full security guide in SECURITY.md](SECURITY.md)

---

## 🐛 Troubleshooting

**Flask won't start?**
```bash
pip install -r requirements.txt --force-reinstall
python --version  # Require 3.8+
```

**Admin login fails?**
```bash
rm instance/chatbot.db && python app.py  # Reset DB
```

**LLM not responding?**
```bash
python verify_intent_endpoints.py  # Check status
grep OPENAI_API_KEY .env  # Verify key
```

---

## 📚 Documentation

- **[README_FEATURES.md](README_FEATURES.md)** - Detailed feature inventory with implementation status
- **[SECURITY.md](SECURITY.md)** - Security guidelines
- **[DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md)** - Deployment information

---

## 🚀 Next Steps

**High Priority**:
- [ ] Implement Blueprint CRUD UI
- [ ] Complete Admin Users management UI
- [ ] Switch from OpenAI to free LLM provider

**Medium Priority**:
- [ ] Multi-language support
- [ ] Advanced analytics
- [ ] Webhook UI management

**Lower Priority**:
- [ ] Mobile app
- [ ] Real-time WebSocket features
- [ ] Email/SMS integration

---

## 📞 Support

Check:
1. [README_FEATURES.md](README_FEATURES.md) - Detailed troubleshooting
2. Browser console (F12) - Frontend errors
3. Flask console output - Backend errors
4. [SECURITY.md](SECURITY.md) - Security issues

---

## 📝 License

Open source - modify and deploy freely.

**Latest Update**: March 1, 2026
