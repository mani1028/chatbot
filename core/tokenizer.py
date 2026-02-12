import re

# Expanded stop words to reduce noise across sectors
STOP_WORDS = {
    "the", "a", "an", "is", "are", "please",
    "can", "you", "i", "we", "do", "does", "me", "my",
    "your", "it", "that", "this", "for", "to", "of", "in",
    "on", "at", "by", "with", "from", "about", "as", "be"
}


def tokenize(text):
    """Tokenize text in a sector-agnostic way.

    - Lowercase and strip punctuation
    - Split on whitespace
    - Remove common stop words
    Returns a list of tokens.
    """
    if not text:
        return []
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return [w for w in text.split() if w and w not in STOP_WORDS]
