# Contact Agent Feature - Implementation Guide

## Overview

The Contact Agent feature allows users to submit contact requests directly from the chat interface. Admins can then view, manage, and respond to these requests from a dedicated dashboard.

## Features

✅ **User-Friendly Contact Form**
- Collects: Name, Email, Message, Priority Level
- Form validation with helpful error messages
- Smooth submission with loading indicators
- Success confirmation messages

✅ **Admin Dashboard**
- View all contact requests in a sortable table
- Filter by Status (New, Viewed, In Progress, Resolved)
- Filter by Priority (Low, Normal, High, Urgent)
- Real-time statistics (total, by status, by priority)
- View detailed request information
- Add admin notes for follow-up
- Update request status
- Delete requests

✅ **Database Storage**
- Persistent storage of all contact requests
- Track creation and update timestamps
- Store admin assignments and notes
- Status tracking for workflow management

## File Structure

### Backend Files

```
routes/
├── chat_routes.py          # Added /api/chat/contact-agent endpoint
└── admin_api.py            # Added contact request management endpoints

models/
├── contact_request.py      # New ContactRequest model (database)
└── __init__.py            # Updated to include ContactRequest

templates/
└── contact_requests_admin.html  # Admin dashboard page
```

### Frontend Files

```
static/
├── contact_agent_form.js    # Form logic and submission handler
└── contact_agent_form.css   # Form styling and animations

intent_templates/
└── contact_escalation_intents.json  # New intent template for contact agent
```

## API Endpoints

### User Endpoints (Public)

#### Submit Contact Request
```http
POST /api/chat/contact-agent
Content-Type: application/json

{
    "site_key": "your-public-key",
    "session_id": "session-id",
    "user_name": "John Doe",
    "user_email": "john@example.com",
    "message": "I need help with...",
    "priority": "normal"  # low, normal, high, urgent
}

Response (Success):
{
    "ok": true,
    "message": "Your request has been submitted...",
    "request_id": 123
}
```

### Admin Endpoints

#### Get All Contact Requests
```http
GET /admin/api/client/contact-requests?site_id=1&status=new&priority=high
```

**Response:**
```json
{
    "contact_requests": [
        {
            "id": 1,
            "site_id": 1,
            "user_name": "John Doe",
            "user_email": "john@example.com",
            "message": "I need help",
            "priority": "normal",
            "status": "new",
            "admin_notes": null,
            "assigned_to": null,
            "created_at": "2024-03-09T10:30:00",
            "updated_at": "2024-03-09T10:30:00"
        }
    ]
}
```

#### Get Request Statistics
```http
GET /admin/api/client/contact-requests/stats?site_id=1
```

**Response:**
```json
{
    "stats": {
        "total": 25,
        "by_status": {
            "new": 5,
            "viewed": 10,
            "in_progress": 8,
            "resolved": 2
        },
        "by_priority": {
            "low": 3,
            "normal": 15,
            "high": 6,
            "urgent": 1
        }
    }
}
```

#### Get Request Details
```http
GET /admin/api/client/contact-requests/123?site_id=1
```

#### Update Request
```http
PUT /admin/api/client/contact-requests/123?site_id=1
Content-Type: application/json

{
    "status": "in_progress",
    "admin_notes": "Assigned to John Smith"
}
```

#### Delete Request
```http
DELETE /admin/api/client/contact-requests/123?site_id=1
```

#### View Dashboard
```http
GET /admin/api/client/contact-requests-dashboard?site_id=1
```

## Integration Steps

### 1. Database Migration

Create the `contact_requests` table:

```sql
CREATE TABLE contact_requests (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    site_id INTEGER NOT NULL,
    session_id VARCHAR(100),
    user_name VARCHAR(255) NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'normal',
    status VARCHAR(50) DEFAULT 'new',
    admin_notes TEXT,
    assigned_to INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_site_id (site_id),
    INDEX idx_created_at (created_at)
);
```

Or use Flask-SQLAlchemy migration:

```bash
python
>>> from app import create_app, db
>>> from models.contact_request import ContactRequest
>>> app = create_app()
>>> with app.app_context():
...     db.create_all()
```

### 2. Import Intent Template

1. Go to Admin Dashboard
2. Navigate to Intents > Import Template
3. Upload `intent_templates/contact_escalation_intents.json`
4. Select "contact_agent" intent to enable

Or manually create the intent:

- **Name:** contact_agent
- **Type:** CONTACT
- **Confidence Threshold:** 0.80
- **Phrases:** contact agent, contact support, I need to speak with someone, etc.
- **Response:** "I'd be happy to help you connect with our team..."

### 3. Include Form Assets in Chat Widget

Add these to your chat widget HTML/JavaScript:

```html
<!-- Include CSS -->
<link rel="stylesheet" href="/static/contact_agent_form.css">

<!-- Include JavaScript -->
<script src="/static/contact_agent_form.js"></script>
```

### 4. Trigger Form from Chat

In your chat interface, when the "contact_agent" intent is detected:

```javascript
// Initialize the form
const contactForm = new ContactAgentForm({
    apiEndpoint: '/api/chat/contact-agent',
    siteKey: 'your-public-key',
    sessionId: 'current-session-id',
    containerId: 'chat-container',
    onSuccess: function(result) {
        console.log('Request submitted:', result.request_id);
    },
    onClose: function() {
        console.log('Form closed');
    }
});

// Show the form
contactForm.show();
```

### 5. Access Admin Dashboard

Navigate to: `/admin/api/client/contact-requests-dashboard?site_id=1`

Or add a link in your admin sidebar:

```html
<a href="/admin/api/client/contact-requests-dashboard?site_id={{ site_id }}">
    📧 Contact Requests
</a>
```

## Usage Examples

### User Flow

1. **User Message:** "I want to contact an agent"
2. **Bot Response:** "I'd be happy to help you connect with our team..."
3. **Form Appears:** User fills in name, email, message, and priority
4. **Submission:** Click "Send Request"
5. **Confirmation:** "Your request has been submitted. Our team will contact you shortly."

### Admin Workflow

1. **Load Dashboard:** `/admin/api/client/contact-requests-dashboard?site_id=1`
2. **View Statistics:** See total requests and breakdowns by status/priority
3. **Filter Requests:** Use dropdowns to filter by status or priority
4. **View Details:** Click "View" to see full message
5. **Add Notes:** Enter admin notes (internal use)
6. **Update Status:** Mark as "In Progress" or "Resolved"
7. **Delete:** Remove handled requests

## Customization

### Modify Form Fields

Edit `static/contact_agent_form.js` in the `getFormHTML()` method:

```javascript
// Add a phone field
<div class="form-group">
  <label for="contact-phone">Phone Number</label>
  <input type="tel" id="contact-phone" name="user_phone" class="form-input"/>
</div>
```

Then update server-side validation in `routes/chat_routes.py`.

### Customize Styling

Edit `static/contact_agent_form.css` to match your brand:

```css
.btn-submit {
    background-color: #your-color;
}

.form-wrapper {
    max-width: 600px; /* Change width */
}
```

### Add Email Notifications

In `routes/chat_routes.py`, add email sending after creating the contact request:

```python
from services.email_service import send_email

# After db.session.commit()
send_email(
    to=admin_email,
    subject=f"New Contact Request from {contact_request.user_name}",
    template="contact_request_notification.html",
    context={
        'user_name': contact_request.user_name,
        'user_email': contact_request.user_email,
        'message': contact_request.message,
        'priority': contact_request.priority
    }
)
```

## Status Values

- **new**: Just submitted, not yet viewed
- **viewed**: Admin has viewed the request
- **in_progress**: Administration is handling the request
- **resolved**: Request has been resolved

## Priority Levels

- **low**: General inquiry, no urgency
- **normal**: Standard request, typical urgency
- **high**: Important matter, should be reviewed soon
- **urgent**: Time-sensitive, needs immediate attention

## Security Considerations

✅ **Rate Limiting:** 20 requests per hour per IP
✅ **Input Validation:** Email format, required fields
✅ **XSS Protection:** HTML escaping in admin dashboard
✅ **CSRF Protection:** Ensure Flask-WTF is configured
✅ **Authentication:** Admin endpoints require admin session

## Troubleshooting

### Form Not Appearing

1. Check browser console for errors
2. Ensure `contact_agent` intent is configured
3. Verify form JavaScript is loaded
4. Check site_key is correct

### Requests Not Saving

1. Verify database table exists
2. Check database connections
3. Review error logs
4. Ensure `ContactRequest` model is imported

### Admin Dashboard Not Loading

1. Verify `/admin/api/client/contact-requests-dashboard` route exists
2. Check that you're logged in as admin
3. Verify site_id parameter is present
4. Check browser network tab for API errors

## Future Enhancements

- [ ] Email notifications to users and admins
- [ ] Webhook/Zapier integration for 3rd party systems
- [ ] Auto-reply with ticket number
- [ ] CSV export of contact requests
- [ ] Attachment support (files/images)
- [ ] Team assignment with workload distribution
- [ ] Response time SLAs and tracking
- [ ] Customer feedback ratings on responses
- [ ] Integration with CRM systems

## Support

For issues or questions, refer to the main README.md or contact the development team.
