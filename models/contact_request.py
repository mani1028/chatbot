from database import db
from datetime import datetime

class ContactRequest(db.Model):
    __tablename__ = 'contact_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, nullable=False, index=True)
    session_id = db.Column(db.String(100), nullable=True)
    
    # User information
    user_name = db.Column(db.String(255), nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    
    # Contact details
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), nullable=False, default='normal')  # low, normal, high, urgent
    
    # Status tracking
    status = db.Column(db.String(50), nullable=False, default='new')  # new, viewed, in_progress, resolved
    admin_notes = db.Column(db.Text, nullable=True)
    assigned_to = db.Column(db.Integer, nullable=True)  # Admin ID
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'user_name': self.user_name,
            'user_email': self.user_email,
            'message': self.message,
            'priority': self.priority,
            'status': self.status,
            'admin_notes': self.admin_notes,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
