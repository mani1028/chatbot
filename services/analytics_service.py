"""
Analytics Service - Aggregates chat data for dashboards.
Provides intent distribution, resolution rates, message trends, form stats, etc.
"""
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from sqlalchemy import func, distinct, case, and_
from database import db
from models.chat_log import ChatLog
from models.conversation import Conversation
from models.usage import Usage
from models.form import FormSubmission

logger = logging.getLogger(__name__)


def get_overview(site_id: int, days: int = 30) -> dict:
    """High-level KPI overview for a site."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    total_messages = ChatLog.query.filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff
    ).count()

    unique_sessions = db.session.query(
        func.count(distinct(ChatLog.session_id))
    ).filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff
    ).scalar() or 0

    # Average confidence
    avg_confidence = db.session.query(
        func.avg(ChatLog.confidence)
    ).filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff,
        ChatLog.confidence.isnot(None)
    ).scalar() or 0

    # Handoff count
    handoff_count = ChatLog.query.filter(
        ChatLog.site_id == site_id,
        ChatLog.detected_intent == 'HUMAN',
        ChatLog.created_at >= cutoff
    ).count()

    # Unknown/fallback count
    unknown_count = ChatLog.query.filter(
        ChatLog.site_id == site_id,
        ChatLog.detected_intent.in_(['UNKNOWN', 'ERROR']),
        ChatLog.created_at >= cutoff
    ).count()

    # Resolution rate = messages resolved without handoff
    resolved = total_messages - handoff_count - unknown_count
    resolution_rate = round((resolved / total_messages * 100), 1) if total_messages > 0 else 0

    # Form submissions
    form_submissions = FormSubmission.query.filter(
        FormSubmission.site_id == site_id,
        FormSubmission.created_at >= cutoff
    ).count()

    return {
        'total_messages': total_messages,
        'unique_sessions': unique_sessions,
        'avg_confidence': round(float(avg_confidence), 3),
        'handoff_count': handoff_count,
        'unknown_count': unknown_count,
        'resolution_rate': resolution_rate,
        'form_submissions': form_submissions,
        'period_days': days
    }


def get_intent_distribution(site_id: int, days: int = 30) -> list:
    """Top intents by frequency."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    results = db.session.query(
        ChatLog.detected_intent,
        func.count(ChatLog.id).label('count')
    ).filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff,
        ChatLog.detected_intent.isnot(None)
    ).group_by(
        ChatLog.detected_intent
    ).order_by(
        func.count(ChatLog.id).desc()
    ).limit(20).all()

    total = sum(r.count for r in results)
    return [
        {
            'intent': r.detected_intent,
            'count': r.count,
            'percentage': round((r.count / total * 100), 1) if total > 0 else 0
        }
        for r in results
    ]


def get_message_trend(site_id: int, days: int = 30) -> list:
    """Daily message counts for a trend chart."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Group by date
    results = db.session.query(
        func.date(ChatLog.created_at).label('date'),
        func.count(ChatLog.id).label('count')
    ).filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff
    ).group_by(
        func.date(ChatLog.created_at)
    ).order_by(
        func.date(ChatLog.created_at)
    ).all()

    # Fill in missing dates
    trend = []
    current = cutoff.date()
    today = datetime.utcnow().date()
    result_map = {str(r.date): r.count for r in results}

    while current <= today:
        date_str = str(current)
        trend.append({
            'date': date_str,
            'messages': result_map.get(date_str, 0)
        })
        current += timedelta(days=1)

    return trend


def get_confidence_distribution(site_id: int, days: int = 30) -> dict:
    """Histogram of confidence scores in bands."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    logs = ChatLog.query.filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff,
        ChatLog.confidence.isnot(None)
    ).with_entities(ChatLog.confidence).all()

    bands = {'0-20': 0, '20-40': 0, '40-60': 0, '60-80': 0, '80-100': 0}
    for (conf,) in logs:
        pct = (conf or 0) * 100
        if pct <= 20:
            bands['0-20'] += 1
        elif pct <= 40:
            bands['20-40'] += 1
        elif pct <= 60:
            bands['40-60'] += 1
        elif pct <= 80:
            bands['60-80'] += 1
        else:
            bands['80-100'] += 1

    return bands


def get_peak_hours(site_id: int, days: int = 30) -> list:
    """Message volume by hour of day (0-23)."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    logs = ChatLog.query.filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff
    ).with_entities(ChatLog.created_at).all()

    hour_counts = Counter()
    for (ts,) in logs:
        if ts:
            hour_counts[ts.hour] += 1

    return [
        {'hour': h, 'messages': hour_counts.get(h, 0)}
        for h in range(24)
    ]


def get_session_metrics(site_id: int, days: int = 30) -> dict:
    """Session-level metrics: avg messages per session, avg duration."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Group messages by session
    session_data = db.session.query(
        ChatLog.session_id,
        func.count(ChatLog.id).label('msg_count'),
        func.min(ChatLog.created_at).label('first_msg'),
        func.max(ChatLog.created_at).label('last_msg')
    ).filter(
        ChatLog.site_id == site_id,
        ChatLog.created_at >= cutoff,
        ChatLog.session_id.isnot(None)
    ).group_by(
        ChatLog.session_id
    ).all()

    if not session_data:
        return {'avg_messages_per_session': 0, 'avg_session_duration_minutes': 0, 'total_sessions': 0}

    total_sessions = len(session_data)
    total_messages = sum(s.msg_count for s in session_data)
    total_duration = sum(
        (s.last_msg - s.first_msg).total_seconds() / 60
        for s in session_data
        if s.first_msg and s.last_msg
    )

    return {
        'total_sessions': total_sessions,
        'avg_messages_per_session': round(total_messages / total_sessions, 1),
        'avg_session_duration_minutes': round(total_duration / total_sessions, 1) if total_sessions > 0 else 0
    }


def get_full_analytics(site_id: int, days: int = 30) -> dict:
    """Aggregated analytics for admin dashboard."""
    return {
        'overview': get_overview(site_id, days),
        'intent_distribution': get_intent_distribution(site_id, days),
        'message_trend': get_message_trend(site_id, days),
        'confidence_distribution': get_confidence_distribution(site_id, days),
        'peak_hours': get_peak_hours(site_id, days),
        'session_metrics': get_session_metrics(site_id, days),
    }
