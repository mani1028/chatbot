/**
 * ChatbotX Enterprise Widget
 * Handles UI, WebSockets, Dark Mode, and Typing Indicators
 */

(function() {
// 1. ENVIRONMENT SETUP
    const configObj = window.ChatbotXConfig || {};
    // Fallback for legacy scripts
    const SCRIPT = document.currentScript || document.querySelector('script[data-site-key]');
    const SITE_KEY = SCRIPT ? SCRIPT.getAttribute("data-site-key") : null;
    const API_BASE = SCRIPT ? new URL(SCRIPT.src).origin : window.location.origin;
    if (!SITE_KEY) {
            console.error("ChatbotX: Missing data-site-key in script tag.");
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

        // FIX: Load Socket.IO client from CDN instead of Flask server
        const script = document.createElement('script');
        script.src = "https://cdn.socket.io/4.7.2/socket.io.min.js";
        script.onload = () => {
            init();
            connectSocket();
        };
        document.head.appendChild(script);
    }

    // 3. INITIALIZATION
    async function init() {
        // Fetch Settings
        try {
            const res = await fetch(`${API_BASE}/api/widget-settings?site_key=${SITE_KEY}`);
            const data = await res.json();
            config = { ...config, ...data };
            buildUI();
        } catch (e) {
            console.error("ChatbotX: Failed to init", e);
        }
    }

    // 5. SOCKETIO CLIENT
    function connectSocket() {
        if (typeof io === 'undefined') return;
        // Explicitly set path and transports to avoid 400 error
        const socket = io(API_BASE, {
            path: '/socket.io',
            transports: ['websocket', 'polling']
        });
        socket.on('agent_handoff', function(data) {
            // Show notification or update UI for agent handoff
            appendMessage('A human agent has joined the chat.', 'bot');
        });
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
        let retryCount = 0;
        let success = false;
        let lastError = null;
        while (retryCount < 2 && !success) {
            try {
                const res = await fetch(`${API_BASE}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        site_key: SITE_KEY,
                        message: text,
                        session_id: sessionId,
                        page_url: window.location.href
                    })
                });
                const data = await res.json();
                if (data.error) {
                    appendErrorWithRetry("⚠️ Error: " + data.error, text);
                    lastError = data.error;
                } else if (data.intent_type && data.intent_type.toUpperCase() === 'LEAD') {
                    renderLeadForm();
                    success = true;
                } else {
                    appendMessage(data.reply, 'bot');
                    success = true;
                }
            } catch (e) {
                lastError = e;
                if (retryCount === 0) {
                    appendErrorWithRetry("⚠️ Connection error. Please try again.", text);
                }
            }
            retryCount++;
        }
        if (!success && lastError) {
            appendErrorWithRetry("❌ Failed to send message after retry.", text);
        }
        function appendErrorWithRetry(errorText, originalText) {
            const body = document.getElementById('chat-body');
            if (!body) return;
            const div = document.createElement('div');
            div.className = 'msg bot error-state';
            div.innerHTML = `${errorText} <button class="retry-btn">Retry</button>`;
            body.appendChild(div);
            body.scrollTop = body.scrollHeight;
            const btn = div.querySelector('.retry-btn');
            if (btn) {
                btn.onclick = () => {
                    div.remove();
                    document.getElementById('chat-input').value = originalText;
                    sendMessage();
                };
            }
        }
    }

    // Behavioral trigger: auto-greet on high-value pages
    function autoGreetIfNeeded() {
        const highValuePages = [/pricing/i, /checkout/i, /contact/i];
        const url = window.location.href;
        if (highValuePages.some(rx => rx.test(url))) {
            setTimeout(() => {
                if (!document.querySelector('.msg.bot.auto-greeted')) {
                    appendMessage(config.initial_message, 'bot');
                    document.querySelector('.msg.bot:last-child').classList.add('auto-greeted');
                }
            }, 2000);
        }
    }

    function renderLeadForm() {
        const body = document.getElementById('chat-body');
        if (!body) return;
        const formDiv = document.createElement('div');
        formDiv.className = 'msg bot lead-form';
        formDiv.innerHTML = `
            <form id="lead-capture-form">
                <label>Name:<input type="text" name="name" required></label><br>
                <label>Email:<input type="email" name="email" required></label><br>
                <label>Phone:<input type="tel" name="phone"></label><br>
                <button type="submit">Submit</button>
            </form>
        `;
        body.appendChild(formDiv);
        body.scrollTop = body.scrollHeight;
        const form = formDiv.querySelector('#lead-capture-form');
        form.onsubmit = async function(e) {
            e.preventDefault();
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.innerText = "Sending...";
            submitBtn.disabled = true;
            const formData = new FormData(form);
            const payload = {
                name: formData.get('name'),
                email: formData.get('email'),
                phone: formData.get('phone'),
                session_id: sessionId,
                site_key: SITE_KEY,
            };
            try {
                await fetch(`${API_BASE}/api/chat/lead-capture`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                appendMessage("Thank you! Our team will reach out soon.", 'bot');
                formDiv.remove();
            } catch (err) {
                submitBtn.innerText = "Submit";
                submitBtn.disabled = false;
                appendMessage("⚠️ Could not send your details. Please try again.", 'bot error-state');
            }
        };
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
    // Show greeting after UI is ready
    setTimeout(() => {
        appendMessage(config.initial_message, 'bot');
    }, 500);

})();