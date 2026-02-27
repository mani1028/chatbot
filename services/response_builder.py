import re
from models import ClientConfig

def build_response(template: str, site_id: int) -> str:
    """
    Replaces placeholders like {consultation_price} with values from ClientConfig.
    Falls back to '[Not configured]' if the key is missing.
    """
    if not template:
        return ""

    # Fetch all config for this site to minimize DB hits
    configs = ClientConfig.query.filter_by(site_id=site_id).all()
    config_map = {c.key: c.value for c in configs}

    def replace_match(match):
        key = match.group(1) # The text inside the brackets
        # Return value from map, or fallback
        return config_map.get(key, f"[{key} not configured]")

    # Use regex to find {word} patterns and replace them
    # Pattern explanation: \{  Look for literal {
    #                      (\w+) Capture alphanumeric key
    #                      \}  Look for literal }
    return re.sub(r'\{(\w+)\}', replace_match, template)

