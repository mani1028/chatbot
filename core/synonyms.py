# Synonym dictionary mapping variations to a single canonical "root" word
SYNONYM_MAP = {
    # Time & Hours additions
    "timings": "hours",
    "timing": "hours",
    "opening": "open",
    "schedule": "hours",
    
    # Pricing-related synonyms
    "fees": "pricing",
    "cost": "pricing",
    "charges": "pricing",
    "rates": "pricing",
    
    # Location-related synonyms
    "directions": "location",
    "place": "location",
    "address": "location",
    
    # Greetings-related synonyms
    "hiya": "hi",
    "howdy": "hi",
    
    # Farewell-related synonyms
    "farewell": "goodbye",
    "take care": "goodbye",
    
    # Observability & Monitoring
    "monitoring": "observability",
    "telemetry": "observability",
    "logs": "observability",
    "tracking": "observability",
    "metrics": "observability",
    
    # Clarification
    "clarify": "explain",
    "elaborate": "explain",
    "detail": "explain",
    "mean": "explain",
    "understand": "explain",
    
    # Support & Help
    "assistance": "help",
    "support": "help",
    "aid": "help",
    "issue": "problem",
    "error": "problem",
    "bug": "problem",
    
    # Contact
    "call": "contact",
    "email": "contact",
    "reach": "contact",
    "message": "contact",
    
    # Human escalation
    "person": "human",
    "agent": "human",
    "representative": "human",
    "real": "human"
}

def canonical(word):
    """
    Returns the canonical form of a word if it exists in the map, 
    otherwise returns the word itself.
    """
    if not word:
        return ""
    
    word = word.lower().strip()
    return SYNONYM_MAP.get(word, word)

def normalize_text(tokens):
    """
    Helper to normalize a list of tokens using the canonical map.
    """
    return [canonical(t) for t in tokens]