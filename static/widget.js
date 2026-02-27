/**
 * ChatbotX Enterprise Widget
 * Handles UI, WebSockets, Dark Mode, and Typing Indicators
 */

(function() {
// 1. ENVIRONMENT SETUP
    const configObj = window.ChatbotXConfig || {};
    
    // Fallback for legacy scripts
    const SCRIPT = document.currentScript || document.getElementById('chatbotx-script') || document.querySelector('script[src*="widget.js"]');
                   
    // Use public siteKey for secure authentication
    const SITE_KEY = configObj.siteKey;
    const API_BASE = configObj.apiUrl || (SCRIPT ? new URL(SCRIPT.src).origin : "https://api.chatbotx.com");

    if (!SITE_KEY) {
        console.error("ChatbotX: Missing siteKey in configuration.");
        return;
    }
    
    let socket = null;
    let sessionId = localStorage.getItem('chat_session_id') || 'sess_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('chat_session_id', sessionId);
    
    let config = {
        primary_color: '#6366f1',
        bot_name: 'AlinaX Chatbot',
        theme_mode: 'light',
        initial_message: 'Hello! I am AlinaX How can I help?'
    };
    // 2. LOAD RESOURCES
    function loadResources() {
        // Load CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `${API_BASE}/static/style.css`;
        document.head.appendChild(link);

        // Load Socket.IO
            // No need to load socket.io anymore
            init();
    }

    // 3. INITIALIZATION
    async function init() {
        // Fetch Settings
        try {
            const res = await fetch(`${API_BASE}/api/widget-settings?site_key=${SITE_KEY}`);
            const data = await res.json();
            config = { ...config, ...data };
            
            buildUI();
                // connectSocket removed; no longer needed
        } catch (e) {
            console.error("ChatbotX: Failed to init", e);
        }
    }

    // 4. UI CONSTRUCTION
    function buildUI() {
        if (document.getElementById('chat-widget-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.id = 'chat-widget-wrapper';
        
        // CSS Variables for branding
        wrapper.style.setProperty('--primary', config.primary_color);

        wrapper.innerHTML = `
            <!-- Launcher -->
            <div id="chat-launcher" style="background-color: ${config.primary_color}">
                <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>
            </div>

            <!-- Widget Window -->
            <div id="chat-widget" class="${config.theme_mode === 'dark' ? 'dark-mode' : ''}">
                <div class="widget-header" style="background-color: ${config.primary_color}">
                    <span>${config.bot_name}</span>
                    <button class="widget-close">×</button>
                </div>
                <div class="widget-body" id="chat-body">
                    <!-- Initial Message -->
                    <div class="msg bot">${config.initial_message}</div>
                </div>
                <div class="widget-footer">
                    <input type="text" class="widget-input" id="chat-input" placeholder="Type a message...">
                    <button class="widget-send" style="background-color: ${config.primary_color}">➤</button>
                </div>
            </div>
        `;
        document.body.appendChild(wrapper);

        // Event Listeners
        const chatLauncher = document.getElementById('chat-launcher');
        if (chatLauncher) chatLauncher.onclick = toggleChat;
        const widgetClose = wrapper.querySelector('.widget-close');
        if (widgetClose) widgetClose.onclick = toggleChat;
        const widgetSend = wrapper.querySelector('.widget-send');
        if (widgetSend) widgetSend.onclick = sendMessage;
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.onkeypress = (e) => {
                if(e.key === 'Enter') sendMessage();
            };
        }
    }

    // 5. WEBSOCKET LOGIC





    // 6. ACTIONS
    function toggleChat() {
        const widget = document.getElementById('chat-widget');
        const launcher = document.getElementById('chat-launcher');
        if (widget && launcher) {
            widget.classList.toggle('open');
            launcher.classList.toggle('hidden');
            if(widget.classList.contains('open')) {
                const chatInput = document.getElementById('chat-input');
                if (chatInput) chatInput.focus();
            }
        }
    }

    async function sendMessage() {
        const input = document.getElementById('chat-input');
        if (!input) return;
        const text = input.value.trim();
        if(!text) return;

        appendMessage(text, 'user');
        input.value = '';

        // Use REST API to send message
        try {
            const res = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_id: SITE_ID,
                    message: text,
                    session_id: sessionId
                })
            });

            const data = await res.json();
            if (data.error) {
                appendMessage("⚠️ Error: " + data.error, 'bot');
            } else {
                appendMessage(data.reply, 'bot');
            }
        } catch (e) {
            console.error("ChatbotX Error:", e);
            appendMessage("⚠️ Connection error. Please try again.", 'bot');
        }
    }

    function appendMessage(text, sender) {
        const body = document.getElementById('chat-body');
        if (!body) return;
        const div = document.createElement('div');
        div.className = `msg ${sender}`;
        div.innerText = text; // Safe text insertion
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
    }

    function showTyping() {
        const body = document.getElementById('chat-body');
        if (!body || document.querySelector('.typing-indicator')) return;

        const div = document.createElement('div');
        div.className = 'typing-indicator';
        div.innerHTML = `<div class="dot"></div><div class="dot"></div><div class="dot"></div>`;
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
    }

    function hideTyping() {
        const el = document.querySelector('.typing-indicator');
        if(el) el.remove();
    }

    // Start
    loadResources();

})();