"""
AI Service - Semantic matching and response generation
"""
from models import FAQ, ChatLog, UnansweredQuestion, db
from config import CONFIDENCE_THRESHOLD, FALLBACK_MESSAGES
import random
import math
from datetime import datetime

class AIService:
    """
    Main AI Service for semantic matching and response generation
    Uses simple cosine similarity for matching FAQs
    """
    
    @staticmethod
    def tokenize(text):
        """
        Simple tokenization - convert text to lowercase words
        """
        return set(text.lower().split())
    
    @staticmethod
    def calculate_similarity(query, faq_question):
        """
        Calculate similarity between user query and FAQ question
        Using Jaccard similarity (simple token-based approach)
        
        Returns similarity score between 0 and 1
        """
        query_tokens = AIService.tokenize(query)
        faq_tokens = AIService.tokenize(faq_question)
        
        if not query_tokens or not faq_tokens:
            return 0.0
        
        # Jaccard similarity: intersection / union
        intersection = len(query_tokens & faq_tokens)
        union = len(query_tokens | faq_tokens)
        
        jaccard_score = intersection / union if union > 0 else 0
        
        # Boost score if there's significant token overlap
        # and questions are not too different in length
        length_ratio = min(len(query_tokens), len(faq_tokens)) / max(len(query_tokens), len(faq_tokens))
        boosted_score = jaccard_score * 0.7 + (length_ratio * 0.3)
        
        return min(boosted_score, 1.0)
    
    @staticmethod
    def find_best_match(user_message):
        """
        Find the best matching FAQ for user message
        
        Returns:
            tuple: (faq_object, confidence_score) or (None, 0)
        """
        # Get all FAQs
        faqs = FAQ.query.all()
        
        if not faqs:
            return None, 0
        
        best_match = None
        best_score = 0
        
        # Calculate similarity with all FAQs
        for faq in faqs:
            score = AIService.calculate_similarity(user_message, faq.question)
            
            if score > best_score:
                best_score = score
                best_match = faq
        
        return best_match, best_score
    
    @staticmethod
    def get_bot_response(user_message, session_id):
        """
        Main method to get bot response for user message
        
        Returns:
            dict: {
                'response': str (bot message),
                'confidence': float,
                'faq_id': int or None,
                'is_answered': bool
            }
        """
        # Find best matching FAQ
        faq, confidence_score = AIService.find_best_match(user_message)
        
        # Check if confidence is above threshold
        if confidence_score >= CONFIDENCE_THRESHOLD and faq:
            # Use FAQ answer
            bot_response = faq.answer
            is_answered = True
            matched_faq_id = faq.id
        else:
            # Use fallback message
            bot_response = random.choice(FALLBACK_MESSAGES)
            is_answered = False
            matched_faq_id = None
        
        # Log the chat interaction
        chat_log = ChatLog(
            user_message=user_message,
            bot_response=bot_response,
            confidence_score=confidence_score,
            matched_faq_id=matched_faq_id,
            session_id=session_id
        )
        db.session.add(chat_log)
        
        # If not answered and question is novel, log as unanswered
        if not is_answered:
            # Check if this question was already asked
            existing = UnansweredQuestion.query.filter_by(
                question=user_message.strip()
            ).first()
            
            if existing:
                # Increment count and update last_asked
                existing.times_asked += 1
                existing.last_asked = datetime.utcnow()
            else:
                # Add new unanswered question
                new_unanswered = UnansweredQuestion(
                    question=user_message.strip()
                )
                db.session.add(new_unanswered)
        
        db.session.commit()
        
        return {
            'response': bot_response,
            'confidence': round(confidence_score, 2),
            'faq_id': matched_faq_id,
            'is_answered': is_answered
        }
    
    @staticmethod
    def add_faq(question, answer, category='General'):
        """
        Add new FAQ to database
        """
        # Check if question already exists
        existing = FAQ.query.filter_by(question=question).first()
        if existing:
            return {'success': False, 'message': 'FAQ question already exists'}
        
        faq = FAQ(
            question=question,
            answer=answer,
            category=category
        )
        db.session.add(faq)
        db.session.commit()
        
        return {'success': True, 'message': 'FAQ added successfully', 'faq_id': faq.id}
    
    @staticmethod
    def update_faq(faq_id, question=None, answer=None, category=None):
        """
        Update existing FAQ
        """
        faq = FAQ.query.get(faq_id)
        if not faq:
            return {'success': False, 'message': 'FAQ not found'}
        
        if question:
            faq.question = question
        if answer:
            faq.answer = answer
        if category:
            faq.category = category
        
        faq.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {'success': True, 'message': 'FAQ updated successfully'}
    
    @staticmethod
    def delete_faq(faq_id):
        """
        Delete FAQ from database
        """
        faq = FAQ.query.get(faq_id)
        if not faq:
            return {'success': False, 'message': 'FAQ not found'}
        
        db.session.delete(faq)
        db.session.commit()
        
        return {'success': True, 'message': 'FAQ deleted successfully'}
    
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
    def get_all_faqs():
        """
        Get all FAQs
        """
        faqs = FAQ.query.all()
        return [faq.to_dict() for faq in faqs]
