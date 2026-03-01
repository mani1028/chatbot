class ChatResponse:
    """Standardized chat response object"""
    def __init__(self, intent_name, intent_type, reply, confidence,
                 handoff=False, lead_capture=False, form_active=False,
                 form_data=None):
        self.intent_name = intent_name
        self.intent_type = intent_type
        self.reply = reply
        self.confidence = confidence
        self.handoff = handoff
        self.lead_capture = lead_capture
        # Multi-step form state
        self.form_active = form_active
        self.form_data = form_data or {}

    def to_dict(self):
        result = {
            'reply': self.reply,
            'intent': self.intent_name,
            'intent_type': self.intent_type,
            'confidence': self.confidence,
            'handoff': self.handoff,
            'lead_capture': self.lead_capture,
        }
        # Include form data if a form is active
        if self.form_active or self.form_data:
            result['form_active'] = self.form_active
            result.update(self.form_data)
        return result