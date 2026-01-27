# AI-Powered Chatbot for College / Company Websites (Phase-1)

A simple, production-ready Flask chatbot that answers FAQs with AI-powered semantic matching.

## Features

### User Features
- ✅ **Simple Chat UI** - Clean, responsive popup chat interface
- ✅ **Real-time Responses** - Instant bot replies to user messages
- ✅ **Semantic Matching** - AI finds best-matching FAQ answers
- ✅ **Confidence Scoring** - Shows whether answer is reliable
- ✅ **Graceful Fallback** - Polite messages when answer not found

### Admin Features
- ✅ **Admin Dashboard** - Complete management portal
- ✅ **FAQ Management** - Add, edit, delete FAQs easily
- ✅ **Chat Logs** - View all conversations with confidence scores
- ✅ **Analytics** - Track answer rates and system stats
- ✅ **Unanswered Questions** - Find gaps in your FAQ knowledge base

### AI Features
- ✅ **Semantic Similarity** - Jaccard similarity-based matching
- ✅ **Confidence Threshold** - Only answer if confidence >= 0.7
- ✅ **No Hallucination** - Strictly uses FAQ knowledge base
- ✅ **Full Logging** - Records all interactions for analysis

## Tech Stack
- **Backend**: Python 3 + Flask
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **ORM**: SQLAlchemy
- **Authentication**: Password hashing with Werkzeug

## Project Structure

```
ai_chatbot/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── database.py            # Database initialization
├── models.py              # Database models (Admin, FAQ, ChatLog, etc.)
├── ai_service.py          # AI matching logic
├── requirements.txt       # Python dependencies
│
├── templates/
│   ├── chat.html          # User chat interface
│   ├── admin_login.html   # Admin login page
│   └── admin_dashboard.html # Admin dashboard
│
└── static/
    ├── style.css          # All styling
    └── chat.js            # Chat UI interactions
```

## Quick Start

### 1. Prerequisites
- Python 3.7 or higher
- pip (Python package manager)

### 2. Installation

```bash
# Clone/download the project
cd ai_chatbot

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Application

```bash
# Start the Flask server
python app.py
```

The server will start at: **http://localhost:5000**

### 4. Access the Application

**User Chat**: http://localhost:5000
- Open in any browser
- Chat interface appears as a popup in bottom-right

**Admin Dashboard**: http://localhost:5000/admin/login
- Username: `admin`
- Password: `admin123`

## Configuration

Edit `config.py` to customize:

```python
# Confidence threshold for answering (0.0 to 1.0)
CONFIDENCE_THRESHOLD = 0.7

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Flask secret key (change in production)
SECRET_KEY = 'your-secret-key-change-in-production'
```

## How It Works

### 1. User Sends Message
User types a question in the chat popup.

### 2. Semantic Matching
AI Service compares user message with all FAQ questions using:
- **Jaccard Similarity**: Calculates overlap between question tokens
- **Length Ratio**: Adjusts score based on question lengths
- **Scoring**: Combines both metrics for final similarity score

### 3. Confidence Check
- If confidence >= 0.7 → Use FAQ answer
- If confidence < 0.7 → Use fallback message

### 4. Logging
- User message
- Bot response
- Confidence score
- Matched FAQ (if any)
- Timestamp

### 5. Unanswered Tracking
- Questions with confidence < 0.7 are logged
- Admin can review to improve FAQ coverage

## Admin Features

### Manage FAQs
1. Go to Admin Dashboard → "Manage FAQs"
2. Add new FAQ with question, answer, and category
3. Edit or delete existing FAQs
4. Changes apply immediately

### View Chat Logs
1. Go to "Chat Logs"
2. See all user-bot conversations
3. Check confidence scores
4. Identify frequently asked questions

### Unanswered Questions
1. Go to "Frequently Unanswered Questions"
2. See questions bot couldn't answer well
3. Quick action to add them as new FAQs
4. Prioritized by frequency

### Dashboard Statistics
- Total number of chats
- Total FAQs in database
- Answer rate percentage
- Number of unanswered questions
- Current confidence threshold

## Sample FAQs (Pre-loaded)

The database comes with sample FAQs:
1. Business hours
2. Customer support contact
3. Payment methods
4. Delivery times

Delete or edit these as needed.

## API Endpoints

### User API
- `GET /` - Chat UI
- `POST /api/chat` - Send message, get response

### Admin API
- `POST /admin/login` - Admin login
- `GET /admin/logout` - Admin logout
- `GET /admin/dashboard` - Dashboard page
- `GET /admin/api/stats` - Dashboard statistics
- `GET /admin/api/faqs` - Get all FAQs
- `POST /admin/api/faq` - Create FAQ
- `PUT /admin/api/faq/<id>` - Update FAQ
- `DELETE /admin/api/faq/<id>` - Delete FAQ
- `GET /admin/api/chat-logs` - Get recent chat logs
- `GET /admin/api/unanswered-questions` - Get unanswered questions

## Database Schema

### Admins Table
- id, username, password_hash, created_at

### FAQs Table
- id, question, answer, category, created_at, updated_at

### ChatLogs Table
- id, user_message, bot_response, confidence_score, matched_faq_id, session_id, timestamp

### UnansweredQuestions Table
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
