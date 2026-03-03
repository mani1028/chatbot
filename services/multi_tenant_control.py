"""
Multi-Tenant Workflow Control

Enable/disable features per:
- Site
- Workspace/Tenant
- Plan (Free, Pro, Enterprise)
- User role

This connects engineering to SaaS monetization.
"""

from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class WorkflowPlan:
    """Define workflows available per plan"""
    
    PLANS = {
        'free': {
            'name': 'Free',
            'max_workflows': 1,
            'available_workflows': ['lead_capture'],  # Free tier gets lead capture
            'features': {
                'analytics': False,
                'custom_workflows': False,
                'escalation': False,
                'memory_compression': False,
                'context_engine': False,
                'rule_engine': False,
                'multi_language': False
            }
        },
        'pro': {
            'name': 'Professional',
            'max_workflows': 3,
            'available_workflows': ['lead_capture', 'booking', 'support'],
            'features': {
                'analytics': True,
                'custom_workflows': False,
                'escalation': True,
                'memory_compression': True,
                'context_engine': True,
                'rule_engine': True,
                'multi_language': False
            }
        },
        'enterprise': {
            'name': 'Enterprise',
            'max_workflows': 999,
            'available_workflows': None,  # All workflows
            'features': {
                'analytics': True,
                'custom_workflows': True,  # Can define own workflows
                'escalation': True,
                'memory_compression': True,
                'context_engine': True,
                'rule_engine': True,
                'multi_language': True,
                'white_label': True,
                'sso': True,
                'api_access': True
            }
        }
    }
    
    @staticmethod
    def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan configuration"""
        return WorkflowPlan.PLANS.get(plan_id)
    
    @staticmethod
    def list_plans() -> List[str]:
        """List available plan IDs"""
        return list(WorkflowPlan.PLANS.keys())


class SiteWorkflowControl:
    """
    Control which workflows are enabled per site.
    
    From database:
    {
        'site_id': 'acme_corp',
        'plan': 'pro',
        'enabled_workflows': ['booking', 'lead_capture'],
        'disabled_workflows': ['support'],
        'workflow_limits': {
            'booking': {'max_sessions': 1000},
            'lead_capture': {'rate_limit': '100/day'}
        }
    }
    """
    
    def __init__(self, site_id: str):
        self.site_id = site_id
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load from database (mock for now)"""
        # In production, this would query:
        # SELECT * FROM site_config WHERE site_id = ?
        
        return {
            'site_id': self.site_id,
            'plan': 'pro',
            'enabled_workflows': ['booking', 'lead_capture', 'support'],
            'custom_rules_enabled': True,
            'analytics_enabled': True,
            'escalation_enabled': True
        }
    
    def can_start_workflow(self, workflow_type: str) -> tuple[bool, Optional[str]]:
        """
        Check if site can use this workflow.
        
        Returns: (allowed, reason_if_denied)
        """
        
        enabled = self.config.get('enabled_workflows', [])
        
        if workflow_type not in enabled:
            return False, f"Workflow '{workflow_type}' not enabled for this site"
        
        return True, None
    
    def get_available_workflows(self) -> List[str]:
        """Get workflows available to this site"""
        return self.config.get('enabled_workflows', [])
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if feature is enabled for site"""
        features = self.config.get('features', {})
        return features.get(feature_name, False)
    
    def enable_workflow(self, workflow_type: str) -> bool:
        """Enable workflow for site (admin function)"""
        enabled = self.config['enabled_workflows']
        if workflow_type not in enabled:
            enabled.append(workflow_type)
            self._save_config()
            logger.info(f"Enabled {workflow_type} for site {self.site_id}")
            return True
        return False
    
    def disable_workflow(self, workflow_type: str) -> bool:
        """Disable workflow for site (admin function)"""
        enabled = self.config['enabled_workflows']
        if workflow_type in enabled:
            enabled.remove(workflow_type)
            self._save_config()
            logger.info(f"Disabled {workflow_type} for site {self.site_id}")
            return True
        return False
    
    def _save_config(self):
        """Save config to database (mock for now)"""
        # In production: UPDATE site_config SET ... WHERE site_id = ?
        pass


class FeatureGate:
    """
    Feature flags for advanced capabilities.
    
    Examples:
    - 'memory_compression': Save tokens
    - 'context_engine': Detect frustration
    - 'rule_engine': Execute rules before LLM
    - 'analytics': Show dashboards
    """
    
    # Global feature flags (can be overridden per site)
    GLOBAL_FLAGS = {
        'memory_compression': {'enabled': True, 'rollout': 1.0},
        'context_engine': {'enabled': True, 'rollout': 0.8},
        'rule_engine': {'enabled': True, 'rollout': 0.9},
        'analytics': {'enabled': True, 'rollout': 1.0},
        'multi_language': {'enabled': False, 'rollout': 0.0},
        'escalation_v2': {'enabled': False, 'rollout': 0.0},  # Beta
        'sentiment_analysis': {'enabled': False, 'rollout': 0.2},  # Beta
    }
    
    @staticmethod
    def is_enabled(
        feature_name: str,
        site_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Check if feature is enabled.
        
        With rollout percentage for gradual rollouts.
        """
        
        flag = FeatureGate.GLOBAL_FLAGS.get(feature_name)
        if not flag:
            logger.warning(f"Unknown feature: {feature_name}")
            return False
        
        # Global enabled/disabled
        if not flag.get('enabled'):
            return False
        
        # Rollout percentage (gradual rollout)
        import hashlib
        if flag.get('rollout', 1.0) < 1.0:
            # Deterministic hash for consistent experience
            hash_input = f"{site_id}:{feature_name}".encode()
            hash_val = int(hashlib.md5(hash_input).hexdigest(), 16)
            if (hash_val % 100) / 100.0 > flag.get('rollout'):
                return False
        
        return True
    
    @staticmethod
    def enable_feature(feature_name: str):
        """Enable feature globally"""
        if feature_name in FeatureGate.GLOBAL_FLAGS:
            FeatureGate.GLOBAL_FLAGS[feature_name]['enabled'] = True
            logger.info(f"Enabled feature: {feature_name}")
    
    @staticmethod
    def disable_feature(feature_name: str):
        """Disable feature globally"""
        if feature_name in FeatureGate.GLOBAL_FLAGS:
            FeatureGate.GLOBAL_FLAGS[feature_name]['enabled'] = False
            logger.info(f"Disabled feature: {feature_name}")
    
    @staticmethod
    def set_rollout(feature_name: str, percentage: float):
        """Set gradual rollout percentage (0-1.0)"""
        if feature_name in FeatureGate.GLOBAL_FLAGS:
            FeatureGate.GLOBAL_FLAGS[feature_name]['rollout'] = max(0.0, min(1.0, percentage))
            logger.info(f"Set rollout for {feature_name}: {percentage*100:.0f}%")


class WorkflowVersionControl:
    """
    Version workflows for safe updates.
    
    Example:
    - booking:1.0 (stable, current)
    - booking:2.0 (beta, gradual rollout)
    """
    
    def __init__(self):
        self.versions = {
            'booking': {
                '1.0': {'enabled': True, 'rollout': 1.0},
                '2.0': {'enabled': True, 'rollout': 0.1}  # 10% of traffic
            },
            'lead_capture': {
                '1.0': {'enabled': True, 'rollout': 1.0}
            },
            'support': {
                '1.0': {'enabled': True, 'rollout': 1.0},
                '1.1': {'enabled': True, 'rollout': 0.5}  # 50% rollout
            }
        }
    
    def get_workflow_version(self, workflow_type: str, site_id: Optional[str] = None) -> Optional[str]:
        """
        Get which version to use for site.
        
        Respects rollout percentages.
        """
        
        versions = self.versions.get(workflow_type, {})
        if not versions:
            return None
        
        import hashlib
        
        # Get highest version available (by rollout)
        for version in sorted(versions.keys(), reverse=True):
            ver_config = versions[version]
            if not ver_config.get('enabled'):
                continue
            
            # Check rollout
            rollout = ver_config.get('rollout', 1.0)
            if rollout >= 1.0:
                return version  # 100% rollout, use this
            
            # Deterministic rollout
            if site_id:
                hash_input = f"{site_id}:{workflow_type}:{version}".encode()
                hash_val = int(hashlib.md5(hash_input).hexdigest(), 16)
                if (hash_val % 100) / 100.0 <= rollout:
                    return version
        
        # Fallback to first available version
        return list(versions.keys())[0] if versions else None
    
    def enable_beta_version(self, workflow_type: str, version: str):
        """Enable new version for testing"""
        if workflow_type in self.versions:
            if version in self.versions[workflow_type]:
                self.versions[workflow_type][version]['enabled'] = True


# Global control instances
_site_controls = {}

def get_site_control(site_id: str) -> SiteWorkflowControl:
    """Get site-specific workflow control"""
    if site_id not in _site_controls:
        _site_controls[site_id] = SiteWorkflowControl(site_id)
    return _site_controls[site_id]
