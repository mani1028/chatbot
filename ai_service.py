"""
AI Service - Intent-based semantic matching with confidence engine
"""
from models import Intent, FAQ, ChatLog, UnansweredQuestion, Lead, db
from config import (
    HIGH_CONFIDENCE_THRESHOLD, 
    MEDIUM_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
    FALLBACK_MESSAGES,
    CONFIDENCE_RESPONSES
)
import random
import re
from datetime import datetime

class AIService:
    """
    Advanced AI Service for intent-based matching with confidence engine
    Implements multi-tiered confidence scoring and hybrid fallback
    """
    
    @staticmethod
    def tokenize(text):
        """
        Tokenize text into words, removing special characters
        """
        text = text.lower()
        # Remove special characters and split
        tokens = re.findall(r'\w+', text)
        return set(tokens)
    
    @staticmethod
    def calculate_similarity(query, target_text):
        """
        Calculate enhanced similarity between query and target
        Uses token-based matching with keyword importance weighting
        
        Returns similarity score between 0 and 1
        """
        query_tokens = AIService.tokenize(query)
        target_tokens = AIService.tokenize(target_text)
        
        if not query_tokens or not target_tokens:
            return 0.0
        
        # Jaccard similarity (intersection / union)
        intersection = len(query_tokens & target_tokens)
        union = len(query_tokens | target_tokens)
        jaccard_score = intersection / union if union > 0 else 0.0
        
        # Length ratio penalty/boost
        length_ratio = min(len(query_tokens), len(target_tokens)) / max(len(query_tokens), len(target_tokens))
        
        # Combined score with length weighting
        combined_score = (jaccard_score * 0.7) + (length_ratio * 0.3)
        
        return min(combined_score, 1.0)
    
    @staticmethod
    def find_best_intent_match(user_message):
        """
        Find the best matching intent for user message
        Score all intents and return the highest match
        
        Returns:
            tuple: (intent_object, confidence_score) or (None, 0)
        """
        intents = Intent.query.all()
        
        if not intents:
            return None, 0
        
        best_match = None
        best_score = 0
        
        for intent in intents:
            training_phrases = intent.get_training_phrases()
            
            # Calculate max similarity across all training phrases
            max_phrase_score = 0
            for phrase in training_phrases:
                score = AIService.calculate_similarity(user_message, phrase)
                max_phrase_score = max(max_phrase_score, score)
            
            # Also match against intent name
            intent_name_score = AIService.calculate_similarity(user_message, intent.intent_name)
            final_score = max(max_phrase_score, intent_name_score * 0.8)  # Slightly lower weight for name
            
            if final_score > best_score:
                best_score = final_score
                best_match = intent
        
        return best_match, best_score
    
    @staticmethod
    def find_best_faq_match(user_message):
        """
        Find the best matching FAQ for user message (fallback to legacy FAQs)
        
        Returns:
            tuple: (faq_object, confidence_score) or (None, 0)
        """
        faqs = FAQ.query.all()
        
        if not faqs:
            return None, 0
        
        best_match = None
        best_score = 0
        
        for faq in faqs:
            score = AIService.calculate_similarity(user_message, faq.question)
            
            if score > best_score:
                best_score = score
                best_match = faq
        
        return best_match, best_score
    
    @staticmethod
    def determine_response_type(confidence_score, requires_handoff):
        """
        Determine response type based on confidence level
        
        Returns:
            str: 'high', 'medium', 'low', or 'handoff'
        """
        if confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
            return 'high'
        elif confidence_score >= MEDIUM_CONFIDENCE_THRESHOLD:
            return 'medium'
        elif confidence_score < LOW_CONFIDENCE_THRESHOLD or requires_handoff:
            return 'handoff'
        else:
            return 'low'
    
    @staticmethod
    def get_bot_response(user_message, session_id):
        """
        Main method to get bot response with confidence engine
        
        Implements three-tier system:
        - Score >= 0.8: Auto-respond with detailed response
        - Score 0.5-0.8: Respond with short response + helpful hint
        - Score < 0.5 or requires_handoff: Trigger human handoff
        
        Returns:
            dict: {
                'response': str,
                'confidence': float,
                'intent_id': int or None,
                'message_type': str,
                'requires_handoff': bool
            }
        """
        # Try to find matching intent first
        intent, confidence_score = AIService.find_best_intent_match(user_message)
        faq = None
        faq_score = 0
        
        # If intent match is weak, try FAQ fallback
        if confidence_score < MEDIUM_CONFIDENCE_THRESHOLD:
            faq, faq_score = AIService.find_best_faq_match(user_message)
            if faq_score > confidence_score:
                intent = None
                confidence_score = faq_score
        
        response_type = AIService.determine_response_type(
            confidence_score, 
            intent.requires_handoff if intent else False
        )
        
        # Generate response based on type
        if response_type == 'high' and intent:
            bot_response = f"{CONFIDENCE_RESPONSES['high']}\n\n{intent.detailed_response}"
            message_type = 'auto_response'
            requires_handoff = False
        
        elif response_type == 'high' and faq:
            bot_response = f"{CONFIDENCE_RESPONSES['high']}\n\n{faq.answer}"
            message_type = 'auto_response'
            requires_handoff = False
        
        elif response_type == 'medium' and intent:
            bot_response = f"{CONFIDENCE_RESPONSES['medium']}\n\n{intent.short_response}\n\nWas this helpful?"
            message_type = 'auto_response'
            requires_handoff = False
        
        elif response_type == 'medium' and faq:
            bot_response = f"{CONFIDENCE_RESPONSES['medium']}\n\n{faq.answer}\n\nWas this helpful?"
            message_type = 'auto_response'
            requires_handoff = False
        
        elif response_type == 'low':
            bot_response = CONFIDENCE_RESPONSES['low']
            message_type = 'lead_capture'
            requires_handoff = True
        
        else:  # handoff
            bot_response = CONFIDENCE_RESPONSES['low']
            message_type = 'lead_capture'
            requires_handoff = True
        
        # Log the chat interaction
        chat_log = ChatLog(
            user_message=user_message,
            bot_response=bot_response,
            confidence_score=confidence_score,
            matched_intent_id=intent.id if intent else None,
            matched_faq_id=faq.id if faq else None,
            message_type=message_type,
            session_id=session_id
        )
        db.session.add(chat_log)
        
        # Log unanswered questions
        if not intent and not faq:
            existing = UnansweredQuestion.query.filter_by(
                question=user_message.strip()
            ).first()
            
            if existing:
                existing.times_asked += 1
                existing.last_asked = datetime.utcnow()
            else:
                new_unanswered = UnansweredQuestion(question=user_message.strip())
                db.session.add(new_unanswered)
        
        db.session.commit()
        
        return {
            'response': bot_response,
            'confidence': round(confidence_score, 2),
            'intent_id': intent.id if intent else None,
            'message_type': message_type,
            'requires_handoff': requires_handoff
        }
    
    @staticmethod
    def save_lead(name, email, phone, message, intent_id, session_id):
        """
        Save lead information for human handoff
        
        Returns:
            dict: {'success': bool, 'message': str, 'lead_id': int or None}
        """
        try:
            lead = Lead(
                name=name,
                email=email,
                phone=phone,
                message=message,
                intent_id=intent_id,
                session_id=session_id,
                status='new'
            )
            db.session.add(lead)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Thank you! A team member will contact you shortly.',
                'lead_id': lead.id
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error saving lead: {str(e)}',
                'lead_id': None
            }
    
    @staticmethod
    def add_intent(intent_name, training_phrases, short_response, detailed_response, 
                   category='General', requires_handoff=False):
        """
        Add new intent to database
        
        Args:
            intent_name: Name of the intent
            training_phrases: List of example phrases
            short_response: Brief response
            detailed_response: Detailed response
            category: Intent category
            requires_handoff: Whether this intent requires human handoff
        
        Returns:
            dict: {'success': bool, 'message': str, 'intent_id': int or None}
        """
        try:
            # Check if intent already exists
            existing = Intent.query.filter_by(intent_name=intent_name).first()
            if existing:
                return {'success': False, 'message': 'Intent already exists'}
            
            intent = Intent(
                intent_name=intent_name,
                category=category,
                short_response=short_response,
                detailed_response=detailed_response,
                requires_handoff=requires_handoff
            )
            intent.set_training_phrases(training_phrases)
            
            db.session.add(intent)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Intent added successfully',
                'intent_id': intent.id
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error adding intent: {str(e)}',
                'intent_id': None
            }
    
    @staticmethod
    def update_intent(intent_id, intent_name=None, training_phrases=None, 
                     short_response=None, detailed_response=None, 
                     category=None, requires_handoff=None):
        """
        Update existing intent
        """
        try:
            intent = Intent.query.get(intent_id)
            if not intent:
                return {'success': False, 'message': 'Intent not found'}
            
            if intent_name:
                intent.intent_name = intent_name
            if training_phrases is not None:
                intent.set_training_phrases(training_phrases)
            if short_response:
                intent.short_response = short_response
            if detailed_response:
                intent.detailed_response = detailed_response
            if category:
                intent.category = category
            if requires_handoff is not None:
                intent.requires_handoff = requires_handoff
            
            intent.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {'success': True, 'message': 'Intent updated successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Error updating intent: {str(e)}'}
    
    @staticmethod
    def delete_intent(intent_id):
        """
        Delete intent from database
        """
        try:
            intent = Intent.query.get(intent_id)
            if not intent:
                return {'success': False, 'message': 'Intent not found'}
            
            db.session.delete(intent)
            db.session.commit()
            
            return {'success': True, 'message': 'Intent deleted successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Error deleting intent: {str(e)}'}
    
    @staticmethod
    def get_all_intents():
        """
        Get all intents
        """
        intents = Intent.query.all()
        return [intent.to_dict() for intent in intents]
    
    @staticmethod
    def get_all_faqs():
        """
        Get all FAQs (legacy)
        """
        faqs = FAQ.query.all()
        return [faq.to_dict() for faq in faqs]
    
    @staticmethod
    def get_chat_logs(limit=50):
        """
        Get recent chat logs
        """
        logs = ChatLog.query.order_by(ChatLog.timestamp.desc()).limit(limit).all()
        return [log.to_dict() for log in logs]
    
    @staticmethod
    def get_unanswered_questions(limit=50):
        """
        Get frequently unanswered questions
        """
        questions = UnansweredQuestion.query.order_by(
            UnansweredQuestion.times_asked.desc()
        ).limit(limit).all()
        return [q.to_dict() for q in questions]
    
    @staticmethod
    def get_all_leads(limit=100):
        """
        Get all leads with optional filtering
        """
        leads = Lead.query.order_by(Lead.created_at.desc()).limit(limit).all()
        return [lead.to_dict() for lead in leads]
    
    @staticmethod
    def update_lead(lead_id, status=None, assigned_to=None, notes=None):
        """
        Update lead status and notes
        """
        try:
            lead = Lead.query.get(lead_id)
            if not lead:
                return {'success': False, 'message': 'Lead not found'}
            
            if status:
                lead.status = status
            if assigned_to:
                lead.assigned_to = assigned_to
            if notes:
                lead.notes = notes
            
            lead.updated_at = datetime.utcnow()
            db.session.commit()
            
            return {'success': True, 'message': 'Lead updated successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Error updating lead: {str(e)}'}
