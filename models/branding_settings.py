from database import db
from datetime import datetime

class BrandingSettings(db.Model):
    __tablename__ = 'branding_settings'
    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    bot_name = db.Column(db.String(255), default="ChatBot")
    bot_description = db.Column(db.String(500), default="We're here to help")
    primary_color = db.Column(db.String(7), default="#667eea")
    secondary_color = db.Column(db.String(7), default="#764ba2")
    accent_color = db.Column(db.String(7), default="#4CAF50")
    logo_url = db.Column(db.String(500), nullable=True)
    favicon_url = db.Column(db.String(500), nullable=True)
    initial_message = db.Column(db.Text, default="Hi! How can I help you today?")
    position = db.Column(db.String(20), default="bottom-right")
    theme_mode = db.Column(db.String(10), default="light")
    custom_css = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "bot_name": self.bot_name,
            "bot_description": getattr(self, "bot_description", ""),
            "primary_color": self.primary_color,
            "secondary_color": getattr(self, "secondary_color", ""),
            "accent_color": getattr(self, "accent_color", ""),
            "logo_url": self.logo_url,
            "favicon_url": self.favicon_url,
            "initial_message": self.initial_message,
            "position": self.position,
            "theme_mode": self.theme_mode,
            "custom_css": getattr(self, "custom_css", ""),
        }
