def mask_secrets(value: str) -> str:
    """Mask all but last 4 characters of a secret value."""
    if not value or len(value) < 8:
        return '****'
    return '*' * (len(value) - 4) + value[-4:]
