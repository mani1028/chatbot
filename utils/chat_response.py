class ChatResponse:
    """Standardized chat response object"""
    def __init__(self, intent_name, intent_type, reply, confidence, handoff=False, lead_capture=False):
        self.intent_name = intent_name
        self.intent_type = intent_type
        self.reply = reply
        self.confidence = confidence
        self.handoff = handoff
        self.lead_capture = lead_capture

    def to_dict(self):
        return {
            'reply': self.reply,
            'intent': self.intent_name,
            'intent_type': self.intent_type,
            'confidence': self.confidence,
            'handoff': self.handoff,
            'lead_capture': self.lead_capture
        }