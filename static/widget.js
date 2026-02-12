
/**
 * Chatbot Widget Embed Script
 * Auto-initializes based on data attributes
 */
(function() {
    // 1. Get configuration immediately from the script tag
    const currentScript = document.currentScript;
    // Default to 1 if not provided
    const siteId = currentScript ? (currentScript.getAttribute('data-site-id') || 1) : 1;
    const position = currentScript ? (currentScript.getAttribute('data-position') || 'bottom-right') : 'bottom-right';
    
    // API CONFIGURATION
    const API_URL = "http://localhost:5000"; 

    // 2. Main Initialization Function
    function initWidget() {
        // Prevent duplicate widgets
        if (document.getElementById('chatbot-widget-container')) return;

        // Inject CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `${API_URL}/static/style.css`;
        document.head.appendChild(link);

        // Create Widget HTML
        const container = document.createElement('div');
        container.id = 'chatbot-widget-container';
        container.className = `chatbot-widget-${position}`;
        container.innerHTML = `
            <div id="chatbot-bubble">💬</div>
            <div id="chatbot-window" style="display: none;">
                <div id="chatbot-header">
                    <span id="chatbot-title">Chat Support</span>
                    <button id="chatbot-close">✖</button>
                </div>
                <div id="chatbot-messages"></div>
                <div id="chatbot-input-area">
                    <input type="text" id="chatbot-input" placeholder="Type a message...">
                    <button id="chatbot-send">➤</button>
                </div>
            </div>
        `;
        
        // Append to body safely
        if (document.body) {
            document.body.appendChild(container);
        } else {
            document.addEventListener('DOMContentLoaded', () => document.body.appendChild(container));
        }

        // Attach Logic
        attachEventListeners(siteId, API_URL);
        
        // Optional: Load Branding
        fetch(`${API_URL}/api/widget-settings?site_id=${siteId}`)
            .then(r => r.json())
            .then(settings => {
                if(settings && settings.bot_name) {
                    document.getElementById('chatbot-title').innerText = settings.bot_name;
                }
            })
            .catch(e => console.log("Branding load error (using defaults)", e));
    }

    // 3. Event Listeners
    function attachEventListeners(siteId, apiUrl) {
        const bubble = document.getElementById('chatbot-bubble');
        const windowEl = document.getElementById('chatbot-window');
        const closeBtn = document.getElementById('chatbot-close');
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');
        const messages = document.getElementById('chatbot-messages');

        // Toggle Visibility
        bubble.onclick = () => { windowEl.style.display = 'flex'; bubble.style.display = 'none'; };
        closeBtn.onclick = () => { windowEl.style.display = 'none'; bubble.style.display = 'flex'; };

        function appendMessage(text, isUser) {
            const div = document.createElement('div');
            div.className = isUser ? 'user-message' : 'bot-message';
            div.innerHTML = `<div class="message-content">${text}</div>`;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            appendMessage(text, true);
            input.value = '';

            try {
                const res = await fetch(`${apiUrl}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        site_id: siteId,
                        message: text
                    })
                });

                if (!res.ok) {
                    const errData = await res.json();
                    throw new Error(errData.error || `Server Error ${res.status}`);
                }

                const data = await res.json();
                appendMessage(data.reply, false);

            } catch (err) {
                console.error("Chat Error:", err);
                appendMessage("⚠️ Error: " + err.message, false);
            }
        }

        sendBtn.onclick = sendMessage;
        input.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
    }

    // 4. Initialize
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        initWidget();
    } else {
        document.addEventListener('DOMContentLoaded', initWidget);
    }

})();
