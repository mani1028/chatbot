"""
Memory Compression Layer

Converts:
- Full chat history
- Unstructured messages
- Scattered entities

Into:
- Short-term: Last N messages
- Structured: Extracted entities
- Compressed: LLM-friendly summary

This reduces token costs and improves LLM quality.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from models.conversation_thread import ConversationThread
from config import ensure_thread_integrity
import logging

logger = logging.getLogger(__name__)


class MemoryCompressor:
    """
    Compress conversation memory for LLM consumption.
    
    Three-tier memory model:
    1. Short-term: Recent messages for context
    2. Structured: Extracted entities, clean data
    3. Long-term: Compressed summary for background context
    """
    
    # How many recent messages to keep
    SHORT_TERM_LENGTH = 5
    
    @staticmethod
    def compress_conversation(thread: ConversationThread) -> Dict[str, Any]:
        """
        Compress thread data into efficient LLM context.
        
        Returns:
        {
            'short_term': [{role, content, timestamp}],
            'structured': {name, email, phone, ...},
            'summary': "User booking haircut...",
            'metadata': {steps_completed, workflow_type, ...}
        }
        """
        
        # 1. SHORT-TERM: Last 5 messages
        short_term = MemoryCompressor._extract_short_term(thread)
        
        # 2. STRUCTURED: Clean entities
        structured = MemoryCompressor._extract_structured(thread)
        
        # 3. SUMMARY: Compressed narrative
        summary = MemoryCompressor._generate_summary(
            thread,
            short_term,
            structured
        )
        
        # 4. METADATA: Key statistics
        metadata = {
            'steps_completed': thread.steps_completed,
            'workflow_type': thread.workflow_type,
            'current_step': thread.current_step,
            'total_turns': thread.total_turns,
            'unknown_intents': thread.unknown_intent_count,
            'status': thread.workflow_status
        }
        
        return {
            'short_term': short_term,
            'structured': structured,
            'summary': summary,
            'metadata': metadata
        }
    
    @staticmethod
    def _extract_short_term(thread: ConversationThread) -> List[Dict[str, Any]]:
        """Extract most recent messages (optimized for token count)"""
        messages = thread.short_term_messages or []
        
        # Return last 5 messages, format clean
        recent = []
        for msg in messages[-MemoryCompressor.SHORT_TERM_LENGTH:]:
            recent.append({
                'role': msg.get('role'),
                'content': msg.get('content'),
                'timestamp': msg.get('timestamp')
            })
        
        return recent
    
    @staticmethod
    def _extract_structured(thread: ConversationThread) -> Dict[str, Any]:
        """Extract clean structured data (no nulls, no formatting)"""
        structured = {}
        
        for key, value in (thread.structured_data or {}).items():
            # Only include non-null, non-empty values
            if value and str(value).strip():
                structured[key] = str(value).strip()
        
        return structured
    
    @staticmethod
    def _generate_summary(
        thread: ConversationThread,
        short_term: List[Dict],
        structured: Dict[str, Any]
    ) -> str:
        """
        Generate concise summary for LLM context.
        
        Example output:
        "User wants: booking. Service: haircut. Name: John Smith.
         Email: john@test.com. Phone: (555) 123-4567. Current step: collecting date."
        """
        
        parts = []
        
        # Workflow context
        if thread.workflow_type:
            parts.append(f"Workflow: {thread.workflow_type}")
        
        # User intent (from last user message)
        if short_term:
            for msg in reversed(short_term):
                if msg['role'] == 'user':
                    user_intent = msg['content']
                    if len(user_intent) > 100:
                        user_intent = user_intent[:100] + "..."
                    parts.append(f"User said: {user_intent}")
                    break
        
        # Structured data (clean list)
        if structured:
            data_str = ", ".join(
                [f"{k}: {v}" for k, v in structured.items()]
            )
            parts.append(f"Info collected: {data_str}")
        
        # Current step
        if thread.current_step:
            parts.append(f"Current step: {thread.current_step}")
        
        # Status flags
        if thread.escalation_triggered:
            parts.append("Status: Marked for escalation")
        
        if thread.unknown_intent_count > 0:
            parts.append(f"Unknown intents: {thread.unknown_intent_count}")
        
        summary = ". ".join(parts)
        return summary
    
    @staticmethod
    def build_llm_context(thread: ConversationThread) -> str:
        """
        Build ready-to-use context string for LLM.
        
        Returns single string: "Workflow: booking. Info: name=John, email=...
         Current: collecting_phone. Unknown intents: 0"
        """
        
        compressed = MemoryCompressor.compress_conversation(thread)
        
        # Combine into single prompt context
        parts = []
        
        # Summary is the main narrative
        parts.append(compressed['summary'])
        
        # Add recent user message for immediate context
        if compressed['short_term']:
            for msg in reversed(compressed['short_term']):
                if msg['role'] == 'user':
                    parts.append(f"Latest: {msg['content']}")
                    break
        
        # Metadata for decision-making
        meta = compressed['metadata']
        if meta.get('status') != 'active':
            parts.append(f"Status: {meta.get('status')}")
        
        return "\n".join(parts)


class MemoryRecaller:
    """
    Recall relevant memory from conversation history.
    
    Used to answer questions like:
    - "What's the user's email?"
    - "What step are we on?"
    - "How many unknown intents so far?"
    """
    
    @staticmethod
    def recall_entity(thread: ConversationThread, entity_name: str) -> Optional[Any]:
        """Recall specific entity from structured data"""
        return thread.structured_data.get(entity_name)
    
    @staticmethod
    def recall_entities_by_type(thread: ConversationThread, entity_type: str) -> Dict[str, Any]:
        """
        Recall entities by type pattern.
        
        Example: recall_entities_by_type(thread, "contact")
        Returns: {email, phone, name}
        """
        
        contact_fields = ['email', 'phone', 'name']
        payment_fields = ['amount', 'card_number', 'account']
        date_fields = ['date', 'time', 'day']
        
        type_map = {
            'contact': contact_fields,
            'payment': payment_fields,
            'datetime': date_fields
        }
        
        fields = type_map.get(entity_type.lower(), [])
        
        result = {}
        for field in fields:
            value = thread.structured_data.get(field)
            if value:
                result[field] = value
        
        return result
    
    @staticmethod
    def recall_recent_messages(thread: ConversationThread, count: int = 3) -> List[Dict[str, str]]:
        """Recall recent messages for context"""
        messages = thread.short_term_messages or []
        return [
            {'role': m['role'], 'content': m['content']}
            for m in messages[-count:]
        ]
    
    @staticmethod
    def recall_conversation_state(thread: ConversationThread) -> Dict[str, Any]:
        """Recall key state info"""
        return {
            'workflow': thread.workflow_type,
            'status': thread.workflow_status,
            'current_step': thread.current_step,
            'steps_completed': thread.steps_completed,
            'total_turns': thread.total_turns,
            'unknown_intents': thread.unknown_intent_count,
            'escalation_triggered': thread.escalation_triggered,
            'completion_score': round(thread.completion_score, 2)
        }
    
    @staticmethod
    def recall_all(thread: ConversationThread) -> Dict[str, Any]:
        """Recall everything about conversation"""
        return {
            'entities': thread.structured_data,
            'recent_messages': MemoryRecaller.recall_recent_messages(thread, count=3),
            'state': MemoryRecaller.recall_conversation_state(thread),
            'summary': MemoryCompressor.build_llm_context(thread)
        }


class MemoryOptimizer:
    """
    Optimize memory storage and retrieval.
    
    Ensures:
    - No redundant data
    - Efficient queries
    - Clean data model
    - Fast lookups
    """
    
    @staticmethod
    def cleanup_expired_threads(site_id: str, keep_days: int = 7) -> int:
        """
        Remove expired conversation threads for SPECIFIC site.
        
        CRITICAL: site_id is REQUIRED to prevent cross-tenant data deletion.
        """
        from datetime import datetime, timedelta
        from database import db
        
        cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
        
        expired = ConversationThread.query.filter(
            ConversationThread.site_id == site_id,
            ConversationThread.expires_at < datetime.utcnow(),
            ConversationThread.created_at < cutoff_date
        ).delete()
        
        db.session.commit()
        logger.info(f"Cleaned up {expired} expired threads for site_id={site_id}")
        
        return expired
    
    @staticmethod
    def get_trimmed_history(thread: ConversationThread, keep_count: int = 5):
        """
        Return trimmed copy of short-term memory WITHOUT mutating thread.
        
        Only MessageOrchestrator decides whether to apply this.
        """
        if len(thread.short_term_messages) > keep_count:
            return thread.short_term_messages[-keep_count:]
        return thread.short_term_messages
    
    @staticmethod
    def deduplicate_entities(thread: ConversationThread):
        """Remove duplicate/stale entity values"""
        # Keep only the most recent value for each entity
        seen = {}
        cleaned = {}
        
        for key, value in thread.structured_data.items():
            if key not in seen:
                cleaned[key] = value
                seen[key] = True
        
        thread.structured_data = cleaned
        import database as db_module
        db_module.db.session.commit()
