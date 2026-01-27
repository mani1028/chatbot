# 📚 COMPLETE DOCUMENTATION - AI CHATBOT PROJECT

## Table of Contents
1. [Project Overview](#project-overview)
2. [Quick Start](#quick-start)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Architecture](#architecture)
6. [File Structure](#file-structure)
7. [Code Explanation](#code-explanation)
8. [Database](#database)
9. [API Reference](#api-reference)
10. [Customization](#customization)
11. [Troubleshooting](#troubleshooting)
12. [Deployment](#deployment)

---

## Project Overview

### What This Is
AI-Powered Chatbot for websites that:
- Answers visitor questions from FAQ database
- Uses semantic matching (not just keywords)
- Tracks confidence in answers
- Logs all conversations
- Includes admin dashboard for management

### What This Isn't
- ❌ NO external API required
- ❌ NO billing/payment
- ❌ NO SaaS dependencies
- ❌ NO complex ML models
- ❌ NO hallucinations (strict FAQ-only)

### Tech Stack
- **Backend**: Python 3 + Flask
- **Database**: SQLite (file-based, no setup needed)
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript
- **ORM**: SQLAlchemy
- **Security**: Werkzeug (password hashing)

---

## Quick Start

### The Fastest Way (30 seconds)

**Windows:**
```bash
cd ai_chatbot
run.bat
```

**Mac/Linux:**
```bash
cd ai_chatbot
chmod +x run.sh
./run.sh
```

**Manual:**
```bash
cd ai_chatbot
pip install -r requirements.txt
python app.py
```

Then open: **http://localhost:5000**

---

## Installation

### Prerequisites
- Python 3.7+ (any version 3.7, 3.8, 3.9, 3.10, 3.11, 3.12 works)
- pip (comes with Python)
- 50MB free disk space

### Step-by-Step

#### 1. Navigate to Project
```bash
cd c:\Users\rishi\Desktop\chatbot\ai_chatbot
```

#### 2. Create Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `Flask==2.3.3` - Web framework
- `Flask-SQLAlchemy==3.0.5` - ORM integration
- `SQLAlchemy==2.0.21` - Database ORM
- `Werkzeug==2.3.7` - Security utilities

#### 4. Run Application
```bash
python app.py
```

You should see:
```
==================================================
AI Chatbot Server Starting...
==================================================
Admin Login: http://localhost:5000/admin/login
Username: admin
Password: admin123
==================================================
 * Running on http://127.0.0.1:5000
```

---

## Usage

### For Visitors/Users

#### Accessing Chat
1. Open **http://localhost:5000** in browser
2. Chat popup appears in bottom-right corner
3. Type your question and press Enter
4. Bot responds with answer or fallback message
5. Minimize with − button, reopen with 💬 button

#### Example Questions
Try these (pre-loaded in database):
- "What are your business hours?"
- "How can I contact support?"
- "What payment methods do you accept?"
- "How long does delivery take?"

#### Understanding Confidence Badges
- ✅ Confidence >= 0.70 (high confidence, FAQ answer)
- ❓ Confidence < 0.70 (low confidence, fallback message)

---

### For Admins

#### Logging In
1. Open **http://localhost:5000/admin/login**
2. Username: `admin`
3. Password: `admin123`
4. Click "Login"

#### Dashboard Navigation
Left sidebar has 4 tabs:
- **Dashboard** - Overview statistics
- **Manage FAQs** - Add/Edit/Delete
- **Chat Logs** - View conversations
- **Unanswered Q's** - Find FAQ gaps

#### Adding an FAQ
1. Click "Manage FAQs"
2. Fill in:
   - **Question**: The question users ask
   - **Answer**: Your response
   - **Category**: e.g., "Billing", "Support"
3. Click "Add FAQ"
4. It appears in chat immediately

#### Editing an FAQ
1. In FAQ list, click "Edit" button
2. Update fields in modal
3. Click "Save Changes"

#### Deleting an FAQ
1. In FAQ list, click "Delete" button
2. Confirm deletion
3. FAQ removed from database

#### Viewing Chat Logs
1. Click "Chat Logs" tab
2. See recent conversations
3. Check confidence scores
4. See which FAQs were used

#### Finding Unanswered Questions
1. Click "Unanswered Q's" tab
2. See questions bot couldn't answer well
3. Sorted by frequency
4. Quick "Add as FAQ" buttons

#### Dashboard Statistics
1. Click "Dashboard" tab
2. See:
   - Total number of chats
   - Total FAQs in system
   - Answer rate percentage
   - Number of unanswered questions
   - Current confidence threshold

---

## Architecture

### How It Works (High Level)

```
User Message
    ↓
Flask API Endpoint (/api/chat)
    ↓
AI Service (Semantic Matching)
    ↓ Calculate similarity with all FAQs
    ↓ Find best match
    ↓ Check confidence threshold
    ↓
Generate Response
    ↓ If confident: Use FAQ answer
    ↓ If not: Use fallback message
    ↓
Log to Database
    ↓ Save message, answer, confidence, timestamp
    ↓ Mark if unanswered
    ↓
Return to Frontend
    ↓
Display in Chat UI
```

### Semantic Matching Explained

#### The Algorithm
1. **Tokenize** both texts (split into words)
2. **Find intersection** (common words)
3. **Find union** (all unique words)
4. **Calculate Jaccard** = intersection / union
5. **Adjust by length** (proportional length bonus)
6. **Final score** = 70% Jaccard + 30% Length

#### Example
```
User: "Do you have business hours?"
FAQ 1: "What are your business hours?"

Step 1: Tokenize
User tokens: {do, you, have, business, hours}
FAQ tokens: {what, are, your, business, hours}

Step 2: Intersection (common)
Common: {business, hours} = 2 words

Step 3: Union (all unique)
Union: {do, you, have, what, are, your, business, hours} = 8 words

Step 4: Jaccard
Jaccard = 2/8 = 0.25

Step 5: Length ratio
User length (5) vs FAQ length (5) = 5/5 = 1.0

Step 6: Final score
Score = 0.25 * 0.7 + 1.0 * 0.3 = 0.175 + 0.3 = 0.475

Step 7: More tokens = higher score
(This is simplified; actual algorithm is more sophisticated)

Result: 0.475 < 0.7 threshold
→ Use fallback message
```

---

## File Structure

### Root Level

| File | Size | Purpose |
|------|------|---------|
| `app.py` | 420 lines | Main Flask app, routes, startup |
| `config.py` | 35 lines | Settings, credentials, paths |
| `database.py` | 25 lines | SQLAlchemy setup |
| `models.py` | 145 lines | Database table definitions |
| `ai_service.py` | 215 lines | Semantic matching logic |
| `requirements.txt` | 4 lines | Python dependencies |
| `README.md` | Full docs | Complete documentation |
| `QUICK_START.md` | Quick guide | Fast setup guide |
| `PROJECT_SUMMARY.md` | Overview | Project summary |
| `run.bat` | Windows script | Startup for Windows |
| `run.sh` | Linux script | Startup for Mac/Linux |

### Templates Directory

| File | Purpose |
|------|---------|
| `chat.html` | User-facing chat popup UI |
| `admin_login.html` | Admin login page |
| `admin_dashboard.html` | Admin control panel |

### Static Directory

| File | Size | Purpose |
|------|------|---------|
| `style.css` | 600 lines | All styling (mobile responsive) |
| `chat.js` | 200 lines | Chat interactions (Fetch API) |

### Generated Files

| File | Purpose |
|------|---------|
| `chatbot.db` | SQLite database (created on first run) |
| `.venv/` | Virtual environment (if created with venv) |

---

## Code Explanation

### app.py - Main Application

#### Initialization
```python
from flask import Flask
from database import db, init_db

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatbot.db'
db.init_app(app)
```

#### Chat Endpoint
```python
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    
    # Get response from AI
    response = AIService.get_bot_response(message, session['session_id'])
    
    return jsonify({
        'success': True,
        'message': response['response'],
        'confidence': response['confidence'],
        'is_answered': response['is_answered']
    })
```

#### Admin Routes
```python
@app.route('/admin/login', methods=['GET', 'POST'])
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # Returns admin dashboard page
    
@app.route('/admin/api/faqs', methods=['GET'])
@login_required
def get_faqs():
    # Returns all FAQs as JSON
    
@app.route('/admin/api/faq', methods=['POST'])
@login_required
def create_faq():
    # Creates new FAQ
```

### ai_service.py - AI Logic

#### Similarity Calculation
```python
@staticmethod
def calculate_similarity(query, faq_question):
    query_tokens = AIService.tokenize(query)
    faq_tokens = AIService.tokenize(faq_question)
    
    # Jaccard similarity
    intersection = len(query_tokens & faq_tokens)
    union = len(query_tokens | faq_tokens)
    jaccard_score = intersection / union if union > 0 else 0
    
    # Apply length ratio
    length_ratio = min(len(query_tokens), len(faq_tokens)) / \
                   max(len(query_tokens), len(faq_tokens))
    boosted_score = jaccard_score * 0.7 + length_ratio * 0.3
    
    return min(boosted_score, 1.0)
```

#### Main Response Logic
```python
@staticmethod
def get_bot_response(user_message, session_id):
    # Find best matching FAQ
    faq, confidence = AIService.find_best_match(user_message)
    
    # Check threshold
    if confidence >= CONFIDENCE_THRESHOLD and faq:
        response = faq.answer
        is_answered = True
    else:
        response = random.choice(FALLBACK_MESSAGES)
        is_answered = False
    
    # Log interaction
    chat_log = ChatLog(
        user_message=user_message,
        bot_response=response,
        confidence_score=confidence,
        matched_faq_id=faq.id if is_answered else None,
        session_id=session_id
    )
    db.session.add(chat_log)
    db.session.commit()
    
    return {
        'response': response,
        'confidence': round(confidence, 2),
        'is_answered': is_answered
    }
```

### models.py - Database Models

#### FAQ Model
```python
class FAQ(db.Model):
    __tablename__ = 'faqs'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False, unique=True)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), default='General')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
```

#### ChatLog Model
```python
class ChatLog(db.Model):
    __tablename__ = 'chat_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    matched_faq_id = db.Column(db.Integer, db.ForeignKey('faqs.id'))
    session_id = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
```

### chat.js - Frontend Logic

#### Sending Messages
```javascript
function sendMessage() {
    const message = document.getElementById('messageInput').value.trim();
    
    if (!message) return;
    
    displayUserMessage(message);
    displayTypingIndicator();
    
    fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: message})
    })
    .then(response => response.json())
    .then(data => {
        removeTypingIndicator();
        displayBotMessage(data.message, data.confidence, data.is_answered);
    });
}
```

#### Displaying Messages
```javascript
function displayBotMessage(message, confidence, isAnswered) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    const badge = isAnswered ? '✅' : '❓';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(message)}</p>
            <div class="confidence-badge">
                ${badge} Confidence: ${(confidence * 100).toFixed(0)}%
            </div>
        </div>
    `;
    
    document.getElementById('chatMessages').appendChild(messageDiv);
    scrollToBottom();
}
```

---

## Database

### Schema Overview

```sql
-- Admins Table
CREATE TABLE admins (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- FAQs Table
CREATE TABLE faqs (
    id INTEGER PRIMARY KEY,
    question VARCHAR(500) UNIQUE NOT NULL,
    answer TEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'General',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Chat Logs Table
CREATE TABLE chat_logs (
    id INTEGER PRIMARY KEY,
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    confidence_score FLOAT NOT NULL,
    matched_faq_id INTEGER,
    session_id VARCHAR(100) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (matched_faq_id) REFERENCES faqs(id)
);

-- Unanswered Questions Table
CREATE TABLE unanswered_questions (
    id INTEGER PRIMARY KEY,
    question TEXT NOT NULL,
    times_asked INTEGER DEFAULT 1,
    first_asked DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_asked DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Querying Database

```python
# Get all FAQs
faqs = FAQ.query.all()

# Get specific FAQ
faq = FAQ.query.get(1)

# Get answered chats
answered = ChatLog.query.filter(ChatLog.matched_faq_id.isnot(None)).all()

# Get unanswered questions
unanswered = UnansweredQuestion.query.order_by(
    UnansweredQuestion.times_asked.desc()
).all()

# Count statistics
total_chats = ChatLog.query.count()
answer_rate = (answered_count / total_chats) * 100
```

---

## API Reference

### User API

#### GET / - Main Chat Page
```
GET http://localhost:5000/
```
Returns HTML for chat interface.

#### POST /api/chat - Send Message
```
POST http://localhost:5000/api/chat

Request Body:
{
    "message": "What are your business hours?"
}

Response:
{
    "success": true,
    "message": "We are open Monday to Friday, 9 AM to 6 PM.",
    "confidence": 0.85,
    "is_answered": true
}
```

### Admin API

#### GET/POST /admin/login - Login
```
GET http://localhost:5000/admin/login
→ Returns login page

POST http://localhost:5000/admin/login
Body: {
    "username": "admin",
    "password": "admin123"
}
→ Authenticates and redirects to dashboard
```

#### GET /admin/dashboard - Admin Dashboard
```
GET http://localhost:5000/admin/dashboard
→ Returns admin dashboard page (requires login)
```

#### GET /admin/api/faqs - Get All FAQs
```
GET http://localhost:5000/admin/api/faqs

Response:
{
    "faqs": [
        {
            "id": 1,
            "question": "What are your hours?",
            "answer": "9 AM to 6 PM",
            "category": "General",
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:00"
        }
    ]
}
```

#### POST /admin/api/faq - Create FAQ
```
POST http://localhost:5000/admin/api/faq

Request Body:
{
    "question": "Do you ship internationally?",
    "answer": "Yes, we ship worldwide.",
    "category": "Shipping"
}

Response:
{
    "success": true,
    "message": "FAQ added successfully",
    "faq_id": 5
}
```

#### PUT /admin/api/faq/<id> - Update FAQ
```
PUT http://localhost:5000/admin/api/faq/1

Request Body:
{
    "question": "Updated question?",
    "answer": "Updated answer.",
    "category": "Updated"
}

Response:
{
    "success": true,
    "message": "FAQ updated successfully"
}
```

#### DELETE /admin/api/faq/<id> - Delete FAQ
```
DELETE http://localhost:5000/admin/api/faq/1

Response:
{
    "success": true,
    "message": "FAQ deleted successfully"
}
```

#### GET /admin/api/chat-logs - Get Chat Logs
```
GET http://localhost:5000/admin/api/chat-logs?limit=50

Response:
{
    "logs": [
        {
            "id": 1,
            "user_message": "What are your hours?",
            "bot_response": "We are open 9 AM to 6 PM.",
            "confidence_score": 0.85,
            "matched_faq_id": 1,
            "session_id": "uuid...",
            "timestamp": "2024-01-28T14:30:00",
            "is_answered": true
        }
    ]
}
```

#### GET /admin/api/unanswered-questions - Get Unanswered
```
GET http://localhost:5000/admin/api/unanswered-questions?limit=50

Response:
{
    "questions": [
        {
            "id": 1,
            "question": "How do I return items?",
            "times_asked": 5,
            "first_asked": "2024-01-20T10:00:00",
            "last_asked": "2024-01-28T15:00:00"
        }
    ]
}
```

#### GET /admin/api/stats - Dashboard Statistics
```
GET http://localhost:5000/admin/api/stats

Response:
{
    "total_chats": 150,
    "total_faqs": 10,
    "answered_chats": 135,
    "answer_rate": 90.0,
    "unanswered_questions": 5,
    "confidence_threshold": 0.7
}
```

---

## Customization

### Change Admin Credentials

Edit `config.py`:
```python
ADMIN_USERNAME = 'myusername'
ADMIN_PASSWORD = 'mypassword'
```

Restart app for changes to take effect.

### Change Confidence Threshold

Edit `config.py`:
```python
CONFIDENCE_THRESHOLD = 0.6  # More lenient
CONFIDENCE_THRESHOLD = 0.8  # More strict
```

Lower = bot answers more questions (more likely to be wrong)
Higher = bot answers fewer questions (more accurate)

### Change Fallback Messages

Edit `config.py`:
```python
FALLBACK_MESSAGES = [
    "I'm not sure about that.",
    "Can you rephrase your question?",
    "Please contact our support team.",
]
```

### Change Chat UI Colors

Edit `static/style.css`:

Find all instances of `#667eea` (purple) and replace:
```css
/* Original */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

/* Change to your colors */
background: linear-gradient(135deg, #FF6B6B 0%, #FF8E72 100%);
```

Common colors:
- Blue: `#3498db`
- Green: `#2ecc71`
- Red: `#e74c3c`
- Purple: `#9b59b6`

### Improve Matching Algorithm

Edit `ai_service.py` - `calculate_similarity()` method:

Current: Simple Jaccard similarity
Better options:
- Levenshtein distance
- TF-IDF similarity
- Word embeddings (spaCy, gensim)
- Neural networks

Example with Levenshtein:
```python
from difflib import SequenceMatcher

def calculate_similarity(query, faq_question):
    ratio = SequenceMatcher(None, query.lower(), 
                           faq_question.lower()).ratio()
    return ratio
```

### Add Multilingual Support

```python
from googletrans import Translator

def translate_to_english(text, lang='auto'):
    translator = Translator()
    result = translator.translate(text, src_lang=lang, dest_lang='en')
    return result['text']

# In get_bot_response:
english_message = translate_to_english(user_message)
```

---

## Troubleshooting

### Issue: Port 5000 Already in Use

**Error**: `Address already in use`

**Solution 1**: Kill existing process
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Mac/Linux
lsof -i :5000
kill -9 <PID>
```

**Solution 2**: Use different port
```python
# In app.py, change last line:
app.run(host='0.0.0.0', port=5001, debug=DEBUG)
```

---

### Issue: Admin Login Fails

**Problem**: "Invalid credentials" after entering correct password

**Solution**:
1. Delete `chatbot.db`
2. Restart app - database recreates
3. Default credentials work again: `admin` / `admin123`

Or update password:
```python
# In app.py, right after db.create_all():
admin = Admin.query.filter_by(username='admin').first()
if admin:
    admin.set_password('newpassword')
    db.session.commit()
```

---

### Issue: Chatbot Not Responding

**Error**: Message stuck on "thinking", never gets response

**Check 1**: Is server running?
```bash
# Should see "Running on http://127.0.0.1:5000"
```

**Check 2**: Browser console (F12) for errors
- Network tab - check `/api/chat` response

**Check 3**: Flask server logs
- Watch for error messages

**Fix**: Restart server
```bash
# Stop (Ctrl+C) and run again
python app.py
```

---

### Issue: Database Lock Error

**Error**: `database is locked`

**Cause**: Multiple processes accessing SQLite simultaneously

**Solution**:
1. Ensure only one `python app.py` running
2. Use PostgreSQL for production with concurrent access
3. Or use WAL mode in SQLite

---

### Issue: 404 Not Found on Admin Pages

**Error**: `/admin/login` → 404

**Fix**: Ensure you're accessing correct URL
- User chat: `http://localhost:5000`
- Admin login: `http://localhost:5000/admin/login`
- Dashboard: `http://localhost:5000/admin/dashboard`

---

### Issue: JavaScript Errors in Browser

**Error**: Chat not working, console shows errors

**Check**: Browser F12 console
- CORS errors: Unlikely with localhost
- Network errors: Check Flask is running
- Syntax errors: Check static/chat.js

**Fix**:
1. Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
2. Clear browser cache
3. Check JavaScript console for details

---

### Issue: Changes Don't Appear

**Problem**: Updated FAQ doesn't appear in chat

**Cause**: Browser cache or session issue

**Fix**:
1. Hard refresh browser: `Ctrl+Shift+R`
2. Open new incognito window
3. Logout and login again

---

## Deployment

### Deployment Checklist

- [ ] Change `SECRET_KEY` in `config.py`
- [ ] Change admin password
- [ ] Set `DEBUG = False` in `config.py`
- [ ] Test all FAQs
- [ ] Test admin panel
- [ ] Back up database
- [ ] Set up monitoring/logging
- [ ] Configure web server (Gunicorn/Nginx)
- [ ] Set up HTTPS/SSL
- [ ] Test on production server
- [ ] Document maintenance procedures

### Using Gunicorn

Gunicorn is a production WSGI server for Flask.

**Installation:**
```bash
pip install gunicorn
```

**Running:**
```bash
# 4 worker processes
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# With logs
gunicorn -w 4 -b 0.0.0.0:5000 --access-logfile - app:app
```

### Using Nginx (Reverse Proxy)

Basic Nginx config (`/etc/nginx/sites-available/chatbot`):

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

### Using Docker (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.9
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

Build and run:
```bash
docker build -t ai-chatbot .
docker run -p 5000:5000 ai-chatbot
```

---

## Performance Optimization

### For More FAQs

If you have 1000+ FAQs, consider:

1. **Caching**: Store frequently matched FAQs
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_similar_faqs(query):
    # Returns cached results
```

2. **Indexing**: Database indexing
```python
class FAQ(db.Model):
    question = db.Column(db.String(500), index=True)
```

3. **Full-text search**: SQLite FTS or PostgreSQL
```sql
CREATE VIRTUAL TABLE faq_search USING fts5(question, answer);
```

### For More Users

1. Use **Gunicorn** with multiple workers
2. Set up **load balancer** (Nginx, HAProxy)
3. Use **PostgreSQL** instead of SQLite
4. Add **Redis cache**
5. Monitor with **prometheus/grafana**

---

## Security Best Practices

### Before Production Deployment

1. **Change Secret Key**
```python
# config.py
SECRET_KEY = 'generate-random-string-here'
# Use: python -c "import secrets; print(secrets.token_urlsafe(32))"
```

2. **Change Admin Password**
```python
# config.py
ADMIN_PASSWORD = 'strong-password-here'
```

3. **Disable Debug Mode**
```python
# config.py
DEBUG = False
```

4. **Use HTTPS**
```
Get SSL certificate from Let's Encrypt
Use Nginx/Apache for HTTPS termination
```

5. **Add Rate Limiting**
```python
from flask_limiter import Limiter
limiter = Limiter(app, key_func=lambda: request.remote_addr)

@app.route('/api/chat', methods=['POST'])
@limiter.limit("10/minute")  # 10 requests per minute
def chat():
    pass
```

6. **Validate Input**
```python
# Already done but ensure:
user_message = data.get('message', '').strip()
if not user_message or len(user_message) > 1000:
    return error
```

7. **Set up Database Backups**
```bash
# Daily backup
0 2 * * * cp /app/chatbot.db /backups/chatbot-$(date +%Y%m%d).db
```

---

This documentation covers everything you need to use, customize, deploy, and troubleshoot your AI Chatbot!

For quick reference, see: **QUICK_START.md**
For project overview, see: **PROJECT_SUMMARY.md**
For full readme, see: **README.md**
