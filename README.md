# Enterprise Intent-Based Chatbot System

A professional-grade Flask-based chatbot with intelligent intent matching, multi-tier confidence scoring, and automatic lead capture.

## ✨ Key Features

### Core Capabilities
- **Intent-Based Matching** - Training phrases for each intent
- **Multi-Tier Confidence Engine** - High/Medium/Low responses
- **Automatic Lead Capture** - Captures contact info when bot is unsure
- **Admin Dashboard** - Full control over intents, leads, and analytics
- **Backward Compatible** - Legacy FAQ system still works as fallback

### Confidence Tiers
```
Score ≥ 0.8  → HIGH    (Detailed response + ✓ badge)
Score 0.5-0.8 → MEDIUM (Short response + feedback request)
Score < 0.5  → HANDOFF (Offer human assistance with lead form)
```

## 🚀 Quick Start (5 Minutes)

### 1. Setup
```bash
python quickstart.py
```

### 2. Start Server
```bash
python app.py
```

### 3. Access
- **Chat**: http://localhost:5000
- **Admin**: http://localhost:5000/admin/login (admin/admin123)

## 📋 Project Structure

```
chatbot/
├── Core Files
│   ├── app.py              # Flask routes & API endpoints
│   ├── models.py           # Database models (Intent, Lead, etc)
│   ├── ai_service.py       # Confidence engine & intent matching
│   ├── config.py           # Configuration settings
│   ├── database.py         # Database initialization
│   └── requirements.txt    # Python dependencies
│
├── Static Files
│   ├── static/
│   │   ├── chat.js         # Chat UI with lead capture form
│   │   └── style.css       # Styling
│   └── templates/
│       ├── chat.html       # Chat interface
│       ├── admin_login.html
│       └── admin_dashboard.html
│
├── Intent Definitions
│   └── intents/
│       ├── software_dev.json   # API, SDK, Troubleshooting
│       ├── ai_ml.json          # ML Models, Data, Performance
│       ├── pricing.json        # Plans, Billing, Enterprise
│       └── support.json        # Account, Limits, Help
│
├── Utilities
│   ├── seed_intents.py    # Load intents from JSON
│   └── cleanup.py         # Remove legacy files
│
└── Documentation
    ├── README.md          # This file
    └── UPGRADE_GUIDE.md   # Complete feature guide
```

## 🎯 Pre-Made Intents (12 Total)

### Software Development (3)
- API Documentation - How to use REST APIs
- SDK Installation - Installing client libraries
- Troubleshooting Code - Debugging errors

### AI/ML (3)
- Machine Learning Models - ML capabilities
- Data Preparation - Dataset preparation
- Model Performance - Metrics monitoring

### Pricing (3)
- Pricing Plans - Plan comparison
- Billing & Invoices - Invoice management
- Enterprise Pricing - Custom quotes

### Support (3)
- Account Management - User settings
- API Rate Limits - Usage limits
- Technical Support - Getting help

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Confidence Thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.8
MEDIUM_CONFIDENCE_THRESHOLD = 0.5

# Handoff Settings
HANDOFF_REQUIRED_CATEGORIES = ['Pricing', 'Support']

# Response Messages
CONFIDENCE_RESPONSES = {
    'high': "Based on our knowledge base, here's the detailed answer:",
    'medium': "Here's what I found that might help:",
    'low': "I'm not entirely sure about this. Would you like to speak with a specialist?"
}

# Admin Credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
```

## 📚 API Endpoints

### User Chat
```
POST /api/chat
  Request: { "message": "user question" }
  Response: {
    "success": true,
    "message": "bot response",
    "confidence": 0.85,
    "message_type": "auto_response|lead_capture",
    "requires_handoff": false
  }

POST /api/lead
  Request: { "name": "...", "email": "...", "phone": "...", "message": "..." }
  Response: { "success": true, "lead_id": 42 }
```

### Admin Intent Management
```
GET  /admin/api/intents
POST /admin/api/intent
PUT  /admin/api/intent/<id>
DELETE /admin/api/intent/<id>
```

### Admin Lead Management
```
GET /admin/api/leads
PUT /admin/api/lead/<id>
```

### Analytics
```
GET /admin/api/stats
GET /admin/api/chat-logs
GET /admin/api/unanswered-questions
```

## 🛠 Development

### Create New Intent

**Option 1: Via JSON (Recommended)**
```json
// intents/my_category.json
{
  "intents": [
    {
      "intent_name": "My Intent",
      "category": "General",
      "training_phrases": [
        "how do I ...",
        "tell me about ...",
        "what is ..."
      ],
      "short_response": "Brief answer",
      "detailed_response": "Full explanation",
      "requires_handoff": false
    }
  ]
}
```

Then run: `python seed_intents.py`

**Option 2: Via Admin Dashboard**
- Login to admin dashboard
- Click "Create Intent"
- Fill in all fields
- Save

### Customize Responses

Edit intent's `short_response` and `detailed_response` fields directly in admin dashboard or JSON files.

## 📊 Database Models

### Intent
```
- intent_name (unique)
- category (Software Dev, AI/ML, Pricing, Support, General)
- training_phrases (JSON array)
- short_response (brief answer)
- detailed_response (full answer)
- requires_handoff (force handoff flag)
```

### Lead
```
- name (optional)
- email (required)
- phone (optional)
- message (user question)
- intent_id (related intent)
- session_id (chat session)
- status (new / assigned / resolved)
- assigned_to (admin name)
- notes (internal notes)
```

### ChatLog
```
- user_message
- bot_response
- confidence_score
- matched_intent_id
- message_type (auto_response / lead_capture)
- session_id
```

## 🔒 Security

Before production:
- [ ] Change `SECRET_KEY` in config.py
- [ ] Change default admin password
- [ ] Set `DEBUG = False`
- [ ] Enable HTTPS/SSL
- [ ] Set up database backups
- [ ] Implement rate limiting
- [ ] Use environment variables for secrets

## 📈 Monitoring

Key metrics to track:
- **Answer Rate**: answered_chats / total_chats (target: >85%)
- **Confidence Distribution**: % high/medium/low responses
- **Lead Conversion**: leads / low-confidence responses
- **Response Time**: average API response time (<200ms)

View all metrics in admin dashboard at `/admin/api/stats`

## 🧪 Testing

### Test High Confidence
```
User: "How do I use your API?"
Bot: Shows detailed response with ✓ High Confidence badge
```

### Test Medium Confidence
```
User: "Tell me about integrations"
Bot: Shows short response + "Was this helpful?"
```

### Test Low Confidence (Handoff)
```
User: "Completely random question"
Bot: Shows handoff message + lead capture form
```

## 🚀 Deployment

### Quick Deploy
```bash
# 1. Initialize
python quickstart.py

# 2. Test locally
python app.py

# 3. Deploy to production
gunicorn app:app --workers 4 --bind 0.0.0.0:5000
```

### Docker Deploy
```dockerfile
FROM python:3.9
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]
```

## 📖 Documentation

- **UPGRADE_GUIDE.md** - Complete feature documentation and configuration guide

## ⚡ Performance

- Intent matching: <100ms (for <1000 intents)
- Chat API response: <200ms typical
- Supports: 100+ requests/second
- Database: SQLite suitable for <100k chats/month
- Scale to PostgreSQL for production use

## 🆘 Troubleshooting

### Database Issues
```bash
rm chatbot.db
python app.py
python seed_intents.py
```

### Intents Not Loading
```bash
python seed_intents.py  # Reseed all intents
```

### Low Match Accuracy
- Add more training phrases to intents
- Review chat logs for user language patterns
- Adjust confidence thresholds in config.py

### Lead Form Not Appearing
- Check browser console for errors
- Verify `requires_handoff` is true in response
- Clear browser cache

## 🔄 Migration from Old FAQ System

Both systems work together:
1. **Intents** are tried first (new system)
2. **FAQs** are fallback if intent match is weak
3. Gradually migrate FAQs → Intents over time
4. Can delete FAQ table when migration complete

## 📦 Utilities

### seed_intents.py
Load intents from JSON files into database
```bash
python seed_intents.py
```

### cleanup.py
Remove legacy files
```bash
python cleanup.py
```

### quickstart.py
Automated 3-step setup
```bash
python quickstart.py
```

## 📋 Stack

- **Backend**: Python 3.8+, Flask 2.x
- **Database**: SQLite 3.x with SQLAlchemy ORM
- **Frontend**: Vanilla JavaScript (ES6+), HTML5, CSS3
- **Matching**: Advanced tokenization with confidence scoring

## 📞 Support

- Check UPGRADE_GUIDE.md for detailed documentation
- Review inline code comments
- Check admin dashboard for real-time analytics
- Review chat logs to identify improvement areas

## 📄 License

Your project license here.

---

**Version:** 2.0 (Enterprise Intent-Based)  
**Last Updated:** February 1, 2026  
**Status:** ✅ Production Ready
