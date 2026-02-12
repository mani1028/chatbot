from models import ClientConfig


def build_response(template: str, client_id: int):
    """Render a template replacing {keys} with values from ClientConfig for client_id.

    Safe: missing keys are left as-is.
    """
    if not template:
        return template

    # Load client configs into a dict
    cfgs = ClientConfig.query.filter_by(client_id=client_id).all()
    mapping = {c.key: c.value for c in cfgs}

    # Simple replacement
    try:
        return template.format(**mapping)
    except Exception:
        # fallback: do manual replace for curly tokens
        out = template
        for k, v in mapping.items():
            out = out.replace('{' + k + '}', str(v))
        return out
