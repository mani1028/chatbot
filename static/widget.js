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

    let siteFeatures = {
        plan: 'free',  // free, pro, enterprise
        analytics_enabled: false,
        context_engine_enabled: false,
        escalation_enabled: false,
        compression_enabled: false
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
            
            // Phase 2: Load site features/plan
            const planRes = await fetch(`${API_BASE}/api/site-features?site_key=${SITE_KEY}`);
            const planData = await planRes.json();
            siteFeatures = {
                plan: planData.plan || 'free',
                analytics_enabled: planData.plan === 'pro' || planData.plan === 'enterprise',
                context_engine_enabled: planData.plan === 'pro' || planData.plan === 'enterprise',
                escalation_enabled: planData.plan === 'pro' || planData.plan === 'enterprise',
                compression_enabled: planData.plan === 'pro' || planData.plan === 'enterprise'
            };
            
            buildUI();
            // NEW: Only load chat history if admin enabled it
            if (config.preserve_chat_history) {
                await loadChatHistory();
            }
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

        // Phase 2: Add escalation button if enabled
        const escalationBtn = siteFeatures.escalation_enabled ? `
            <button class="widget-escalate" title="Connect to Human Agent">
                👤 Escalate
            </button>
        ` : '';

        // Phase 2: Add context indicator if context engine enabled
        const contextIndicator = siteFeatures.context_engine_enabled ? `
            <div class="context-indicator" id="context-indicator" style="display: none;">
                <span class="indicator-dot"></span>
                <span class="indicator-text">Support available</span>
            </div>
        ` : '';

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
                ${contextIndicator}
                <div class="widget-body" id="chat-body">
                </div>
                <div class="widget-footer">
                    <input type="text" class="widget-input" id="chat-input" placeholder="Type a message...">
                    <button class="widget-send" style="background-color: ${config.primary_color}">➤</button>
                    ${escalationBtn}
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
        const escalateBtn = wrapper.querySelector('.widget-escalate');
        if (escalateBtn) escalateBtn.onclick = escalateToHuman;
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

    // Phase 2: Escalate to human agent
    async function escalateToHuman() {
        appendMessage('Connecting you to a human agent...', 'bot');
        try {
            const res = await fetch(`${API_BASE}/api/escalate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site_key: SITE_KEY,
                    session_id: sessionId
                })
            });
            if (res.ok) {
                const data = await res.json();
                appendMessage('A human agent has been assigned to you.', 'bot agent-message');
                if (socket && socket.connected) {
                    socket.emit('escalation_request', { session_id: sessionId });
                }
            }
        } catch(e) {
            console.error('Escalation failed:', e);
            appendMessage('Failed to escalate. Please try again.', 'bot error-state');
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

            // Phase 2: Handle context analysis (frustration, confusion)
            if (siteFeatures.context_engine_enabled && data.context_analysis) {
                updateContextIndicator(data.context_analysis);
                
                // Auto-escalate if context engine detects high frustration
                if (data.context_analysis.should_escalate) {
                    appendMessage('I sense you may need additional support. Would you like to speak with a human agent?', 'bot');
                    showEscalationOffer();
                    return;
                }
            }

            let rendered = false;

            // FIX: Print the bot's conversational response looking for reply, text, or response keys
            const botMessageText = data.reply || data.text || data.response;
            if (botMessageText) {
                appendMessage(botMessageText, 'bot');
                rendered = true;
            }

            // NEW: Render workflow state and collected data
            if (data.workflow_state && data.collected_data) {
                renderWorkflowState(data.workflow_state, data.collected_data, data.intent_name);
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

    function renderWorkflowState(state, collectedData, intentName) {
        // Define workflow configurations
        const workflowConfigs = {
            'booking': {
                name: 'Booking',
                states: ['greeting', 'collecting_service', 'collecting_name', 'collecting_email', 'collecting_phone', 'collecting_date', 'collecting_time', 'confirming', 'completed'],
                fields: ['service', 'name', 'email', 'phone', 'date', 'time']
            },
            'lead_capture': {
                name: 'Lead Capture',
                states: ['greeting', 'collecting_name', 'collecting_email', 'collecting_phone', 'collecting_message', 'confirming', 'completed'],
                fields: ['name', 'email', 'phone', 'message']
            },
            'support': {
                name: 'Support',
                states: ['greeting', 'collecting_issue', 'collecting_priority', 'collecting_contact', 'confirming', 'escalated'],
                fields: ['issue', 'priority', 'contact']
            }
        };

        // Detect workflow type from intent or state
        let workflowType = null;
        if (intentName && intentName.includes('booking')) workflowType = 'booking';
        else if (intentName && (intentName.includes('lead') || intentName.includes('capture'))) workflowType = 'lead_capture';
        else if (intentName && intentName.includes('support')) workflowType = 'support';
        
        const config = workflowType ? workflowConfigs[workflowType] : null;
        
        if (!config) return; // Skip if workflow type unknown

        // Calculate progress
        const currentStateIndex = config.states.indexOf(state);
        const totalStates = config.states.length;
        const progress = currentStateIndex >= 0 ? Math.round((currentStateIndex / totalStates) * 100) : 0;

        // Create workflow card
        const card = document.createElement('div');
        card.className = 'workflow-card';
        card.innerHTML = `
            <div class="workflow-header">
                <span class="workflow-title">📋 ${config.name} Workflow</span>
                <span class="workflow-progress">${currentStateIndex + 1}/${totalStates}</span>
            </div>
            <div class="workflow-bar">
                <div class="workflow-progress-fill" style="width: ${progress}%"></div>
            </div>
            <div class="workflow-state">
                <strong>Current Step:</strong> ${formatStateLabel(state)}
            </div>
        `;

        // Add collected data section
        if (Object.keys(collectedData).length > 0) {
            const dataSection = document.createElement('div');
            dataSection.className = 'workflow-collected';
            dataSection.innerHTML = '<strong>✓ Collected Data:</strong>';
            
            const dataList = document.createElement('ul');
            dataList.className = 'collected-list';
            
            config.fields.forEach(field => {
                if (collectedData[field]) {
                    const li = document.createElement('li');
                    li.innerHTML = `<span class="field-name">${capitalizeFirst(field)}:</span> <span class="field-value">${escapeHtml(String(collectedData[field]))}</span>`;
                    dataList.appendChild(li);
                }
            });
            
            dataSection.appendChild(dataList);
            card.appendChild(dataSection);
        }

        // Append to chat
        const body = document.getElementById('chat-body');
        if (body) {
            body.appendChild(card);
            body.scrollTop = body.scrollHeight;
        }
    }

    function formatStateLabel(state) {
        return state
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    function capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    function escapeHtml(text) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, m => map[m]);
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

    // Phase 2: Context Indicator - show frustration/confusion level
    function updateContextIndicator(contextAnalysis) {
        const indicator = document.getElementById('context-indicator');
        if (!indicator) return;

        const frustration = contextAnalysis.frustration_level || 0;
        const confusion = contextAnalysis.confusion_level || 0;

        if (frustration > 0.6) {
            indicator.style.display = 'flex';
            indicator.innerHTML = `
                <span class="indicator-dot" style="background-color: #ef4444;"></span>
                <span class="indicator-text">User frustrated - escalation available</span>
            `;
        } else if (confusion > 0.5) {
            indicator.style.display = 'flex';
            indicator.innerHTML = `
                <span class="indicator-dot" style="background-color: #f59e0b;"></span>
                <span class="indicator-text">User may need clarification</span>
            `;
        } else {
            indicator.style.display = 'none';
        }
    }

    // Phase 2: Show escalation offer button
    function showEscalationOffer() {
        const body = document.getElementById('chat-body');
        if (!body) return;

        const offerDiv = document.createElement('div');
        offerDiv.className = 'escalation-offer';
        offerDiv.innerHTML = `
            <button class="escalation-yes" onclick="escalateToHuman(); this.parentElement.remove();">
                Yes, Connect Me
            </button>
            <button class="escalation-no" onclick="this.parentElement.remove();">
                No, Continue with Bot
            </button>
        `;
        body.appendChild(offerDiv);
        body.scrollTop = body.scrollHeight;
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