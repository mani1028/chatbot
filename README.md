# AI-Powered Chatbot for College / Company Websites (Phase-1)

A simple, production-ready Flask chatbot that answers FAQs with AI-powered semantic matching.

## Features

### User Features
- ✅ **Simple Chat UI** - Clean, responsive popup chat interface
- ✅ **Real-time Responses** - Instant bot replies to user messages
- ✅ **Semantic Matching** - AI finds best-matching FAQ answers
- ✅ **Confidence Scoring** - Shows whether answer is reliable

# SaaS Conversation Automation Platform

## Overview

This project is a modular, multi-tenant SaaS chatbot platform for rapid deployment of sector-specific conversational bots (e.g., Hospital, Travel, etc.). It features intent detection, workflow automation, dynamic response building, and multi-tenancy support.

---

## 🏗️ Architecture

| Component             | Location                        | Description                                                      |
|-----------------------|----------------------------------|------------------------------------------------------------------|
| **Intent Engine**     | core/intent_engine.py            | Fuzzy matching, confidence scoring for user messages.             |
| **Decision Layer**    | services/intent_service.py       | Routes between Info, Action (Workflows), and Handoff.             |
| **Workflow System**   | workflows/handler.py             | Dynamic logic (e.g., get_price) called by intents.                |
| **Response Builder**  | services/response_builder.py     | Replaces {placeholders} using ClientConfig.                       |
| **Config/Data**       | models/intent.py, models/site.py | DB supports sector, site_id, client_config.                       |
| **JSON Importer**     | scripts/import_intents.py        | Loads sector packs (e.g., Hospital) into the DB.                  |
| **Multi-Tenant API**  | routes/chat_routes.py            | Endpoints require site_id, enforce domain whitelisting.           |

---

## 🚀 Quick Start Guide

### 1. Clone & Install

```bash
git clone <repo-url>
cd chatbot
pip install -r requirements.txt
```

### 2. Reset & Initialize Database

**Delete old DB (if exists):**

- On Windows:
    ```
    del instance\chatbot.db
    ```
- On Linux/Mac:
    ```
    rm instance/chatbot.db
    ```

**Create tables:**

```bash
python app.py
# Wait for 'AI Chatbot Server Starting...' then stop (CTRL+C)
```

### 3. Create a Tenant (Site)

```bash
python init_site.py
# Should print: Successfully created Site ID 1
```

### 4. Import Sector Template (e.g., Hospital)

```bash
python scripts/import_intents.py intent_templates/hospital_intents.json --client 1
```

**Expected Output:**
```
Created intent: VISITING_HOURS (site 1)
    + phrase: hospital timings
Created intent: CHECK_PRICE (site 1)
    + phrase: what is consultation fee
    + workflow: get_price
    + client_config key: consultation_price (empty)
Import complete
```

### 5. Configure Client Data

Set config values (e.g., consultation price):

```bash
python
```

```python
from app import app
from database import db
from models import ClientConfig

with app.app_context():
        conf = ClientConfig.query.filter_by(client_id=1, key='consultation_price').first()
        if conf:
                conf.value = "500"
                db.session.commit()
                print("Price updated!")
exit()
```

### 6. Run the Server

```bash
python app.py
```

### 7. Test the API

```bash
curl -X POST http://localhost:5000/api/chat \
    -H "Content-Type: application/json" \
    -H "Referer: http://localhost/" \
    -d '{
        "site_id": 1,
        "message": "What is the consultation fee?"
    }'
```

**Expected Response:**
```json
{
    "reply": "Consultation fee is ₹500",
    "intent": "CHECK_PRICE",
    "intent_type": "action"
}
```

---

## 🧩 Extending the Platform

- **Add a New Sector:**
    - Create a new JSON template (e.g., travel_intents.json).
    - Import with `python scripts/import_intents.py intent_templates/travel_intents.json --client 2`.
- **Add/Change Workflows:**
    - Edit workflows/handler.py to add new logic.
- **Multi-Tenancy:**
    - Each site (tenant) is isolated by site_id.
    - API endpoints require site_id and validate domain.

---

## 🔮 Roadmap

- **Phase 4:** Super Admin UI to upload JSONs and create Sites (no CLI needed).
- **Phase 5:** Client Admin UI for clients to update their config (e.g., prices, timings) without seeing intent logic.

---

## 📁 Project Structure

```
chatbot/
├── app.py
├── config.py
├── database.py
├── core/
│   ├── intent_engine.py
│   ├── synonyms.py
│   └── tokenizer.py
├── models/
│   ├── __init__.py
│   ├── chat_log.py
│   ├── intent.py
│   └── site.py
├── routes/
│   └── chat_routes.py
├── scripts/
│   ├── apply_migration.py
│   ├── import_intents.py
│   └── migrations/
├── services/
│   ├── chat_service.py
│   ├── intent_service.py
│   └── response_builder.py
├── workflows/
│   └── handler.py
├── static/
├── templates/
├── instance/
│   └── chatbot.db
└── intent_templates/
        └── hospital_intents.json
```

---

## 🛠️ Troubleshooting

- **DB Errors:** Delete instance/chatbot.db and re-run steps 2-4.
- **Import Errors:** Ensure your JSON matches the schema in intent_templates/hospital_intents.json.
- **API 400/403:** Check site_id and Referer header.

---

## 📝 License

This project is for demonstration and prototyping. For production, review security, scalability, and compliance requirements.
- id, question, times_asked, first_asked, last_asked

## Security Notes

⚠️ **Important for Production**:
1. Change `SECRET_KEY` in config.py
2. Change default admin password
3. Use HTTPS (reverse proxy like Nginx)
4. Add rate limiting
5. Add CSRF protection
6. Use environment variables for secrets
7. Enable database backups

## Performance Tips

1. **FAQ Size**: Works efficiently with 100-1000 FAQs
2. **Similarity Algorithm**: O(n) complexity, scales well
3. **Database**: SQLite works for small-medium deployments
4. **Caching**: Can be added for frequently matched FAQs
5. **Concurrent Users**: Flask development server handles ~10 concurrent; use Gunicorn for production

## Troubleshooting

### Chatbot not responding?
- Check if Flask server is running
- Check browser console for errors (F12)
- Verify `/api/chat` endpoint is accessible

### Admin login fails?
- Default credentials: `admin` / `admin123`
- Check if database file exists (chatbot.db)

### Database issues?
- Delete `chatbot.db` to reset
- App will recreate it automatically
- Sample FAQs will be added

### Port already in use?
```bash
# Use different port
python -c "import app; app.app.run(port=5001)"
```

## Customization

### Change Confidence Threshold
```python
# In config.py
CONFIDENCE_THRESHOLD = 0.6  # More lenient (0.0-1.0)
```

### Add Fallback Messages
```python
# In config.py
FALLBACK_MESSAGES = [
    "Your custom message 1",
    "Your custom message 2",
]
```

### Improve Matching Algorithm
Edit `AIService.calculate_similarity()` in `ai_service.py` for:
- Different tokenization
- Advanced NLP (spaCy, NLTK)
- Word embeddings (gensim)
- Phrase matching

## Deployment

### Local/Development
```bash
python app.py
```

### Production (Gunicorn)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker (Optional)
```bash
docker build -t ai-chatbot .
docker run -p 5000:5000 ai-chatbot
```

## License

Open source - Feel free to use and modify

## Support

For issues or questions:
1. Check README troubleshooting section
2. Review admin dashboard statistics
3. Check browser console for errors
4. Review Flask server logs

---

**Ready to chat!** 🚀 Open http://localhost:5000 and start testing.
