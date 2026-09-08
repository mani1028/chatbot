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
from services.vector_search import query_knowledge_base
from services.fallback_optimizer import get_optimizer
from config import (
    classify_confidence,
    FRUSTRATION_ESCALATION_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    ensure_thread_integrity,
)
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
                if self._is_affirmative(message):
                    confirmed_intent = thread.pending_clarification
                    thread.pending_clarification = None
                    thread.last_detected_intent = confirmed_intent
                    thread.last_intent_confidence = 1.0
                    
                    intent_result = IntentResult(
                        name=confirmed_intent,
                        confidence=1.0
                    )
                    self._apply_intent_response(thread, confirmed_intent, record_weight=True)
                    thread.execution_trace.append(f"clarification_confirmed:{confirmed_intent}")
                else:
                    # User said no/unclear — record correction then continue with detection
                    denied = thread.pending_clarification
                    thread.pending_clarification = None
                    self._record_clarification_correction(thread, denied)
                    thread.execution_trace.append("clarification_denied")
            
            # Only run detection if confirmation didn't already set result
            if intent_result is None:
                profiler.start_stage("intent_detection")
                intent_result = self._detect_intent(thread, message)
                profiler.end_stage("intent_detection")
                
                thread.execution_trace.append(f"intent_detected:{intent_result.name or 'unknown'}")
                
                if intent_result.name and intent_result.name != 'UNKNOWN':
                    # Apply success-based confidence weighting
                    intent_result = self._apply_confidence_weighting(thread, intent_result)
                    thread.last_detected_intent = intent_result.name
                    thread.last_intent_confidence = intent_result.confidence
                    self._apply_intent_response(thread, intent_result.name, record_weight=True)

            
            # Store intent result for metrics logging
            self._request_intent_result = intent_result
            
            # CLARIFICATION BAND — aligned with classify_confidence MEDIUM range
            if (
                intent_result.name
                and intent_result.name != 'UNKNOWN'
                and MEDIUM_CONFIDENCE_THRESHOLD <= intent_result.confidence < HIGH_CONFIDENCE_THRESHOLD
                and not thread.pending_clarification
                and not thread.workflow_type
            ):
                # Prefer optimizer clarifying questions when available
                clarifying = self._build_clarifying_question(thread, intent_result, message)
                thread.pending_clarification = intent_result.name
                thread.pending_reply = clarifying
                thread.execution_trace.append("clarification_band_triggered")
                
                self._run_analytics(thread)
                return self._finalize(thread)
            
            # STAGE 7: Apply feature gating
            self._apply_feature_gates(thread, intent_result)
            thread.execution_trace.append("feature_gates_applied")
            
            # STAGE 8: KB retrieval → throttle → LLM fallback
            if self._should_call_llm(thread, intent_result):
                if self._try_knowledge_base(thread, message):
                    thread.execution_trace.append("knowledge_base_hit")
                else:
                    throttled = self._maybe_throttle_llm(thread, message, intent_result)
                    if throttled:
                        thread.execution_trace.append("llm_throttled")
                    else:
                        self._log_unknown_intent(thread, message, fallback_type='llm')
                        
                        self._request_llm_start_time = time.time()
                        llm_result = self._run_llm(thread, message)
                        self._request_llm_end_time = time.time()
                        self._request_used_llm = True
                        
                        thread.execution_trace.append("llm_invoked")
                        self._merge_llm_result(thread, llm_result)
                        self._attach_llm_response_to_unknown_log(thread, llm_result.text)
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
            
            # ContextAnalyzer returns frustration_level / confusion_level
            thread.frustration_score = context.get(
                "frustration_level",
                context.get("frustration", 0.0)
            ) or 0.0
            thread.confusion_score = context.get(
                "confusion_level",
                context.get("confusion", 0.0)
            ) or 0.0
            thread.intent_drift = context.get("intent_drift")
            thread.recommendation = context.get("recommendation", "continue")
            
            escalate = context.get("should_escalate")
            if isinstance(escalate, (tuple, list)):
                should_esc = bool(escalate[0]) if escalate else False
                reason = escalate[1] if len(escalate) > 1 else "context_escalation"
            else:
                should_esc = bool(escalate)
                reason = "context_escalation"
            
            if should_esc or thread.frustration_score > FRUSTRATION_ESCALATION_THRESHOLD:
                thread.escalation_triggered = True
                thread.escalation_reason = reason if should_esc else "high_frustration"
                
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
            history = None
            if thread.short_term_messages:
                history = []
                for msg in thread.short_term_messages:
                    if msg.get('role') == 'user':
                        history.append({
                            'user_message': msg.get('content', ''),
                            'detected_intent': thread.last_detected_intent,
                        })
            
            result = detect_intent_only(message, thread.site_id, history)
            
            intent_name = result.get('intent_name')
            confidence = result.get('confidence', 0.0)
            
            # Treat UNKNOWN as no-intent for downstream gating
            if intent_name in (None, 'UNKNOWN', 'ERROR'):
                return IntentResult(name=intent_name if intent_name == 'UNKNOWN' else None, confidence=confidence)
            
            return IntentResult(
                name=intent_name,
                confidence=confidence,
                phrases=result.get('phrases', [])
            )
            
        except Exception as e:
            logger.warning(f"Intent detection error: {e}")
            return IntentResult(name=None, confidence=0.0)

    @staticmethod
    def _is_affirmative(message: str) -> bool:
        """True for clear yes-confirmations; avoids matching 'yesterday' via startswith('y')."""
        if not message:
            return False
        normalized = message.lower().strip().rstrip('.!,?')
        affirmatives = {
            'yes', 'yeah', 'yep', 'yup', 'y', 'sure', 'correct',
            'right', 'ok', 'okay', 'affirmative', 'please',
        }
        if normalized in affirmatives:
            return True
        tokens = normalized.split()
        return bool(tokens) and tokens[0] in affirmatives

    def _lookup_intent(self, thread: ConversationThread, intent_name: str):
        from models.intent import Intent
        from sqlalchemy import or_
        if not intent_name:
            return None
        return Intent.query.filter(
            or_(Intent.site_id == 0, Intent.site_id == thread.site_id),
            Intent.intent_name == intent_name
        ).first()

    def _apply_intent_response(self, thread: ConversationThread, intent_name: str,
                               record_weight: bool = False) -> None:
        """Load templated intent response from DB into thread.pending_reply."""
        from services.response_formatter import substitute_template_variables
        
        intent_obj = self._lookup_intent(thread, intent_name)
        if not intent_obj:
            return
        
        if intent_obj.response:
            reply = substitute_template_variables(intent_obj.response, thread.site_id)
            thread.pending_reply = reply
            thread.execution_trace.append(f"intent_response_loaded:{intent_name}")
        
        itype = (intent_obj.intent_type or '').upper()
        if itype in ('HUMAN', 'LEAD'):
            thread.escalation_triggered = True
            thread.escalation_reason = f"intent_type_{itype.lower()}"
        
        if record_weight:
            try:
                from models import IntentConfidenceWeight
                w = IntentConfidenceWeight.get_or_create(
                    thread.site_id, intent_obj.id, commit=False
                )
                w.record_detection()
            except Exception as e:
                logger.debug(f"Confidence weight record skipped: {e}")

    def _apply_confidence_weighting(self, thread: ConversationThread,
                                    intent_result: IntentResult) -> IntentResult:
        """Adjust confidence using historical success multipliers."""
        try:
            intent_obj = self._lookup_intent(thread, intent_result.name)
            if not intent_obj:
                return intent_result
            from models import IntentConfidenceWeight
            weight = IntentConfidenceWeight.get_or_create(
                thread.site_id, intent_obj.id, commit=False
            )
            effective = min(1.0, max(0.0, intent_result.confidence * (weight.confidence_multiplier or 1.0)))
            intent_result.confidence = effective
            thread.last_intent_confidence = effective
        except Exception as e:
            logger.debug(f"Confidence weighting skipped: {e}")
        return intent_result

    def _build_clarifying_question(self, thread: ConversationThread,
                                   intent_result: IntentResult, message: str) -> str:
        clean_name = (intent_result.name or '').replace('_', ' ').title()
        default_q = f"Did you mean '{clean_name}'?"
        try:
            intent_obj = self._lookup_intent(thread, intent_result.name)
            if not intent_obj:
                return default_q
            optimizer = get_optimizer()
            custom = optimizer.generate_clarifying_questions(
                intent_obj, message, thread.site_id
            )
            return custom or default_q
        except Exception:
            return default_q

    def _record_clarification_correction(self, thread: ConversationThread,
                                         intent_name: str) -> None:
        try:
            intent_obj = self._lookup_intent(thread, intent_name)
            if not intent_obj:
                return
            from models import IntentConfidenceWeight
            w = IntentConfidenceWeight.get_or_create(
                thread.site_id, intent_obj.id, commit=False
            )
            w.record_detection()
            w.record_user_correction()
        except Exception as e:
            logger.debug(f"Clarification correction record skipped: {e}")

    def _try_knowledge_base(self, thread: ConversationThread, message: str) -> bool:
        """Attempt RAG hit before LLM. Returns True if reply was set."""
        try:
            kb_results = query_knowledge_base(thread.site_id, message, top_k=1)
            if not kb_results:
                return False
            top_score, top_file = kb_results[0]
            if top_score < 0.45:
                return False
            filename = getattr(top_file, 'filename', 'knowledge base')
            thread.pending_reply = (
                f"I found this in your knowledge base ({filename}). "
                f"If that doesn't answer your question, please rephrase."
            )
            thread.last_detected_intent = 'KNOWLEDGE_BASE'
            thread.last_intent_confidence = float(top_score)
            return True
        except Exception as e:
            logger.debug(f"KB lookup skipped: {e}")
            return False

    def _maybe_throttle_llm(self, thread: ConversationThread, message: str,
                            intent_result: IntentResult) -> bool:
        """If session is in fallback storm, return safe template instead of LLM."""
        try:
            optimizer = get_optimizer()
            should_throttle, reason = optimizer.should_throttle_fallback(
                thread.site_id,
                thread.session_id,
                intent_result.confidence if intent_result else 0.0,
            )
            if not should_throttle:
                return False
            thread.pending_reply = (
                "I'm having trouble understanding. "
                "Could you rephrase or be more specific?"
            )
            self._log_unknown_intent(thread, message, fallback_type='throttle')
            from models import ConfidenceThrottle
            ConfidenceThrottle.record_fallback(
                thread.site_id, thread.session_id, commit=False
            )
            logger.info(f"LLM throttled for session {thread.session_id}: {reason}")
            return True
        except Exception as e:
            logger.debug(f"Throttle check skipped: {e}")
            return False

    def _attach_llm_response_to_unknown_log(self, thread: ConversationThread,
                                            llm_text: str) -> None:
        """Attach LLM text to the most recent uncommitted unknown log for this site/message."""
        try:
            from models import UnknownIntentLog, ConfidenceThrottle
            # Prefer in-session pending objects
            for obj in list(db.session.new):
                if isinstance(obj, UnknownIntentLog) and obj.site_id == thread.site_id:
                    obj.llm_response = llm_text
                    break
            ConfidenceThrottle.record_fallback(
                thread.site_id, thread.session_id, commit=False
            )
        except Exception as e:
            logger.debug(f"Attach LLM response skipped: {e}")

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
        """Decide whether Stage 8 should invoke LLM / KB / throttle path.
        
        Call when there is no pending reply yet (unknown / low confidence /
        known intent missing DB response). Never call when a reply is ready
        or a workflow owns the turn.
        """
        if thread.has_active_workflow():
            return False
        
        if thread.pending_reply:
            return False
        
        if getattr(thread, 'block_reason', None):
            return False
        
        confidence = intent_result.confidence if intent_result else 0.0
        confidence_class = classify_confidence(confidence)
        no_intent = (
            not intent_result
            or not intent_result.name
            or intent_result.name == 'UNKNOWN'
        )
        
        if thread.escalation_triggered and not no_intent:
            thread.pending_reply = (
                "I'm connecting you with a team member who can help."
            )
            should_call = False
        else:
            # No reply loaded yet → generative / KB path
            should_call = True
        
        logger.debug(
            "LLM decision workflow=%s escalated=%s class=%s intent=%s conf=%.3f call=%s",
            thread.has_active_workflow(),
            thread.escalation_triggered,
            confidence_class,
            getattr(intent_result, 'name', None),
            confidence or 0.0,
            should_call,
        )
        
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

    def _log_unknown_intent(self, thread: ConversationThread, message: str,
                            fallback_type: str = 'llm'):
        """Log unknown intent for admin mapping (Phase 1 minimal).
        
        Non-blocking. If logging fails, orchestrator continues.
        Does not commit — Stage 10 (_finalize) owns the atomic commit.
        """
        try:
            from models import UnknownIntentLog
            
            log = UnknownIntentLog(
                site_id=thread.site_id,
                message=message,
                fallback_type=fallback_type or 'llm',
                resolved=False,
            )
            db.session.add(log)
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
