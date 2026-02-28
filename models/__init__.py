"""
Database models package for chatbot application.
This file consolidates all modular models so they are recognized by SQLAlchemy.
"""
from database import db

# 1. Import all modular models from their respective files
from .admin import Admin
from .site import Site
from .plan import Plan, Subscription
from .usage import Usage
from .intent import Intent, IntentPhrase, Workflow
from .chat_log import ChatLog
from .unanswered_question import UnansweredQuestion
from .lead_capture import LeadCapture
from .client_config import ClientConfig
from .branding_settings import BrandingSettings
from .bot import Bot
from .billing import Billing
from .announcement import Announcement
from .integration import Integration
from .platform_settings import PlatformSetting, AuditLog
from .sector_template import SectorTemplate
from .file_manager import TemplateFile, SiteFile
from .booking_request import BookingRequest

# 2. Define what is accessible when someone does "from models import *"
__all__ = [
    'db',
    'Admin',
    'Site',
    'Plan',
    'Subscription',
    'Usage',
    'Intent',
    'IntentPhrase',
    'Workflow',
    'ChatLog',
    'UnansweredQuestion',
    'LeadCapture',
    'BookingRequest',
    'ClientConfig',
    'BrandingSettings',
    'Bot',
    'Billing',
    'Announcement',
    'Integration',
    'PlatformSetting',
    'AuditLog',
    'SectorTemplate',
    'TemplateFile',
    'SiteFile'
]

