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

        // Load Socket.IO client from CDN
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
            await loadChatHistory(); // Load chat history after UI is built
        } catch (e) {
            console.error("ChatbotX: Failed to init", e);
        }
    }

    // Fetch and render chat history
    async function loadChatHistory() {
        try {
            const res = await fetch(`${API_BASE}/api/chat/history?session_id=${sessionId}`);
            if (!res.ok) {
                console.error('Failed to fetch chat history: HTTP error', res.status);
                appendMessage('⚠️ Unable to load chat history.', 'bot error-state');
                return;
            }

            const history = await res.json();
            if (!Array.isArray(history) || history.length === 0) {
                appendMessage('No previous messages found.', 'bot info-state');
                return;
            }

            history.forEach(msg => {
                appendMessage(msg.text, msg.sender === 'user' ? 'user' : 'bot');
            });
        } catch (e) {
            console.error('Failed to load chat history', e);
            appendMessage('⚠️ Error loading chat history. Please try again.', 'bot error-state');
        }
    }

    // 4. SOCKETIO CLIENT
    function connectSocket() {
        if (typeof io === 'undefined') {
            console.error("Socket.IO library is not loaded.");
            return;
        }

        socket = io(API_BASE, {
            path: '/socket.io',
            transports: ['websocket', 'polling']
        });

        socket.on('connect', () => {
            console.log("Socket connected successfully.");

            // Listeners for live agent handoff
            socket.on('agent_handoff', function(data) {
                appendMessage('A human agent has joined the chat.', 'bot');
            });

            // Safely isolated inside the connect block
            socket.on('agent_message', function(data) {
                appendMessage(data.message, 'bot agent-message');
            });
        });

        socket.on('connect_error', (error) => {
            console.error("Socket connection error:", error);
        });
    }

    // 5. UI CONSTRUCTION
    function buildUI() {
        if (document.getElementById('chat-widget-wrapper')) return;

        const wrapper = document.createElement('div');
        wrapper.id = 'chat-widget-wrapper';
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

    // 6. ACTIONS & LOGIC
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
        if (!text) return;

        appendMessage(text, 'user');
        input.value = '';
        showTyping(); 

        try {
            const res = await fetch(`${API_BASE}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_key: SITE_KEY,
                    session_id: sessionId,
                    message: text
                })
            });
            
            // Check for HTTP errors (like 429 Rate Limit or 500 Server Error)
            if (!res.ok) {
                let errorMsg = "Server Error";
                try {
                    const errData = await res.json();
                    errorMsg = errData.error || errorMsg;
                } catch(e) {}
                throw new Error(errorMsg);
            }
            
            const data = await res.json();
            hideTyping();

            // Intercept API JSON errors
            if (data.error) {
                appendMessage("⚠️ " + data.error, 'bot error-state');
                return;
            }

            let rendered = false;

            // FIX: Print the bot's conversational response looking for reply, text, or response keys
            const botMessageText = data.reply || data.text || data.response;
            if (botMessageText) {
                appendMessage(botMessageText, 'bot');
                rendered = true;
            }

            // Render rich UI components based on intent
            if (data.data && data.intent_name === 'track_order') {
                renderOrderStatusCard(data.data); 
                rendered = true;
            } 
            else if (data.intent_type === 'LEAD' || data.handoff === 'LEAD') {
                renderLeadForm(); 
                rendered = true;
            }
            else if (data.intent_name === 'book_appointment' || data.intent_name === 'booking') {
                renderBookingForm();
                rendered = true;
            }

            // Fallback safety if the bot returned absolutely nothing
            if (!rendered) {
                appendMessage("⚠️ Received empty response from server.", 'bot error-state');
            }

        } catch (e) {
            console.error('Failed to send message', e);
            hideTyping();
            appendMessage("⚠️ " + (e.message || "Connection error. Please try again."), 'bot error-state');
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

    // 7. UI RENDERERS
    function renderOrderStatusCard(data) {
        const chatBody = document.getElementById('chat-body');
        if (!chatBody) return;

        const card = document.createElement('div');
        card.className = 'order-status-card';
        card.innerHTML = `
            <div style="border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin-top: 10px; background: #fff; color: #333;">
                <h4 style="margin: 0 0 5px 0;">Order Status</h4>
                <p style="margin: 0; font-size: 13px;">Order ID: <strong>${data.order_id}</strong></p>
                <p style="margin: 5px 0; font-size: 13px;">Status: <strong>${data.status}</strong></p>
                <div style="background: #eee; border-radius: 4px; height: 8px; width: 100%; margin-top: 8px;">
                    <div style="background: ${config.primary_color}; border-radius: 4px; height: 100%; width: ${data.progress}%;"></div>
                </div>
            </div>
        `;
        chatBody.appendChild(card);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function renderBookingForm() {
        const chatBody = document.getElementById('chat-body');
        if (!chatBody) return;

        const form = document.createElement('form');
        form.className = 'booking-form msg bot';
        form.innerHTML = `
            <h4 style="margin: 0 0 10px 0;">Book an Appointment</h4>
            <label style="display:block; font-size:12px; margin-bottom: 4px;">Date:</label>
            <input type="date" id="date" required style="width:100%; margin-bottom: 10px; padding: 5px; border: 1px solid #ccc; border-radius: 4px;">
            <label style="display:block; font-size:12px; margin-bottom: 4px;">Time:</label>
            <input type="time" id="time" required style="width:100%; margin-bottom: 10px; padding: 5px; border: 1px solid #ccc; border-radius: 4px;">
            <button type="submit" style="background: ${config.primary_color}; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; width: 100%;">Confirm</button>
        `;
        form.onsubmit = async (e) => {
            e.preventDefault();
            const date = form.querySelector('#date').value;
            const time = form.querySelector('#time').value;
            appendMessage(`Booking confirmed for ${date} at ${time}`, 'bot');
            form.remove();
        };
        chatBody.appendChild(form);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function renderLeadForm() {
        const body = document.getElementById('chat-body');
        if (!body) return;
        const formDiv = document.createElement('div');
        formDiv.className = 'msg bot lead-form';
        formDiv.innerHTML = `
            <form id="lead-capture-form">
                <label style="font-size: 12px;">Name:<input type="text" name="name" required style="width:100%; margin: 4px 0 8px; padding: 5px; border:1px solid #ccc; border-radius:4px;"></label>
                <label style="font-size: 12px;">Email:<input type="email" name="email" required style="width:100%; margin: 4px 0 8px; padding: 5px; border:1px solid #ccc; border-radius:4px;"></label>
                <label style="font-size: 12px;">Phone:<input type="tel" name="phone" style="width:100%; margin: 4px 0 8px; padding: 5px; border:1px solid #ccc; border-radius:4px;"></label>
                <label style="font-size: 12px;">How can we help?
                    <textarea name="issue" rows="3" required style="width: 100%; margin: 4px 0 8px; border-radius: 4px; border: 1px solid #ccc; padding: 5px;"></textarea>
                </label>
                <button type="submit" style="background: ${config.primary_color}; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; width: 100%;">Submit</button>
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
                user_message: formData.get('issue'), 
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

    // 8. HELPERS
    function appendMessage(text, sender) {
        const body = document.getElementById('chat-body');
        if (!body) return;
        const div = document.createElement('div');
        div.className = `msg ${sender}`;
        div.innerText = text; 
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

    // 9. EXECUTE
    loadResources();
    
    // Show greeting after UI is ready
    setTimeout(() => {
        // Only show if history didn't already load a greeting
        if (document.getElementById('chat-body') && document.getElementById('chat-body').children.length === 0) {
            appendMessage(config.initial_message, 'bot');
        }
        autoGreetIfNeeded();
    }, 500);

    // Function to handle tab switching
    function switchTab(tabName, element) {
        // Remove active class from all nav items
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => item.classList.remove('active'));

        // Add active class to the clicked nav item
        element.classList.add('active');

        // Hide all tab content sections
        const tabContents = document.querySelectorAll('.tab-content');
        tabContents.forEach(content => content.style.display = 'none');

        // Show the selected tab content
        const activeTab = document.getElementById(tabName);
        if (activeTab) {
            activeTab.style.display = 'block';
        } else {
            console.error(`Tab content for '${tabName}' not found.`);
        }
    }
})();