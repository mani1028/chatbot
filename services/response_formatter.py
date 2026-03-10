"""Template variable substitution for intent responses."""

import re
from models.client_config import ClientConfig
from models.branding_settings import BrandingSettings


def substitute_template_variables(response_text: str, site_id: int) -> str:
    """
    Replace template variables in response text with actual site configuration values.
    
    Variables: {open_time}, {close_time}, {support_email}, {support_phone}, {office_address}, etc.
    
    Args:
        response_text: Response text with template variables
        site_id: Site ID to fetch configuration for
        
    Returns:
        Response text with variables substituted, or fallback text if variable not found
    """
    if not response_text or '{' not in response_text:
        return response_text
    
    # Find all template variables
    pattern = r'\{(\w+)\}'
    variables = re.findall(pattern, response_text)
    
    if not variables:
        return response_text
    
    # Build substitution map from site config
    substitutions = _build_substitution_map(site_id, variables)
    
    # Replace variables
    result = response_text
    for var_name in variables:
        placeholder = f"{{{var_name}}}"
        value = substitutions.get(var_name, f"[{var_name}]")  # Fallback shows variable name
        result = result.replace(placeholder, value)
    
    return result


def _build_substitution_map(site_id: int, variables: list) -> dict:
    """Build a map of variable names to their values from site config."""
    
    substitutions = {}
    
    # Common variables that come from ClientConfig
    # Maps response template variable names to database config keys
    config_keys = {
        'open_time': 'open_time',
        'close_time': 'close_time',
        'support_email': 'support_email',
        'support_phone': 'support_phone',
        'office_address': 'office_address',
        'consultation_price': 'consultation_price',
    }
    
    # Fetch ClientConfig values
    for var_name in variables:
        config_key = config_keys.get(var_name)
        
        if config_key:
            config = ClientConfig.query.filter_by(
                site_id=site_id,
                key=config_key
            ).first()
            
            if config and config.value:
                substitutions[var_name] = config.value
            else:
                # Use sensible defaults if not configured
                defaults = {
                    'open_time': '9:00 AM',
                    'close_time': '5:00 PM',
                    'support_email': 'support@example.com',
                    'support_phone': '1-800-SUPPORT',
                    'office_address': '123 Main St, City, State 12345',
                    'consultation_price': '$500',
                }
                substitutions[var_name] = defaults.get(var_name, f'[{var_name}]')
        else:
            # Unknown variable, show placeholder
            substitutions[var_name] = f'[{var_name}]'
    
    return substitutions
