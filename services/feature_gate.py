"""
Feature Gate Service - Plan-based feature access control.
Check whether a site's plan allows a specific feature before executing it.
"""
import logging
from database import db
from models.site import Site
from models.plan import Plan

logger = logging.getLogger(__name__)

# Feature gate constants
FEATURE_AI = 'ai_enabled'
FEATURE_WORKFLOWS = 'workflows_enabled'
FEATURE_FORMS = 'forms_enabled'
FEATURE_ANALYTICS = 'analytics_enabled'
FEATURE_WEBHOOKS = 'webhooks_enabled'
FEATURE_BRANDING = 'custom_branding'


def get_site_plan(site_id: int) -> Plan:
    """Get the plan for a site, returns None if no plan."""
    site = db.session.get(Site, site_id)
    if not site:
        return None
    return site.plan


def check_feature(site_id: int, feature: str) -> bool:
    """
    Check if a feature is enabled for the given site's plan.
    Returns True if the feature is enabled, False otherwise.
    Sites without a plan get basic features only.
    """
    plan = get_site_plan(site_id)
    if not plan:
        # No plan = free tier, only basic features
        return feature in (FEATURE_WORKFLOWS,)  # Only workflows on free tier

    return getattr(plan, feature, False)


def check_limit(site_id: int, limit_name: str, current_count: int) -> bool:
    """
    Check if a site is within its plan limits.
    Returns True if within limit, False if exceeded.
    """
    plan = get_site_plan(site_id)
    if not plan:
        # Free tier defaults
        defaults = {
            'max_intents': 10,
            'max_monthly_chats': 100,
            'max_forms': 1,
            'max_webhooks': 0,
        }
        limit = defaults.get(limit_name, 0)
        return current_count < limit

    limit = getattr(plan, limit_name, 0)
    return current_count < limit


def get_site_features(site_id: int) -> dict:
    """
    Get all feature flags and limits for a site.
    Used by the frontend to show/hide UI elements.
    """
    plan = get_site_plan(site_id)
    if not plan:
        return {
            'plan_name': 'Free',
            'ai_enabled': False,
            'workflows_enabled': True,
            'forms_enabled': False,
            'analytics_enabled': False,
            'webhooks_enabled': False,
            'custom_branding': False,
            'priority_support': False,
            'max_intents': 10,
            'max_monthly_chats': 100,
            'max_forms': 1,
            'max_webhooks': 0,
        }

    features = plan.get_features()
    features['plan_name'] = plan.name
    return features


def require_feature(site_id: int, feature: str) -> tuple:
    """
    Gate check that returns (allowed: bool, error_message: str or None).
    Use in route handlers before executing feature logic.
    """
    if check_feature(site_id, feature):
        return True, None

    plan = get_site_plan(site_id)
    plan_name = plan.name if plan else 'Free'
    feature_label = feature.replace('_', ' ').replace('enabled', '').strip().title()

    return False, f"{feature_label} is not available on the {plan_name} plan. Please upgrade."
