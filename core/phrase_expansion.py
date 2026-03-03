"""
Phrase Expansion: Auto-training logic for unknown message learning.

When admin maps an unknown message to an intent:
1. Message becomes a training phrase
2. Confidence weight tracking begins
3. System learns from corrections over time
"""
from typing import Optional, List
from database import db
from models import IntentPhrase, Intent


class PhraseExpansion:
    """
    Manages automatic phrase training when admins map unknown messages.
    """

    @staticmethod
    def add_training_phrase(
        intent_id: int,
        phrase_text: str,
        auto_normalize: bool = True
    ) -> bool:
        """
        Add a new training phrase to an intent.
        
        Args:
            intent_id: Intent.id
            phrase_text: The user's original message
            auto_normalize: Clean up whitespace/case?
        
        Returns:
            True if phrase was added, False if already exists
        """
        if auto_normalize:
            phrase_text = phrase_text.strip().lower()
        
        # Check if phrase already exists
        existing = IntentPhrase.query.filter_by(
            intent_id=intent_id,
            phrase=phrase_text
        ).first()
        
        if existing:
            return False
        
        # Add new phrase
        phrase = IntentPhrase(
            intent_id=intent_id,
            phrase=phrase_text
        )
        db.session.add(phrase)
        
        try:
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def get_auto_trained_phrases(intent_id: int) -> List[str]:
        """
        Get list of phrases that were auto-trained via admin mapping.
        
        Useful for auditing what the system learned.
        """
        # This would require tracking which phrases were auto-added
        # vs manually created. For now, return all phrases.
        phrases = IntentPhrase.query.filter_by(intent_id=intent_id).all()
        return [p.phrase for p in phrases]

    @staticmethod
    def suggest_phrase_consolidation(intent_id: int) -> List[dict]:
        """
        Suggest consolidating similar phrases within an intent.
        
        Uses fuzzy matching to find near-duplicates.
        
        Returns list of:
        {
            "phrase_1_id": 123,
            "phrase_2_id": 456,
            "similarity": 0.89,
            "suggestion": "Consolidate 'fees' and 'costs' as synonym variants"
        }
        """
        from thefuzz import fuzz
        
        phrases = IntentPhrase.query.filter_by(intent_id=intent_id).all()
        suggestions = []
        
        for i, p1 in enumerate(phrases):
            for j, p2 in enumerate(phrases[i+1:], i+1):
                ratio = fuzz.token_set_ratio(p1.phrase, p2.phrase)
                
                if 70 <= ratio < 100:
                    suggestions.append({
                        'phrase_1_id': p1.id,
                        'phrase_2_id': p2.id,
                        'phrase_1_text': p1.phrase,
                        'phrase_2_text': p2.phrase,
                        'similarity': ratio / 100.0,
                        'suggestion': f"Consider consolidating or marking as synonyms"
                    })
        
        return sorted(suggestions, key=lambda x: x['similarity'], reverse=True)
