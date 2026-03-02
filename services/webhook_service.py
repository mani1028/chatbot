"""
Webhook Service - Fires webhooks for site events (handoff, form completion, etc.)
Replaces the old hardcoded CRM webhook with per-site configurable webhooks.
"""
import json
import logging
import threading
import requests
from datetime import datetime
from database import db
from models.webhook import WebhookConfig, WebhookLog

logger = logging.getLogger(__name__)

# Supported event types
EVENT_HANDOFF = 'handoff'
EVENT_FORM_COMPLETE = 'form_complete'
EVENT_LEAD_CAPTURE = 'lead_capture'
EVENT_ESCALATION = 'escalation'
EVENT_NEW_CONVERSATION = 'new_conversation'

ALL_EVENTS = [EVENT_HANDOFF, EVENT_FORM_COMPLETE, EVENT_LEAD_CAPTURE, EVENT_ESCALATION, EVENT_NEW_CONVERSATION]


def fire_event(site_id: int, event_type: str, payload: dict):
    """
    Fire all enabled webhooks for a given event type on a site.
    Runs in a background thread to avoid blocking the response.
    """
    thread = threading.Thread(
        target=_fire_event_sync,
        args=(site_id, event_type, payload),
        daemon=True
    )
    thread.start()


def _fire_event_sync(site_id: int, event_type: str, payload: dict):
    """Synchronous webhook firing - called in a background thread."""
    from app import app

    with app.app_context():
        webhooks = WebhookConfig.query.filter_by(
            site_id=site_id,
            event_type=event_type,
            enabled=True
        ).all()

        if not webhooks:
            return

        for webhook in webhooks:
            _deliver_webhook(webhook, site_id, event_type, payload)


def _deliver_webhook(webhook: WebhookConfig, site_id: int, event_type: str, payload: dict):
    """Attempt to deliver a webhook with retries."""
    headers = webhook.get_headers()
    headers.setdefault('Content-Type', 'application/json')

    # Build the final payload
    final_payload = _build_payload(webhook, event_type, payload)

    for attempt in range(1, webhook.max_retries + 1):
        try:
            if webhook.method.upper() == 'PUT':
                resp = requests.put(
                    webhook.url,
                    json=final_payload,
                    headers=headers,
                    timeout=webhook.timeout_seconds
                )
            else:
                resp = requests.post(
                    webhook.url,
                    json=final_payload,
                    headers=headers,
                    timeout=webhook.timeout_seconds
                )

            success = 200 <= resp.status_code < 300

            # Log the attempt
            log = WebhookLog(
                webhook_id=webhook.id,
                site_id=site_id,
                event_type=event_type,
                payload=json.dumps(final_payload),
                status_code=resp.status_code,
                response_body=resp.text[:1000] if resp.text else None,
                success=success,
                attempt=attempt
            )
            db.session.add(log)

            # Update webhook status
            webhook.last_triggered = datetime.utcnow()
            webhook.last_status_code = resp.status_code
            db.session.commit()

            if success:
                logger.info(f"Webhook {webhook.id} delivered successfully for {event_type}")
                return
            else:
                logger.warning(f"Webhook {webhook.id} returned {resp.status_code} (attempt {attempt})")

        except requests.exceptions.Timeout:
            _log_error(webhook, site_id, event_type, final_payload, attempt, "Request timed out")
        except requests.exceptions.ConnectionError:
            _log_error(webhook, site_id, event_type, final_payload, attempt, "Connection refused")
        except Exception as e:
            _log_error(webhook, site_id, event_type, final_payload, attempt, str(e))

    logger.error(f"Webhook {webhook.id} failed after {webhook.max_retries} attempts")


def _build_payload(webhook: WebhookConfig, event_type: str, data: dict) -> dict:
    """Build the webhook payload, using a template if configured."""
    if webhook.payload_template:
        try:
            template = json.loads(webhook.payload_template)
            # Simple placeholder replacement
            rendered = _render_template(template, data)
            return rendered
        except (json.JSONDecodeError, TypeError):
            pass

    # Default payload structure
    return {
        'event': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'site_id': webhook.site_id,
        'data': data
    }


def _render_template(template, data: dict):
    """Recursively replace {key} placeholders in a template dict/list/str."""
    if isinstance(template, str):
        for key, value in data.items():
            template = template.replace(f'{{{key}}}', str(value))
        return template
    elif isinstance(template, dict):
        return {k: _render_template(v, data) for k, v in template.items()}
    elif isinstance(template, list):
        return [_render_template(item, data) for item in template]
    return template


def _log_error(webhook, site_id, event_type, payload, attempt, error_msg):
    """Log a failed webhook attempt."""
    try:
        log = WebhookLog(
            webhook_id=webhook.id,
            site_id=site_id,
            event_type=event_type,
            payload=json.dumps(payload),
            success=False,
            error_message=error_msg,
            attempt=attempt
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log webhook error: {e}")
        db.session.rollback()


def get_webhook_stats(site_id: int) -> dict:
    """Get webhook delivery statistics for a site."""
    from sqlalchemy import func

    total = WebhookLog.query.filter_by(site_id=site_id).count()
    successful = WebhookLog.query.filter_by(site_id=site_id, success=True).count()
    failed = total - successful

    recent_logs = WebhookLog.query.filter_by(site_id=site_id)\
        .order_by(WebhookLog.created_at.desc()).limit(10).all()

    return {
        'total_deliveries': total,
        'successful': successful,
        'failed': failed,
        'success_rate': round((successful / total * 100), 1) if total > 0 else 0,
        'recent_logs': [log.to_dict() for log in recent_logs]
    }
