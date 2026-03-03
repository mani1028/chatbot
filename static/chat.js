/**
 * Chat UI JavaScript
 * Handles real-time chat interactions for the main demo page
 * Phase 2: Added plan-based features and context analysis support
 */

document.addEventListener('DOMContentLoaded', function () {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    // DEFAULT SITE ID for the main demo page
    const DEFAULT_SITE_ID = 1; 
    const DEFAULT_SITE_KEY = 'pk_live_086ea639519a4733'; 

    // Phase 2: Site features/plan
    let siteFeatures = {
        plan: 'free',
        context_engine_enabled: false,
        escalation_enabled: false
    };

    // Load site features on init
    async function initFeatures() {
        try {
            const res = await fetch(`/api/site-features?site_key=${DEFAULT_SITE_KEY}`);
            const data = await res.json();
            siteFeatures = {
                plan: data.plan || 'free',
                context_engine_enabled: data.plan === 'pro' || data.plan === 'enterprise',
                escalation_enabled: data.plan === 'pro' || data.plan === 'enterprise'
            };
            console.log(`Site Plan: ${siteFeatures.plan}, Context Engine: ${siteFeatures.context_engine_enabled}`);
        } catch (e) {
            console.warn('Failed to load site features, using defaults:', e);
        }
    }

    function appendMessage(text, isUser, metadata = null) {
        if (!chatBox) return;
        const div = document.createElement('div');
        div.className = isUser ? 'user-message' : 'bot-message';
        div.textContent = text;
        chatBox.appendChild(div);
        
        // Phase 2: Show context indicators if available
        if (metadata && metadata.context_analysis && siteFeatures.context_engine_enabled) {
            const contextDiv = document.createElement('div');
            contextDiv.className = 'context-indicator-inline';
            
            if (metadata.context_analysis.frustration_level > 0.6) {
                contextDiv.innerHTML = `⚠️ Frustration detected (${Math.round(metadata.context_analysis.frustration_level * 100)}%)`;
                contextDiv.style.color = '#EF4444';
            } else if (metadata.context_analysis.confusion_level > 0.5) {
                contextDiv.innerHTML = `ℹ️ User may need clarification (${Math.round(metadata.context_analysis.confusion_level * 100)}%)`;
                contextDiv.style.color = '#F59E0B';
            }
            
            if (contextDiv.innerHTML) {
                contextDiv.style.fontSize = '12px';
                contextDiv.style.fontStyle = 'italic';
                contextDiv.style.padding = '4px 8px';
                chatBox.appendChild(contextDiv);
            }
        }
        
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function sendMessage() {
        if (!userInput) return;
        
        const text = userInput.value.trim();
        if (!text) return;

        appendMessage(text, true);
        userInput.value = '';

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: text,
                    site_key: DEFAULT_SITE_KEY
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Server Error');
            }

            const data = await response.json();
            
            // Phase 2: Handle escalation auto-offer
            if (siteFeatures.context_engine_enabled && data.context_analysis && data.context_analysis.should_escalate) {
                appendMessage('I sense you may need additional support. Would you like to speak with a human agent?', false);
                if (siteFeatures.escalation_enabled) {
                    const offerDiv = document.createElement('div');
                    offerDiv.style.marginTop = '8px';
                    offerDiv.innerHTML = `
                        <button onclick="escalate();" style="padding: 6px 12px; background-color: #3B82F6; color: white; border: none; border-radius: 4px; cursor: pointer;">
                            Connect to Agent
                        </button>
                    `;
                    chatBox.appendChild(offerDiv);
                }
            } else {
                appendMessage(data.reply, false, data);
            }

        } catch (error) {
            console.error('Error:', error);
            appendMessage("⚠️ Error: " + error.message, false);
        }
    }

    // Phase 2: Escalate to human
    window.escalate = async function() {
        appendMessage('Connecting you to a human agent...', false);
        try {
            const res = await fetch('/api/escalate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_key: DEFAULT_SITE_KEY
                })
            });
            if (res.ok) {
                appendMessage('Human agent assigned. Please wait...', false);
            }
        } catch(e) {
            appendMessage('Failed to escalate. Please try again.', false);
        }
    };

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (userInput) userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Initialize features on page load
    initFeatures();
});