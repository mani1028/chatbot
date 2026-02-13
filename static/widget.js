/**
 * ChatbotX Enterprise Widget
 * Handles UI, WebSockets, Dark Mode, and Typing Indicators
 */
(function() {
    // 1. ENVIRONMENT SETUP
    const SCRIPT = document.currentScript;
    const SITE_ID = SCRIPT ? (SCRIPT.getAttribute('data-site-id') || 1) : 1;
    // Auto-detect backend URL
    const API_BASE = SCRIPT ? new URL(SCRIPT.src).origin : "http://localhost:5000";
    
    let socket = null;
    let sessionId = localStorage.getItem('chat_session_id') || 'sess_' + Math.random().toString(36).substr(2, 9);
    localStorage.setItem('chat_session_id', sessionId);
    
    let config = {
        primary_color: '#6366f1',
        bot_name: 'ChatBot',
        theme_mode: 'light',
        initial_message: 'Hello! How can I help?'
    };

    // 2. LOAD RESOURCES
    function loadResources() {
        // Load CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `${API_BASE}/static/style.css`;
        document.head.appendChild(link);

        // Load Socket.IO
        const script = document.createElement('script');
        script.src = "https://cdn.socket.io/4.7.4/socket.io.min.js"; 
        script.onload = init;
        document.head.appendChild(script);
    }

    // 3. INITIALIZATION
    async function init() {
        // Fetch Settings
        try {
            const res = await fetch(`${API_BASE}/api/widget-settings?site_id=${SITE_ID}`);
            const data = await res.json();
            config = { ...config, ...data };
            
            buildUI();
            connectSocket();
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
        document.getElementById('chat-launcher').onclick = toggleChat;
        wrapper.querySelector('.widget-close').onclick = toggleChat;
        wrapper.querySelector('.widget-send').onclick = sendMessage;
        document.getElementById('chat-input').onkeypress = (e) => {
            if(e.key === 'Enter') sendMessage();
        };
    }

    // 5. WEBSOCKET LOGIC
    function connectSocket() {
        socket = io(API_BASE, { transports: ['websocket', 'polling'] });

        socket.on('connect', () => {
            console.log("ChatbotX: Connected");
            socket.emit('join', { site_id: SITE_ID });
        });

        // Listen for typing indicator
        socket.on('typing', () => {
            showTyping();
        });

        // Listen for responses
        socket.on('bot_response', (data) => {
            hideTyping();
            appendMessage(data.reply, 'bot');
        });
    }

    // 6. ACTIONS
    function toggleChat() {
        const widget = document.getElementById('chat-widget');
        const launcher = document.getElementById('chat-launcher');
        
        widget.classList.toggle('open');
        launcher.classList.toggle('hidden');
        
        if(widget.classList.contains('open')) {
            document.getElementById('chat-input').focus();
        }
    }

    function sendMessage() {
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if(!text) return;

        appendMessage(text, 'user');
        input.value = '';

        // Emit to server (app.py handles this via socketio)
        if(socket) {
            socket.emit('client_message', {
                site_id: SITE_ID,
                message: text,
                session_id: sessionId
            });
        }
    }

    function appendMessage(text, sender) {
        const body = document.getElementById('chat-body');
        const div = document.createElement('div');
        div.className = `msg ${sender}`;
        div.innerText = text; // Safe text insertion
        body.appendChild(div);
        body.scrollTop = body.scrollHeight;
    }

    function showTyping() {
        const body = document.getElementById('chat-body');
        if(document.querySelector('.typing-indicator')) return;

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