# 🧪 Widget Testing Guide

## Quick Start

You now have **two test HTML files** to test the chatbot widget in real-world scenarios:

### Files Created:
1. **`TEST_WIDGET.html`** - Test for Site #1 (College)
2. **`TEST_WIDGET_2.html`** - Test for Site #2 (Corporation) 

---

## 🚀 How to Test

### Step 1: Start the Backend
Make sure your Flask app is running:
```bash
python app.py
```
It should be accessible at `http://localhost:5000`

### Step 2: Open Test Files
Open the test HTML files in your browser:
- **Option A (Single Tab)**: Open `TEST_WIDGET.html` 
- **Option B (Multi-Tenant Test)**: Open both files in separate tabs/windows

```
File → Open File → Select TEST_WIDGET.html
```

### Step 3: Test the Widget
- Click the **💬 chat bubble** in the corner
- Send a message to the bot
- Observe the response and confidence score

---

## 🧪 What Each Test File Does

### TEST_WIDGET.html (Site #1)
✅ Tests the widget with **basic configuration**
- **Site ID**: 1
- **Position**: bottom-right
- **Theme**: light
- **Use Case**: College/Educational Institution

#### Try asking:
- "What are your business hours?"
- "How can I contact support?"
- "What payment methods do you accept?"
- "How long does delivery take?"

---

### TEST_WIDGET_2.html (Site #2)
✅ Tests **multi-tenant isolation**
- **Site ID**: 2
- **Position**: bottom-left
- **Theme**: light
- **Use Case**: Corporate/Enterprise

#### Key Features:
- Different position (bottom-left instead of bottom-right)
- Completely isolated data from Site #1
- Different intents configured
- Different session ID

---

## 📊 Multi-Tenant Testing

### To Test Multi-Tenancy:

1. **Open both test files side-by-side**
   - Left: `TEST_WIDGET.html` (Site #1)
   - Right: `TEST_WIDGET_2.html` (Site #2)

2. **Observe differences**:
   - Widget appears in different corners
   - Chat bubbles might have different colors/branding
   - Responses may differ based on configured intents

3. **Check Database**:
   - Both sites create entries in the same `chat_logs` table
   - But each site sees only its own `site_id` data
   - Verify:
     ```sql
     SELECT * FROM chat_logs WHERE site_id=1;  -- Only Site #1 messages
     SELECT * FROM chat_logs WHERE site_id=2;  -- Only Site #2 messages
     ```

---

## 🔍 Debug & Inspect

### Browser Console (F12)

The test pages automatically log initialization info. Open the browser console to see:

```javascript
ChatbotWidget.getSiteId()        // Returns: 1 or 2
ChatbotWidget.getSessionId()     // Returns: session-xxx
ChatbotWidget.open()             // Open chat programmatically
ChatbotWidget.close()            // Close chat programmatically
```

### Network Tab

To see API calls:
1. Open Developer Tools (F12)
2. Go to **Network** tab
3. Send a message in the chat
4. Notice the `POST /api/chat` request
5. Check the request payload and response

Example request:
```json
{
  "site_id": 1,
  "message": "What are your hours?",
  "session_id": "session-abc123"
}
```

Expected response:
```json
{
  "reply": "We are open Monday to Friday, 9 AM to 6 PM...",
  "intent": "BUSINESS_HOURS",
  "intent_type": "AUTO",
  "confidence": 0.92,
  "handoff": false,
  "lead_capture": false
}
```

---

## ✅ Testing Checklist

### Widget Rendering
- [ ] Chat bubble appears in the correct position
- [ ] Bubble has proper styling (colors, shadows)
- [ ] Hover effects work (scale, shadow change)
- [ ] Button is clickable

### Chat Interaction
- [ ] Clicking bubble opens the chat window
- [ ] Chat window is properly sized
- [ ] Message input field is visible
- [ ] Send button works
- [ ] Chat closes when you click close button

### Backend Communication
- [ ] Messages are sent to `/api/chat`
- [ ] Backend returns proper response
- [ ] Response is displayed in chat
- [ ] Confidence scores show up
- [ ] No console errors

### Multi-Tenancy
- [ ] Site #1 and Site #2 have different `site_id` values
- [ ] Chat logs are properly isolated
- [ ] Different intents are loaded per site
- [ ] Domain whitelisting works (if configured)

### Session Management
- [ ] Session ID persists across page reloads
- [ ] Session ID is different for each browser tab
- [ ] Chat history is maintained in a session

---

## 🛠️ Troubleshooting

### Problem: Widget doesn't appear
**Solution:**
- Check if backend is running: `http://localhost:5000`
- Check browser console for errors (F12)
- Verify `data-site-id` attribute is present
- Clear browser cache and reload

### Problem: "Site not found" error
**Solution:**
- Make sure you've created Site #1 and Site #2 in the database
- Check admin dashboard or database:
  ```sql
  SELECT * FROM sites;
  ```

### Problem: Messages don't send
**Solution:**
- Check Network tab for API responses
- Verify `/api/chat` endpoint exists in app.py
- Check if intents are created for the site (admin dashboard)
- Look for database errors in server logs

### Problem: Bot responds with fallback message
**Solution:**
- The confidence score is below threshold (0.7)
- Check if intents are properly configured
- Try asking exact phrases from the intent_phrases table
- Verify the site_id in the request matches configured intents

---

## 📝 Creating More Test Pages

To test with a **new Site #3**:

1. Create a new file: `TEST_WIDGET_3.html`
2. Copy content from `TEST_WIDGET.html`
3. Change the widget script:
   ```html
   <script 
     src="http://localhost:5000/widget.js"
     data-site-id="3"
     data-position="top-right"
     async>
   </script>
   ```
4. Create Site #3 in admin dashboard
5. Configure intents for Site #3
6. Open the test page and verify it works

---

## 🔐 Security Notes

### Domain Whitelisting
In production, add your domains to the Site's `domain_whitelist`:

```python
site.domain_whitelist = "college.edu,www.college.edu"  # Comma-separated
```

The backend will check the `Referer` header and reject requests from unauthorized domains.

### For Local Testing
Whitelist `localhost`:
```python
site.domain_whitelist = "localhost"
```

---

## 🚀 Next Steps

After successful testing:

1. **Deploy Backend** to production domain
2. **Update Widget Script URL** to production domain
3. **Configure Domain Whitelisting** for each client
4. **Add More Intents** in admin dashboard
5. **Implement Lead Capture** for LEAD type intents
6. **Set Up Handoff Service** for HUMAN type intents
7. **Enable CORS** for cross-domain requests

---

## 📊 Database Check

To verify everything is working, check your database:

```sql
-- Check sites
SELECT * FROM sites;

-- Check intents for each site
SELECT * FROM intents WHERE site_id=1;
SELECT * FROM intents WHERE site_id=2;

-- Check intent phrases
SELECT i.intent_name, ip.phrase 
FROM intent_phrases ip 
JOIN intents i ON ip.intent_id = i.id 
WHERE i.site_id=1;

-- Check chat logs
SELECT * FROM chat_logs WHERE site_id=1;
SELECT * FROM chat_logs WHERE site_id=2;
```

---

## 💡 Pro Tips

1. **Use localStorage** to test session persistence:
   - Open test page
   - Send a message
   - Reload page (F5)
   - Session ID should be the same (check console)

2. **Test cross-domain** by changing the `src` URL in the script tag

3. **Test different themes** by changing `data-theme` attribute:
   ```html
   data-theme="dark"
   ```

4. **Test different positions** by changing `data-position`:
   ```html
   data-position="top-left"
   ```

---

## 📞 Support

If you encounter issues:
1. Check browser console for errors (F12)
2. Check Network tab for API responses
3. Check server logs for backend errors
4. Verify database has data for your site_id
5. Ensure backend is running on correct port

---

**Happy Testing! 🚀**
