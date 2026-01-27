# QUICK START GUIDE

## 🚀 One-Minute Setup

### Windows Users
```bash
# Navigate to project folder
cd ai_chatbot

# Double-click run.bat
# OR run in PowerShell:
.\run.bat
```

### macOS/Linux Users
```bash
cd ai_chatbot
chmod +x run.sh
./run.sh
```

### Manual Setup (Any OS)
```bash
cd ai_chatbot

# Create virtual environment
python -m venv venv

# Activate it
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run app
python app.py
```

---

## 📱 Using the Chatbot

1. **Open browser**: http://localhost:5000
2. **Chat popup** appears in bottom-right corner
3. **Type a question**: e.g., "What are your business hours?"
4. **Bot responds** with answer from FAQ database
5. **Confidence score** shown as ✅ or ❓

### Example Questions (Pre-loaded FAQs)
- "What are your business hours?"
- "How can I contact support?"
- "What payment methods do you accept?"
- "How long does delivery take?"

---

## 🔐 Admin Dashboard

1. **Open**: http://localhost:5000/admin/login
2. **Login with**:
   - Username: `admin`
   - Password: `admin123`

### Admin Tasks
- ➕ **Add FAQ** → Go to "Manage FAQs"
- ✏️ **Edit FAQ** → Click "Edit" on any FAQ
- ❌ **Delete FAQ** → Click "Delete" on any FAQ
- 📊 **View Stats** → Dashboard tab shows metrics
- 📋 **Chat Logs** → See all conversations
- ❓ **Unanswered Q's** → Find FAQ gaps

---

## 📊 Key Features Explained

### How It Answers
1. User sends question
2. AI compares with all FAQ questions
3. Finds best match (similarity score)
4. If score >= 0.7 → Reply with FAQ answer
5. If score < 0.7 → Polite fallback message

### Confidence Score
- **✅ 0.70-1.00**: High confidence (answer provided)
- **❓ 0.00-0.69**: Low confidence (fallback used)
- **Threshold**: Can be changed in `config.py`

### Logging
- Every chat is logged to database
- Includes: question, answer, confidence score, timestamp
- Unanswered questions tracked separately

---

## 🛠️ Customization

### Change Admin Password
Edit `config.py`:
```python
ADMIN_PASSWORD = 'your-new-password'
```

### Change Confidence Threshold
Edit `config.py` (lower = more answers, higher = more selective):
```python
CONFIDENCE_THRESHOLD = 0.6  # More lenient
CONFIDENCE_THRESHOLD = 0.8  # More strict
```

### Add Fallback Messages
Edit `config.py`:
```python
FALLBACK_MESSAGES = [
    "I'm not sure. Can you rephrase?",
    "Try asking our support team.",
]
```

### Change Chat UI Colors
Edit `static/style.css`:
- Search for `#667eea` (primary purple color)
- Replace with your color

### Add Sample FAQs
- Use Admin Dashboard "Manage FAQs" tab
- Or import via `ai_service.py`

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 5000 already in use | Change port in `app.py` line: `app.run(port=5001)` |
| Admin login fails | Delete `chatbot.db` and restart |
| Chatbot not responding | Refresh browser, check console (F12) |
| Can't access from other computer | Change `localhost` to your IP in URL |

---

## 📁 File Breakdown

| File | Purpose |
|------|---------|
| `app.py` | Main Flask app & routes |
| `ai_service.py` | Chatbot AI logic |
| `models.py` | Database tables |
| `config.py` | Settings & credentials |
| `templates/` | HTML pages |
| `static/` | CSS & JavaScript |
| `chatbot.db` | SQLite database (auto-created) |

---

## 🔗 API Endpoints

**User Chat**:
- `GET /` → Chat interface
- `POST /api/chat` → Send message

**Admin**:
- `GET /admin/login` → Login page
- `GET /admin/dashboard` → Admin page
- `POST /admin/api/faq` → Add FAQ
- `PUT /admin/api/faq/1` → Update FAQ
- `DELETE /admin/api/faq/1` → Delete FAQ
- `GET /admin/api/chat-logs` → Get logs
- `GET /admin/api/unanswered-questions` → Get unanswered

---

## ⚙️ Production Notes

Before deploying to production:
1. Change `SECRET_KEY` in `config.py`
2. Change admin password
3. Set `DEBUG = False` in `config.py`
4. Use Gunicorn instead of Flask dev server
5. Use reverse proxy (Nginx) with HTTPS
6. Set up database backups
7. Add rate limiting

**Install Gunicorn**:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## 📞 Support

**Common Tasks**:
- Add new FAQ: Admin Dashboard → Manage FAQs → Add New FAQ
- View conversations: Admin Dashboard → Chat Logs
- Find gaps in FAQs: Admin Dashboard → Unanswered Q's
- Reset database: Delete `chatbot.db`, restart app

**Need help?** Check the full README.md for detailed docs.

---

## ✅ You're All Set!

1. ✅ Project downloaded
2. ✅ Dependencies installed
3. ✅ Database created
4. ✅ Server running
5. ✅ Ready to chat!

Open **http://localhost:5000** and start chatting! 🎉

For admin: **http://localhost:5000/admin/login** 🔐
