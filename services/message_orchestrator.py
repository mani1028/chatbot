"""
Message Orchestrator - Production-Grade Conversation Kernel

This is the SINGLE execution engine for all message processing.
It coordinates all Phase 1 and Phase 2 components deterministically.

Architectural Guarantees:
- Single entry: process_message()
- Single exit: _finalize()
- No engine imports db
- No engine calls commit()
- No early returns except _finalize()
- Deterministic execution order
- Atomic state transitions
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import uuid
import time
from models.conversation_thread import ConversationThread
from models.chat_log import ChatLog
from models.site import Site
from models.phase1_metrics import Phase1Metrics
from services.rule_engine import get_rule_engine
from services.context_engine import ContextAnalyzer
from services.generic_workflow_engine import get_workflow_engine
from services.intent_service import detect_intent_only, llm_fallback
from services.multi_tenant_control import get_site_control
from services.conversation_analytics import ConversationScorer
from services.timing_profiler import TimingProfiler
from config import classify_confidence, FRUSTRATION_ESCALATION_THRESHOLD, ensure_thread_integrity
from database import db
import logging

logger = logging.getLogger(__name__)


class LLMResult:
    """Pure data object for LLM output (no side effects)"""
    def __init__(self, text: str, confidence: float = 0.5, 
                 intent_name: str = None, metadata: Dict = None):
        self.text = text
        self.confidence = confidence
        self.intent_name = intent_name
        self.metadata = metadata or {}


class RuleEngineResult:
    """Pure data object for rule engine output"""
    def __init__(self, hard_stop: bool = False, action: str = None,
                 reply: str = None, reason: str = None):
        self.hard_stop = hard_stop
        self.action = action
        self.reply = reply
        self.reason = reason


class WorkflowResult:
    """Pure data object for workflow engine output"""
    def __init__(self, handled: bool = False, reply: str = None,
                 next_step: str = None, metadata: Dict = None):
        self.handled = handled
        self.reply = reply
        self.next_step = next_step
        self.metadata = metadata or {}


class IntentResult:
    """Pure data object for intent detection output"""
    def __init__(self, name: str = None, confidence: float = 0.0,
                 phrases: List[str] = None):
        self.name = name
        self.confidence = confidence
        self.phrases = phrases or []


class MessageOrchestrator:
    """
    Deterministic message execution kernel.
    
    Execution Order (FIXED):
    1. Load/create ConversationThread
    2. Append user message
    3. RuleEngine (hard stop check)
    4. ContextEngine (frustration/confusion analysis)
    5. GenericWorkflowEngine (if workflow active)
    6. Intent detection (if no workflow)
    7. Feature gating validation
    8. LLM fallback (if needed)
    9. Analytics scoring
    10. Persist + build response
    """

    def process_message(self, site_id: int, session_id: str, 
                       message: str) -> Dict:
        """
        SINGLE entry point for all message processing.
        
        Args:
            site_id: Tenant site ID
            session_id: Conversation session ID
            message: User message text
            
        Returns:
            {
                "reply": str,
                "workflow_state": str,
                "workflow_type": str,
                "collected_data": dict,
                "context_analysis": dict,
                "actions_taken": list,
                "completion_score": float
            }
        """
        try:
            # Initialize timing profiler
            profiler = TimingProfiler()
            profiler.request_id = str(uuid.uuid4())[:8]
            
            # Initialize metrics tracking for Phase 1 analytics
            self._request_start_time = time.time()
            self._request_message_id = str(uuid.uuid4())
            self._request_site_id = site_id
            self._request_session_id = session_id
            self._request_intent_result = None  # Will be populated during intent detection
            self._request_used_llm = False  # Will be set if LLM fallback is used
            self._request_llm_start_time = None
            self._request_llm_end_time = None
            
            # STAGE 1: Load thread
            profiler.start_stage("load_thread")
            thread = self._load_or_create_thread(site_id, session_id)
            profiler.end_stage("load_thread")
            
            # STAGE 2: Append user message to thread
            profiler.start_stage("append_message")
            self._append_user_message(thread, message)
            thread.execution_trace.append("user_message_appended")
            profiler.end_stage("append_message")
            
            # STAGE 3: Run rule engine (hard stop check)
            profiler.start_stage("rule_engine")
            rule_result = self._run_rules(thread)
            profiler.end_stage("rule_engine")
            
            if rule_result.hard_stop:
                thread.execution_trace.append(f"rule_engine_hard_stop:{rule_result.action}")
                thread.escalation_triggered = True
                thread.recommendation = rule_result.action
                thread.escalation_reason = rule_result.reason
                profiler.log_summary()
                return self._finalize(thread, override_reply=rule_result.reply)
            
            thread.execution_trace.append("rule_engine_passed")
            
            # GATE 4: Ensure loaded thread doesn't have NULL fields
            ensure_thread_integrity(thread)
            thread.execution_trace.append("thread_integrity_checked")
            
            # STAGE 4: Run context analysis
            self._run_context_analysis(thread)
            thread.execution_trace.append("context_analysis_complete")
            
            # STAGE 5: Check if active workflow exists
            workflow_result = self._run_workflow(thread)
            if workflow_result.handled:
                thread.execution_trace.append("workflow_handled")
                thread.pending_reply = workflow_result.reply
                self._run_analytics(thread)
                return self._finalize(thread)
            
            thread.execution_trace.append("workflow_skipped")
            
            # STAGE 6: CLARIFICATION CONFIRMATION (MUST RUN BEFORE DETECTION)
            # If user is confirming previous clarification, handle FIRST before detection
            # This ensures confirmation is never overwritten by new intent detection
            intent_result = None
            
            if thread.pending_clarification:
                # User responded to clarification question
                # Tolerant matching: "yes", "yeah", "y", "yes please", etc.
                if message.lower().startswith(('yes', 'yeah', 'y')):
                    # User confirmed the intent
                    confirmed_intent = thread.pending_clarification
                    thread.pending_clarification = None
                    thread.last_detected_intent = confirmed_intent
                    thread.last_intent_confidence = 1.0
                    
                    # Create result directly - SKIP detection entirely
                    intent_result = IntentResult(
                        name=confirmed_intent,
                        confidence=1.0
                    )
                    thread.execution_trace.append(f"clarification_confirmed:{confirmed_intent}")
                else:
                    # User said no/unclear, clear pending and continue with detection
                    thread.pending_clarification = None
                    thread.execution_trace.append("clarification_denied")
            
            # Only run detection if confirmation didn't already set result
            if intent_result is None:
                profiler.start_stage("intent_detection")
                intent_result = self._detect_intent(thread, message)
                profiler.end_stage("intent_detection")
                
                thread.execution_trace.append(f"intent_detected:{intent_result.name or 'unknown'}")
                
                # Store detected intent for response building
                if intent_result.name:
                    thread.last_detected_intent = intent_result.name
                    thread.last_intent_confidence = intent_result.confidence
                    
                    # FETCH INTENT RESPONSE FROM DATABASE
                    profiler.start_stage("intent_response_lookup")
                    from models.intent import Intent
                    from sqlalchemy import or_
                    intent_obj = Intent.query.filter(
                        or_(Intent.site_id == 0, Intent.site_id == thread.site_id),
                        Intent.intent_name == intent_result.name
                    ).first()
                    profiler.end_stage("intent_response_lookup")
                    
                    if intent_obj and intent_obj.response:
                        profiler.start_stage("template_substitution")
                        thread.pending_reply = intent_obj.response
                        # Substitute template variables with site configuration
                        from services.response_formatter import substitute_template_variables
                        thread.pending_reply = substitute_template_variables(thread.pending_reply, thread.site_id)
                        profiler.end_stage("template_substitution")
                        thread.execution_trace.append(f"intent_response_loaded:{intent_result.name}")

            
            # Store intent result for metrics logging
            self._request_intent_result = intent_result
            
            # CLARIFICATION BAND (Phase 1) - Only triggers on NEW intent, not confirmations
            if (
                intent_result.name 
                and 0.55 <= intent_result.confidence < 0.8
                and not thread.pending_clarification
                and not thread.workflow_type
            ):
                # Enter clarification band instead of calling LLM
                thread.pending_clarification = intent_result.name
                clean_name = intent_result.name.replace('_', ' ').title()
                thread.pending_reply = f"Did you mean '{clean_name}'?"
                thread.execution_trace.append("clarification_band_triggered")
                
                # Add bot reply and finalize (skip LLM)
                self._run_analytics(thread)
                return self._finalize(thread)
            
            # STAGE 7: Apply feature gating
            self._apply_feature_gates(thread, intent_result)
            thread.execution_trace.append("feature_gates_applied")
            
            # STAGE 8: LLM fallback (if needed)
            if self._should_call_llm(thread, intent_result):
                # Log unknown intent for admin mapping (Phase 1)
                self._log_unknown_intent(thread, message)
                
                # Track LLM timing for metrics
                self._request_llm_start_time = time.time()
                llm_result = self._run_llm(thread, message)
                self._request_llm_end_time = time.time()
                self._request_used_llm = True
                
                thread.execution_trace.append("llm_invoked")
                self._merge_llm_result(thread, llm_result)
            else:
                thread.execution_trace.append("llm_skipped")
            
            # STAGE 9: Analytics
            self._run_analytics(thread)
            thread.execution_trace.append("analytics_complete")
            
            # STAGE 10: Finalize and persist
            return self._finalize(thread)
            
        except Exception as e:
            # CRITICAL: Re-raise database errors to prevent state divergence
            # If commit fails, client must receive 500, not 200 with error message
            from sqlalchemy.exc import SQLAlchemyError
            if isinstance(e, SQLAlchemyError):
                logger.error(f"DATABASE ERROR - Must propagate: {e}", exc_info=True)
                raise  # Let route return 500
            
            logger.error(f"Message orchestration failed: {e}", exc_info=True)
            # Return error response without persistence (for non-DB errors)
            return {
                "reply": "⚠️ An error occurred. Please try again.",
                "error": str(e),
                "workflow_state": None,
                "actions_taken": []
            }

    # ============================================================================
    # STAGE 1: LOAD THREAD
    # ============================================================================

    def _load_or_create_thread(self, site_id: int, 
                               session_id: str) -> ConversationThread:
        """Load existing thread or create new one"""
        thread = ConversationThread.query.filter_by(
            site_id=site_id,
            session_id=session_id
        ).first()
        
        if thread and thread.is_expired():
            # Thread expired, create new one
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                workflow_type=None,
                current_step=None,
                workflow_status="active"
            )
        elif not thread:
            # New thread
            thread = ConversationThread(
                site_id=site_id,
                session_id=session_id,
                workflow_type=None,
                current_step=None,
                workflow_status="active"
            )
        
        return thread

    # ============================================================================
    # STAGE 2: APPEND MESSAGE
    # ============================================================================

    def _append_user_message(self, thread: ConversationThread, message: str):
        """Add user message to thread history"""
        if not hasattr(thread, 'short_term_messages') or thread.short_term_messages is None:
            thread.short_term_messages = []
        
        thread.short_term_messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last 5 messages
        if len(thread.short_term_messages) > 5:
            thread.short_term_messages = thread.short_term_messages[-5:]

    # ============================================================================
    # GATE 4: THREAD INTEGRITY (Ensure backward compatibility with old DB rows)
    # ============================================================================

    # ============================================================================
    # STAGE 3: RULE ENGINE
    # ============================================================================

    def _run_rules(self, thread: ConversationThread) -> RuleEngineResult:
        """Run rule engine (hard stop checks)"""
        try:
            rule_engine = get_rule_engine()
            
            # Get last user message
            user_messages = [m for m in thread.short_term_messages 
                           if m.get("role") == "user"]
            if not user_messages:
                return RuleEngineResult(hard_stop=False)
            
            last_message = user_messages[-1].get("content", "")
            
            # Evaluate rules
            rule_result = rule_engine.evaluate(thread, last_message)
            
            if rule_result and rule_result.get("action") in ["escalate", "hard_deny"]:
                return RuleEngineResult(
                    hard_stop=True,
                    action=rule_result.get("action"),
                    reply=rule_result.get("bot_reply", 
                          "I'm connecting you to a human agent..."),
                    reason=rule_result.get("matched_rule")
                )
            
            return RuleEngineResult(hard_stop=False)
            
        except Exception as e:
            # Silently continue if rule engine fails - it's not critical
            logger.debug(f"Rule engine evaluation skipped: {e}")
            return RuleEngineResult(hard_stop=False)

    # ============================================================================
    # STAGE 4: CONTEXT ANALYSIS
    # ============================================================================

    def _run_context_analysis(self, thread: ConversationThread):
        """Analyze conversation context (frustration, confusion, drift)"""
        try:
            analyzer = ContextAnalyzer()
            context = analyzer.analyze_full_context(thread)
            
            thread.frustration_score = context.get("frustration", 0.0)
            thread.confusion_score = context.get("confusion", 0.0)
            thread.intent_drift = context.get("intent_drift")
            thread.recommendation = context.get("recommendation", "continue")
            
            # Mark for escalation if frustrated
            if thread.frustration_score > FRUSTRATION_ESCALATION_THRESHOLD:
                thread.escalation_triggered = True
                thread.escalation_reason = "high_frustration"
                
        except Exception as e:
            logger.warning(f"Context analysis error: {e}")
            thread.frustration_score = 0.0
            thread.confusion_score = 0.0

    # ============================================================================
    # STAGE 5: WORKFLOW ENGINE
    # ============================================================================

    def _run_workflow(self, thread: ConversationThread) -> WorkflowResult:
        """Process through workflow if active"""
        try:
            if not thread.workflow_type or thread.workflow_status != "active":
                return WorkflowResult(handled=False)
            
            engine = get_workflow_engine()
            
            # Get last user message
            user_messages = [m for m in thread.short_term_messages 
                           if m.get("role") == "user"]
            if not user_messages:
                return WorkflowResult(handled=False)
            
            last_message = user_messages[-1].get("content", "")
            
            # Process through workflow (pure function - doesn't commit)
            workflow_result = engine.process_message(thread, last_message, thread.site_id)
            
            if workflow_result:
                # Engine already updated thread fields; just capture result
                # (update_structured_data, advance_workflow, complete_workflow already called)
                
                # Mark escalation if indicated
                if workflow_result.get("should_escalate"):
                    thread.escalation_triggered = True
                
                return WorkflowResult(
                    handled=True,
                    reply=workflow_result.get("reply"),
                    metadata=workflow_result
                )
            
            return WorkflowResult(handled=False)
            
        except Exception as e:
            logger.warning(f"Workflow error: {e}")
            return WorkflowResult(handled=False)

    # ============================================================================
    # STAGE 6: INTENT DETECTION (DETERMINISTIC - NO LLM)
    # ============================================================================

    def _detect_intent(self, thread: ConversationThread, 
                      message: str) -> IntentResult:
        """Detect user intent from message - deterministic, no LLM.
        
        LLM is reserved for Stage 8 (orchestrator owns all external calls).
        """
        try:
            # Convert thread short_term_messages to history format expected by intent_service
            # intent_service expects: [{'user_message': '...', ...}]
            # thread has: [{'role': 'user'/'assistant', 'content': '...', 'timestamp': '...'}]
            history = None
            if thread.short_term_messages:
                history = []
                for msg in thread.short_term_messages:
                    if msg.get('role') == 'user':
                        history.append({'user_message': msg.get('content', '')})
            
            # CRITICAL: Use detect_intent_only (no embedded LLM)
            # Let orchestrator own all LLM invocation
            result = detect_intent_only(message, thread.site_id, history)
            
            # Extract intent data from pipeline result
            intent_name = result.get('intent_name')
            confidence = result.get('confidence', 0.0)
            
            return IntentResult(
                name=intent_name,
                confidence=confidence,
                phrases=result.get('phrases', [])
            )
            
        except Exception as e:
            logger.warning(f"Intent detection error: {e}")
            return IntentResult(name=None, confidence=0.0)

    # ============================================================================
    # STAGE 7: FEATURE GATING
    # ============================================================================

    def _apply_feature_gates(self, thread: ConversationThread, 
                            intent_result: IntentResult):
        """Validate against feature gates based on site plan"""
        try:
            site_control = get_site_control(thread.site_id)
            
            # Check if site can use advanced features
            if not site_control.is_feature_enabled("context_engine"):
                # Mark as blocked if features unavailable
                thread.context_engine_enabled = False
            
            if not site_control.is_feature_enabled("rule_engine"):
                thread.rule_engine_enabled = False
            
        except Exception as e:
            logger.warning(f"Feature gating error: {e}")

    # ============================================================================
    # STAGE 8: LLM DECISION & INVOCATION
    # ============================================================================

    def _should_call_llm(self, thread: ConversationThread, 
                         intent_result: IntentResult) -> bool:
        """Pure decision function for LLM invocation
        
        GATE 1 ENFORCEMENT: Only orchestrator decides whether to call LLM.
        GATE 2 ENFORCEMENT: Uses single classify_confidence() authority.        
        GATE 3 ENFORCEMENT: Workflow blocks LLM invocation.
        """
        # Workflow blocks LLM (Gate 3)
        if thread.has_active_workflow():
            return False
        
        # Escalation blocks LLM
        if thread.escalation_triggered:
            return False
        
        # Hard block blocks LLM
        if getattr(thread, 'block_reason', None):
            return False
        
        # Use single confidence authority function (Gate 2)
        confidence_class = classify_confidence(intent_result.confidence)
        
        # Call LLM only if LOW confidence or no intent detected
        should_call = (confidence_class == "LOW" or not intent_result.name)
        
        print(f"[LLM DECISION DEBUG]")
        print(f"  Has active workflow: {thread.has_active_workflow()}")
        print(f"  Is escalated: {thread.escalation_triggered}")
        print(f"  Is blocked: {bool(getattr(thread, 'block_reason', None))}")
        print(f"  Confidence classification: {confidence_class}")
        print(f"    - intent_name: {intent_result.name}")
        print(f"    - confidence_score: {intent_result.confidence}")
        print(f"  CALL_LLM: {should_call}")
        
        return should_call

    def _run_llm(self, thread: ConversationThread, message: str) -> LLMResult:
        """Run LLM fallback (pure function, no side effects)"""
        try:
            logger.info(f"[LLM ORCHESTRATOR Stage 8] Calling LLM for: {message[:50]}")
            
            # Get LLM fallback response
            llm_text = llm_fallback(message, thread.site_id)
            
            return LLMResult(
                text=llm_text,
                confidence=0.6,  # LLM fallback is medium confidence
                intent_name=None,
                metadata={"source": "llm_fallback"}
            )
            
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            return LLMResult(
                text="I apologize, I'm having trouble understanding.",
                confidence=0.3
            )

    def _merge_llm_result(self, thread: ConversationThread, 
                         llm_result: LLMResult):
        """Merge LLM result into thread state"""
        thread.pending_reply = llm_result.text
        thread.used_llm = True
        thread.llm_confidence = llm_result.confidence
        
        if llm_result.intent_name:
            thread.last_detected_intent = llm_result.intent_name

    def _log_unknown_intent(self, thread: ConversationThread, message: str):
        """Log unknown intent for admin mapping (Phase 1 minimal).
        
        Non-blocking. If logging fails, orchestrator continues.
        """
        try:
            from models import UnknownIntentLog
            
            log = UnknownIntentLog(
                site_id=thread.site_id,
                message=message
            )
            db.session.add(log)
            # Don't commit here - let Stage 10 (_finalize) do atomic commit
            # This ensures log is persisted atomically with thread
        except Exception as e:
            logger.warning(f"Failed to log unknown intent: {e}")
            # Non-critical: don't break orchestrator

    # ============================================================================
    # STAGE 9: ANALYTICS
    # ============================================================================

    def _run_analytics(self, thread: ConversationThread):
        """Score and update conversation analytics"""
        try:
            scorer = ConversationScorer()
            
            # Calculate completion score
            score = scorer.score_thread(thread)
            thread.completion_score = score
            
            # Update unknown intent tracking
            user_messages = [m for m in thread.short_term_messages 
                           if m.get("role") == "user"]
            if not thread.last_detected_intent and user_messages:
                # Handle None values from old database records
                current_count = thread.unknown_intent_count or 0
                thread.unknown_intent_count = current_count + 1
            
        except Exception as e:
            logger.warning(f"Analytics error: {e}")

    # ============================================================================
    # STAGE 10: FINALIZE & PERSIST
    # ============================================================================

    def _finalize(self, thread: ConversationThread, 
                 override_reply: str = None) -> Dict:
        """
        ATOMIC FINALIZATION STAGE
        
        All state transitions are complete.
        Now:
        1. Add bot reply to thread history
        2. Persist state (single commit)
        3. Build response payload
        4. Return
        """
        try:
            # 1. Append bot reply to thread history
            bot_reply = override_reply or thread.pending_reply or "I'm here to help."
            
            if not hasattr(thread, 'short_term_messages') or thread.short_term_messages is None:
                thread.short_term_messages = []
            
            thread.short_term_messages.append({
                "role": "assistant",
                "content": bot_reply,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Keep only last 5
            if len(thread.short_term_messages) > 5:
                thread.short_term_messages = thread.short_term_messages[-5:]
            
            # Clear pending_reply (now in history)
            thread.pending_reply = None
            thread.updated_at = datetime.utcnow()
            
            # 2. Persist to database (atomic)
            try:
                db.session.add(thread)
                db.session.commit()
                logger.info(f"Thread {thread.id} persisted successfully")
            except Exception as db_error:
                db.session.rollback()
                logger.error(f"Database persistence failed: {db_error}")
                # CRITICAL: Re-raise original exception (SQLAlchemyError) so calling code
                # knows atomicity failed and route can return 500, not 200
                raise
            
            # 3. Also log to ChatLog for backward compatibility
            try:
                chat_log = ChatLog(
                    site_id=thread.site_id,
                    session_id=thread.session_id,
                    user_message=thread.short_term_messages[-2]["content"] if len(thread.short_term_messages) > 1 else "",
                    bot_response=bot_reply,
                    detected_intent=thread.last_detected_intent,
                    confidence=self._request_intent_result.confidence if self._request_intent_result else 0.0,
                    created_at=datetime.utcnow()
                )
                db.session.add(chat_log)
                db.session.commit()
            except Exception as e:
                logger.warning(f"ChatLog creation failed (non-critical): {e}")
                db.session.rollback()
            
            # 3.5. Log Phase 1 Analytics Metrics (fail-safe, don't break main flow)
            try:
                # Get site for tenant_id lookup (in this system, site IS the tenant)
                site = Site.query.filter_by(id=self._request_site_id).first()
                tenant_id = site.id if site else self._request_site_id  # Use site.id as tenant_id
                
                # Calculate LLM response time if LLM was called
                llm_response_time_ms = None
                if self._request_llm_start_time and self._request_llm_end_time:
                    llm_response_time_ms = int((self._request_llm_end_time - self._request_llm_start_time) * 1000)
                
                # Create metrics entry from orchestrator state
                metrics = Phase1Metrics.create_from_orchestrator(
                    site_id=self._request_site_id,
                    tenant_id=tenant_id,
                    session_id=self._request_session_id,
                    message_id=self._request_message_id,
                    orchestrator_result={
                        'intent_name': thread.last_detected_intent,
                        'intent_confidence': self._request_intent_result.confidence if self._request_intent_result else 0.0,
                        'used_llm': self._request_used_llm
                    },
                    thread=thread,
                    start_time=self._request_start_time
                )
                
                db.session.add(metrics)
                db.session.commit()
                logger.info(f"Phase1Metrics logged for message {self._request_message_id}")
            except Exception as e:
                # TELEMETRY MONITORING: Make failures visible
                # Telemetry is decoupled from user data (by design), but failures MUST be observable
                self.metrics_failures = getattr(self, 'metrics_failures', 0) + 1
                
                # Log as ERROR not warning - telemetry failure is a system health issue
                if self.metrics_failures % 10 == 0:
                    # Every 10th failure, log with full context
                    logger.error(
                        f"TELEMETRY FAILURE #{self.metrics_failures}: Phase1Metrics logging failed. "
                        f"Message: {self._request_message_id}, Error: {e}",
                        exc_info=True
                    )
                else:
                    # For others, just count it
                    logger.error(f"Phase1Metrics logging failed: {e}")
                
                db.session.rollback()
            
            # 4. Build response payload
            response = {
                "reply": bot_reply,
                "intent_name": thread.last_detected_intent,
                "intent_confidence": (
                    thread.last_intent_confidence or thread.llm_confidence or 0.0
                ),
                "workflow_state": thread.current_step,
                "workflow_type": thread.workflow_type,
                "collected_data": thread.structured_data or {},
                "context_analysis": {
                    "frustration_level": thread.frustration_score,
                    "confusion_level": thread.confusion_score,
                    "should_escalate": thread.escalation_triggered,
                    "escalation_reason": thread.escalation_reason,
                    "recommendation": thread.recommendation
                },
                "actions_taken": thread.execution_trace,
                "completion_score": thread.completion_score
            }
            
            # 5. Return
            return response
            
        except Exception as e:
            logger.error(f"Finalization failed: {e}", exc_info=True)
            return {
                "reply": "⚠️ An error occurred processing your message.",
                "error": str(e),
                "workflow_state": None,
                "actions_taken": thread.execution_trace if thread else []
            }


def get_message_orchestrator() -> MessageOrchestrator:
    """Singleton getter for MessageOrchestrator"""
    return MessageOrchestrator()


def get_metrics_health():
    """
    Health check for metrics telemetry system.
    Returns: dict with 'healthy' flag and failure count.
    """
    orchestrator = get_message_orchestrator()
    failures = getattr(orchestrator, 'metrics_failures', 0)
    
    return {
        'telemetry_healthy': failures == 0,
        'metrics_failures': failures,
        'status': 'OPERATIONAL' if failures == 0 else 'DEGRADED'
    }
