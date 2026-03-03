"""
Entity Extraction Engine
Extracts structured data (name, email, phone, date) from user messages.
Supports:
- Regex patterns
- LLM extraction (fallback)
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extracts entities from user messages using regex and patterns."""
    
    # Regex patterns for common entities
    PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'phone': r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        'date': r'\b((?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|tomorrow|today|(?:0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?(?:\s+(?:of\s+)?)?(?:jan|january|feb|february|mar|march|apr|april|may|june|july|aug|august|sep|september|oct|october|nov|november|dec|december)(?:\s+\d{4})?)\b',
        'time': r'\b(?:0?[0-9]|1[0-9]|2[0-3]):?[0-5][0-9](?:\s*(?:am|pm|AM|PM))?\b',
    }
    
    @staticmethod
    def extract_name(message: str) -> str:
        """Extract name from message."""
        # Pattern: "My name is John" or "I'm John" or "Call me John"
        patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"my name's (\w+)",
            r"this is (\w+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return match.group(1).capitalize()
        
        return None
    
    @staticmethod
    def extract_email(message: str) -> str:
        """Extract email from message."""
        match = re.search(EntityExtractor.PATTERNS['email'], message)
        return match.group(0) if match else None
    
    @staticmethod
    def extract_phone(message: str) -> str:
        """Extract phone number from message."""
        match = re.search(EntityExtractor.PATTERNS['phone'], message)
        return match.group(0) if match else None
    
    @staticmethod
    def extract_date(message: str) -> str:
        """Extract date from message and convert to ISO format (YYYY-MM-DD)."""
        message_lower = message.lower()
        
        # Handle relative dates
        today = datetime.now().date()
        
        if 'tomorrow' in message_lower:
            return (today + timedelta(days=1)).isoformat()
        
        if 'today' in message_lower:
            return today.isoformat()
        
        # Handle day names
        days = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        for day_name, day_num in days.items():
            if day_name in message_lower:
                # Find next occurrence of this day
                current_day = today.weekday()
                days_ahead = day_num - current_day
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = today + timedelta(days=days_ahead)
                return target_date.isoformat()
        
        # Regex-based date extraction
        match = re.search(EntityExtractor.PATTERNS['date'], message, re.IGNORECASE)
        if match:
            return match.group(0)
        
        return None
    
    @staticmethod
    def extract_time(message: str) -> str:
        """Extract time from message."""
        match = re.search(EntityExtractor.PATTERNS['time'], message)
        return match.group(0) if match else None
    
    @staticmethod
    def extract_company(message: str) -> str:
        """Extract company name (basic: after 'company' keyword)."""
        pattern = r"(?:company|organization|firm|business)(?:\s+(?:is|name|called))?\s+(\w+(?:\s+\w+)?(?:\s+\w+)?)"
        match = re.search(pattern, message.lower())
        return match.group(1).title() if match else None
    
    @staticmethod
    def extract_all(message: str) -> Dict[str, Any]:
        """Extract all available entities from message."""
        entities = {}
        
        # Extract each entity type
        name = EntityExtractor.extract_name(message)
        if name:
            entities['name'] = name
        
        email = EntityExtractor.extract_email(message)
        if email:
            entities['email'] = email
        
        phone = EntityExtractor.extract_phone(message)
        if phone:
            entities['phone'] = phone
        
        date_val = EntityExtractor.extract_date(message)
        if date_val:
            entities['date'] = date_val
        
        time_val = EntityExtractor.extract_time(message)
        if time_val:
            entities['time'] = time_val
        
        company = EntityExtractor.extract_company(message)
        if company:
            entities['company'] = company
        
        return entities
    
    @staticmethod
    def llm_extract(message: str, site_id: int, entity_names: list = None) -> Dict[str, Any]:
        """
        Use LLM to extract specific entities (fallback for complex extraction).
        entity_names: ["name", "email", "phone", "date"] - which entities to extract
        """
        if not entity_names:
            entity_names = ["name", "email", "phone", "date"]
        
        try:
            # NOTE: LLM extraction now handled by orchestrator only
            # Service layer returns signal, orchestrator decides
            return {}
        
        except Exception:
            pass
        
        # Fallback if orchestrator cannot call LLM
        return {}
            
    def extract_entities_with_llm_OLD(self, message: str, site_id: int, entity_names: list = None):
        """DEPRECATED: Use orchestrator._run_llm() instead."""
        try:
            from services.intent_service import llm_fallback
            
            prompt = f"""Extract the following entities from this message. Return as JSON.
            
Message: "{message}"
Entities to extract: {', '.join(entity_names)}

Return ONLY valid JSON, e.g.: {{"name": "John", "email": "john@example.com"}}
If an entity is not found, omit it from the response."""
            
            response = llm_fallback(prompt, site_id)
            
            # Try to parse JSON from response
            import json
            # Find JSON in response (sometimes LLM adds extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                extracted = json.loads(json_match.group())
                logger.info(f"LLM extracted entities: {extracted}")
                return extracted
                
        except Exception as e:
            logger.debug(f"LLM extraction failed: {e}")
        
        return {}


def extract_entities(message: str, site_id: int = None, use_llm: bool = False) -> Dict[str, Any]:
    """
    Main entry point for entity extraction.
    First tries regex patterns, optionally falls back to LLM.
    """
    # First: try regex-based extraction
    entities = EntityExtractor.extract_all(message)
    
    # If missing critical fields and LLM available, try LLM extraction
    if use_llm and site_id:
        try:
            llm_entities = EntityExtractor.llm_extract(message, site_id)
            entities.update(llm_entities)
        except Exception as e:
            logger.debug(f"LLM extraction optional fallback failed: {e}")
    
    return entities
