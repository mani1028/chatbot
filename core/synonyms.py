"""Simple synonyms mapping for sector-agnostic intent matching.

This file contains a lightweight dictionary mapping common synonyms to
canonical tokens. It is intentionally small and editable; later you can
load a larger dataset or connect to an external lexical DB.
"""

SYNONYMS = {
    # medical
    'physician': 'doctor',
    'doc': 'doctor',
    'md': 'doctor',
    'ambulance': 'ambulance',
    'ambulans': 'ambulance',

    # travel / taxi
    'cab': 'taxi',
    'taxi': 'taxi',
    'ride': 'taxi',
    'uber': 'taxi',

    # common
    'hi': 'hello',
    'hey': 'hello',
    'thanks': 'thank_you',
    'thankyou': 'thank_you',
}


def canonical(token: str) -> str:
    """Return a canonical token for a possible synonym, or the token itself."""
    if not token:
        return token
    t = token.lower()
    return SYNONYMS.get(t, t)
