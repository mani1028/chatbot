# 👨‍💻 DEVELOPER'S GUIDE

## For Developers Who Want to Extend/Modify the Project

---

## Code Organization

### Backend Flow

```
User sends message via chat.html
                ↓
JavaScript (chat.js) sends POST /api/chat
                ↓
Flask app.py receives request
                ↓
Calls AIService.get_bot_response()
                ↓
AIService calculates similarity with all FAQs
                ↓
Finds best match and checks confidence threshold
                ↓
Logs to database (ChatLog model)
                ↓
Returns JSON response
                ↓
JavaScript displays in chat UI
```

### Key Classes and Methods

#### AIService Class (`ai_service.py`)

```python
AIService.tokenize(text)
# Splits text into words
# Used by: calculate_similarity

AIService.calculate_similarity(query, faq_question)
# Returns: float (0.0 to 1.0)
# Implementation: Jaccard similarity + length ratio
# Used by: find_best_match

AIService.find_best_match(user_message)
# Returns: tuple (FAQ object or None, confidence_score)
# Loops through all FAQs calling calculate_similarity
# Used by: get_bot_response

AIService.get_bot_response(user_message, session_id)
# Returns: dict with response, confidence, is_answered
# Main entry point from Flask routes
# Logs to ChatLog and UnansweredQuestion tables

AIService.add_faq(question, answer, category)
# Adds new FAQ to database
# Used by: /admin/api/faq POST route

AIService.get_all_faqs()
# Returns: list of all FAQ dicts
# Used by: /admin/api/faqs GET route

AIService.get_chat_logs(limit)
# Returns: list of recent chat logs
# Used by: /admin/api/chat-logs GET route

AIService.get_unanswered_questions(limit)
# Returns: list of frequently unanswered questions
# Used by: /admin/api/unanswered-questions GET route
```

#### Flask Routes (`app.py`)

```python
GET /
# Returns: chat.html template
# Purpose: User-facing chat interface

POST /api/chat
# Expects: JSON body with 'message'
# Returns: JSON with bot response
# Calls: AIService.get_bot_response()

GET/POST /admin/login
# GET: Returns admin_login.html
# POST: Authenticates admin and sets session
# Uses: Admin model with password hashing

GET /admin/dashboard
# Returns: admin_dashboard.html template
# Decorator: @login_required
# Purpose: Admin control panel

GET /admin/api/stats
# Returns: Dashboard statistics JSON
# Decorator: @login_required

GET /admin/api/faqs
# Returns: List of all FAQs as JSON
# Decorator: @login_required

POST /admin/api/faq
# Expects: JSON with question, answer, category
# Returns: Success/error JSON
# Decorator: @login_required

PUT /admin/api/faq/<id>
# Expects: JSON with updated fields
# Returns: Success/error JSON
# Decorator: @login_required

DELETE /admin/api/faq/<id>
# Returns: Success/error JSON
# Decorator: @login_required

GET /admin/api/chat-logs
# Returns: Recent chat logs as JSON
# Decorator: @login_required

GET /admin/api/unanswered-questions
# Returns: Unanswered questions as JSON
# Decorator: @login_required
```

#### Database Models (`models.py`)

```python
Admin
├── id (PK, Integer)
├── username (String, unique)
├── password_hash (String)
├── created_at (DateTime)
└── Methods:
    ├── set_password(password)
    └── check_password(password)

FAQ
├── id (PK, Integer)
├── question (String, unique)
├── answer (Text)
├── category (String)
├── created_at (DateTime)
├── updated_at (DateTime)
├── Relationships:
│   └── chat_logs (one-to-many)
└── Methods:
    └── to_dict()

ChatLog
├── id (PK, Integer)
├── user_message (Text)
├── bot_response (Text)
├── confidence_score (Float)
├── matched_faq_id (FK to FAQ)
├── session_id (String)
├── timestamp (DateTime)
├── Relationships:
│   └── faq (many-to-one)
└── Methods:
    └── to_dict()

UnansweredQuestion
├── id (PK, Integer)
├── question (Text)
├── times_asked (Integer)
├── first_asked (DateTime)
├── last_asked (DateTime)
└── Methods:
    └── to_dict()
```

---

## Extending the Project

### Adding a New Feature

#### Example: Sentiment Analysis

**Step 1**: Create new AI feature

```python
# In ai_service.py
@staticmethod
def analyze_sentiment(text):
    """
    Simple sentiment analysis
    Returns: 'positive', 'negative', or 'neutral'
    """
    positive_words = {'good', 'great', 'excellent', 'happy', 'love'}
    negative_words = {'bad', 'terrible', 'hate', 'angry', 'sad'}
    
    tokens = AIService.tokenize(text)
    
    pos_count = len(tokens & positive_words)
    neg_count = len(tokens & negative_words)
    
    if pos_count > neg_count:
        return 'positive'
    elif neg_count > pos_count:
        return 'negative'
    else:
        return 'neutral'
```

**Step 2**: Update database to track sentiment

```python
# In models.py, add to ChatLog:
class ChatLog(db.Model):
    # ... existing fields ...
    user_sentiment = db.Column(db.String(20))  # positive, negative, neutral
```

**Step 3**: Use in response logic

```python
# In ai_service.py, update get_bot_response():
sentiment = AIService.analyze_sentiment(user_message)

chat_log = ChatLog(
    user_message=user_message,
    bot_response=bot_response,
    confidence_score=confidence,
    user_sentiment=sentiment,
    # ... other fields ...
)
```

**Step 4**: Display in admin dashboard

```javascript
// In admin_dashboard.html
// Update chat logs to show sentiment badge
<span class="sentiment-${log.sentiment}">${log.sentiment}</span>
```

### Adding a New Database Field

#### Example: Feedback System (thumbs up/down)

**Step 1**: Add field to ChatLog model

```python
# In models.py
class ChatLog(db.Model):
    # ... existing fields ...
    user_feedback = db.Column(db.Integer, default=0)  # -1, 0, or 1
    feedback_timestamp = db.Column(db.DateTime)
```

**Step 2**: Run migration

```python
# Delete chatbot.db to reset, or:
# Create migration script
with app.app_context():
    db.create_all()  # Updates table schema
```

**Step 3**: Add API endpoint

```python
# In app.py
@app.route('/admin/api/chat-log/<int:log_id>/feedback', methods=['POST'])
@login_required
def add_feedback(log_id):
    data = request.json
    feedback = data.get('feedback')  # -1 or 1
    
    log = ChatLog.query.get(log_id)
    if log:
        log.user_feedback = feedback
        log.feedback_timestamp = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404
```

**Step 4**: Add to frontend

```html
<!-- In admin_dashboard.html -->
<button onclick="addFeedback(${log.id}, 1)">👍</button>
<button onclick="addFeedback(${log.id}, -1)">👎</button>
```

### Improving the Matching Algorithm

#### Option 1: Use Levenshtein Distance

```python
from difflib import SequenceMatcher

@staticmethod
def calculate_similarity(query, faq_question):
    # Simple string matching ratio
    ratio = SequenceMatcher(
        None, 
        query.lower(), 
        faq_question.lower()
    ).ratio()
    return ratio
```

#### Option 2: Use TF-IDF

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

@staticmethod
def calculate_similarity_tfidf(query, all_faq_questions):
    vectorizer = TfidfVectorizer()
    corpus = [query] + all_faq_questions
    tfidf_matrix = vectorizer.fit_transform(corpus)
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])
    return similarities[0]
```

#### Option 3: Use Word Embeddings (spaCy)

```python
import spacy

nlp = spacy.load('en_core_web_sm')

@staticmethod
def calculate_similarity_embeddings(query, faq_question):
    doc1 = nlp(query)
    doc2 = nlp(faq_question)
    return doc1.similarity(doc2)
```

---

## Testing

### Unit Testing Example

```python
# Create file: test_ai_service.py

import unittest
from ai_service import AIService

class TestAIService(unittest.TestCase):
    
    def test_tokenize(self):
        result = AIService.tokenize("Hello World")
        self.assertEqual(result, {'hello', 'world'})
    
    def test_similarity_exact_match(self):
        score = AIService.calculate_similarity(
            "What are your hours?",
            "What are your hours?"
        )
        self.assertEqual(score, 1.0)
    
    def test_similarity_no_match(self):
        score = AIService.calculate_similarity(
            "xyz abc def",
            "qwe rty uiop"
        )
        self.assertEqual(score, 0.0)
    
    def test_similarity_partial_match(self):
        score = AIService.calculate_similarity(
            "What are your business hours?",
            "What are your hours?"
        )
        self.assertGreater(score, 0.5)
        self.assertLess(score, 1.0)

if __name__ == '__main__':
    unittest.main()
```

Run tests:
```bash
python -m pytest test_ai_service.py
# or
python test_ai_service.py
```

---

## Performance Optimization

### Database Indexing

```python
# In models.py
class ChatLog(db.Model):
    __tablename__ = 'chat_logs'
    
    # Speed up queries by FAQ
    matched_faq_id = db.Column(
        db.Integer, 
        db.ForeignKey('faqs.id'), 
        index=True  # Add index
    )
    
    # Speed up date range queries
    timestamp = db.Column(
        db.DateTime, 
        default=datetime.utcnow, 
        index=True  # Add index
    )
```

### Query Optimization

**Bad:**
```python
# This queries each FAQ one by one
for faq in FAQ.query.all():
    if calculate_similarity(query, faq.question) > threshold:
        return faq
```

**Good:**
```python
# This loads all FAQs once
faqs = FAQ.query.all()
best_match = None
best_score = 0

for faq in faqs:
    score = calculate_similarity(query, faq.question)
    if score > best_score:
        best_score = score
        best_match = faq

return best_match
```

### Caching

```python
from functools import lru_cache

@staticmethod
@lru_cache(maxsize=128)
def get_all_faq_questions():
    """Cache frequently accessed FAQ list"""
    return [f.question for f in FAQ.query.all()]
```

---

## Debugging

### Enable Flask Debug Mode

```python
# app.py
app.run(debug=True)  # Enables debug toolbar and auto-reload
```

### Print Debugging

```python
# In ai_service.py
def find_best_match(user_message):
    faqs = FAQ.query.all()
    print(f"[DEBUG] Searching through {len(faqs)} FAQs")
    
    for faq in faqs:
        score = calculate_similarity(user_message, faq.question)
        print(f"[DEBUG] FAQ: {faq.question[:30]} → Score: {score}")
    
    return best_match, best_score
```

### Use Debugger

```python
# In app.py
import pdb

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    
    pdb.set_trace()  # Execution stops here
    # Now use: p variable_name, c (continue), n (next), etc.
    
    response = AIService.get_bot_response(message, session['session_id'])
    return jsonify(response)
```

Run with debugger:
```bash
python -m pdb app.py
```

### View Database Content

```python
# Create file: view_db.py

from app import app
from models import FAQ, ChatLog, Admin

with app.app_context():
    print("=== All FAQs ===")
    for faq in FAQ.query.all():
        print(f"{faq.id}: {faq.question}")
    
    print("\n=== Recent Chats ===")
    for log in ChatLog.query.order_by(ChatLog.timestamp.desc()).limit(5):
        print(f"{log.timestamp}: {log.user_message[:50]}")
        print(f"  → {log.bot_response[:50]}")
        print(f"  Confidence: {log.confidence_score}")

# Run:
# python view_db.py
```

---

## Git Workflow

### Setup Git

```bash
git init
git add .
git commit -m "Initial commit: AI Chatbot project"
git remote add origin https://github.com/yourname/ai-chatbot.git
git push -u origin main
```

### Typical Workflow

```bash
# Create feature branch
git checkout -b feature/sentiment-analysis

# Make changes
# ... edit files ...

# Stage changes
git add .

# Commit
git commit -m "Add sentiment analysis to chatbot"

# Push
git push origin feature/sentiment-analysis

# Create pull request on GitHub
```

### .gitignore Template

```
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.venv/
venv/
env/

# Flask
instance/

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local
```

---

## Common Issues and Solutions

### Issue: Changes in ai_service.py Don't Apply

**Cause**: Flask debug reloader issue

**Fix**:
```bash
# Stop server (Ctrl+C)
# Delete __pycache__ folder
# Restart: python app.py
```

### Issue: Database becomes corrupted

**Cause**: Multiple processes writing simultaneously

**Fix**:
```bash
# Ensure only one app.py running
# Delete chatbot.db - will recreate with sample data
# Or backup db: cp chatbot.db chatbot.db.backup
```

### Issue: Admin can't login after password change

**Cause**: Password not hashed correctly

**Fix**:
```python
# In Python shell
from app import app
from models import db, Admin

with app.app_context():
    admin = Admin.query.filter_by(username='admin').first()
    admin.set_password('newpassword')  # Hashes automatically
    db.session.commit()
    print("Password updated")
```

---

## Deployment for Developers

### Create requirements-dev.txt

```
# All requirements plus dev tools
-r requirements.txt

pytest==7.4.0
pytest-cov==4.1.0
black==23.7.0
flake8==6.0.0
pylint==2.17.5
```

### Code Quality Tools

```bash
# Format code
black .

# Check style
flake8 .

# Linting
pylint *.py

# Run tests with coverage
pytest --cov=. test_*.py
```

### Docker for Development

```dockerfile
FROM python:3.9

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code
COPY . .

# Expose port
EXPOSE 5000

# Run development server
CMD ["python", "app.py"]
```

---

## Resources

### Learning Resources
- Flask Documentation: https://flask.palletsprojects.com/
- SQLAlchemy ORM: https://docs.sqlalchemy.org/
- JavaScript Fetch API: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API
- Python Decorators: https://realpython.com/primer-on-python-decorators/

### Tools
- VS Code: Best Python editor
- Postman: Test APIs
- SQLite Browser: View database
- Git: Version control

---

## Contributing

### Code Style
- Use 4-space indentation
- Follow PEP 8 for Python
- Add docstrings to functions
- Use type hints where possible

### Commit Messages
- Use present tense: "Add feature" not "Added feature"
- Be specific: "Add sentiment analysis to chatbot" not "Update code"
- Keep under 50 characters

### Pull Requests
- Describe changes clearly
- Reference issues if applicable
- Test before submitting
- Get review before merging

---

This guide should help you extend and maintain the AI Chatbot project!
