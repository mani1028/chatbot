/**
 * Chat UI JavaScript - Enterprise Intent-Based Chatbot
 * Handles real-time chat interactions with lead capture and handoff flow
 */

// Initialize session and UI
document.addEventListener('DOMContentLoaded', function () {
    initializeChat();
});

function initializeChat() {
    // Set up enter key for sending messages
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('keypress', handleKeyPress);
        messageInput.focus();
    }
}

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();

    if (!message) {
        return;
    }

    // Display user message immediately
    displayUserMessage(message);

    // Clear input
    messageInput.value = '';

    // Show typing indicator
    displayTypingIndicator();

    // Send message to backend
    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: message
        })
    })
    .then(response => response.json())
    .then(data => {
        // Remove typing indicator
        removeTypingIndicator();

        if (data.success) {
            // Display bot response
            displayBotMessage(data.message, data.confidence, data.message_type);
            
            // If handoff is required, show lead capture form
            if (data.requires_handoff) {
                displayLeadCaptureForm(data);
            }
        } else {
            // Display error
            displayBotMessage('Sorry, something went wrong. Please try again.', 0, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        removeTypingIndicator();
        displayBotMessage('Sorry, I couldn\'t connect to the server. Please check your connection.', 0, 'error');
    });

    // Focus back to input
    messageInput.focus();
}

function displayUserMessage(message) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(message)}</p>
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function displayBotMessage(message, confidence, messageType) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';

    let confidenceInfo = '';
    let typeIcon = '💬';
    
    if (messageType === 'auto_response') {
        typeIcon = '✅';
        if (confidence >= 0.8) {
            confidenceInfo = `<div class="confidence-badge high-confidence">✓ High Confidence (${(confidence * 100).toFixed(0)}%)</div>`;
        } else {
            confidenceInfo = `<div class="confidence-badge medium-confidence">≈ Medium Confidence (${(confidence * 100).toFixed(0)}%)</div>`;
        }
    } else if (messageType === 'lead_capture') {
        typeIcon = '🤝';
    } else if (messageType === 'error') {
        typeIcon = '⚠️';
    }

    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(message)}</p>
            ${confidenceInfo}
        </div>
    `;

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function displayLeadCaptureForm(responseData) {
    const chatMessages = document.getElementById('chatMessages');

    const formDiv = document.createElement('div');
    formDiv.className = 'message bot-message lead-capture-form';
    formDiv.id = 'leadCaptureForm';
    
    formDiv.innerHTML = `
        <div class="message-content">
            <h4>Get Expert Support 🤝</h4>
            <p>To provide the best assistance, please share your details:</p>
            <form id="leadForm">
                <div class="form-group">
                    <label for="leadName">Name (Optional):</label>
                    <input type="text" id="leadName" name="name" placeholder="Your name" />
                </div>
                
                <div class="form-group">
                    <label for="leadEmail">Email (Required):</label>
                    <input type="email" id="leadEmail" name="email" placeholder="your@email.com" required />
                </div>
                
                <div class="form-group">
                    <label for="leadPhone">Phone (Optional):</label>
                    <input type="tel" id="leadPhone" name="phone" placeholder="(123) 456-7890" />
                </div>
                
                <div class="form-group">
                    <label for="leadMessage">Message:</label>
                    <textarea id="leadMessage" name="message" placeholder="How can we help?" rows="3"></textarea>
                </div>
                
                <button type="submit" class="btn-submit">Submit for Expert Review</button>
                <button type="button" class="btn-cancel" onclick="cancelLeadCapture()">Cancel</button>
            </form>
        </div>
    `;

    chatMessages.appendChild(formDiv);
    scrollToBottom();

    // Add form submit handler
    const leadForm = document.getElementById('leadForm');
    leadForm.addEventListener('submit', handleLeadSubmit);
}

function handleLeadSubmit(e) {
    e.preventDefault();
    
    const name = document.getElementById('leadName').value.trim();
    const email = document.getElementById('leadEmail').value.trim();
    const phone = document.getElementById('leadPhone').value.trim();
    const message = document.getElementById('leadMessage').value.trim();
    
    if (!email) {
        alert('Email is required');
        return;
    }

    // Disable form while submitting
    const submitBtn = e.target.querySelector('.btn-submit');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    // Send lead data to backend
    fetch('/api/lead', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            name: name,
            email: email,
            phone: phone,
            message: message,
            intent_id: null
        })
    })
    .then(response => response.json())
    .then(data => {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
        
        if (data.success) {
            // Remove form and show confirmation
            const formDiv = document.getElementById('leadCaptureForm');
            if (formDiv) {
                formDiv.remove();
            }
            
            displayBotMessage(
                `Thank you, ${name || 'valued customer'}! We've received your information. A team member will contact you shortly at ${email}. 📧`,
                1.0,
                'auto_response'
            );
            
            // Clear the message input
            document.getElementById('messageInput').value = '';
        } else {
            alert('Error saving lead: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
        alert('Error submitting form. Please try again.');
    });
}

function cancelLeadCapture() {
    const formDiv = document.getElementById('leadCaptureForm');
    if (formDiv) {
        formDiv.remove();
    }
    
    displayBotMessage(
        'No problem! If you have any other questions, feel free to ask. 😊',
        0.5,
        'auto_response'
    );
}

function displayTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');

    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `
        <div class="message-content">
            <p>Assistant is thinking<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></p>
        </div>
    `;

    chatMessages.appendChild(typingDiv);
    scrollToBottom();

    // Add animation styles if not already present
    if (!document.querySelector('style[data-typing-animation]')) {
        const style = document.createElement('style');
        style.setAttribute('data-typing-animation', 'true');
        style.textContent = `
            .typing-indicator .dot {
                animation: blink 1.4s infinite;
            }
            .typing-indicator .dot:nth-child(1) {
                animation-delay: 0s;
            }
            .typing-indicator .dot:nth-child(2) {
                animation-delay: 0.2s;
            }
            .typing-indicator .dot:nth-child(3) {
                animation-delay: 0.4s;
            }
            @keyframes blink {
                0%, 60%, 100% { opacity: 0.3; }
                30% { opacity: 1; }
            }
            
            /* Form Styling */
            .lead-capture-form .form-group {
                margin: 12px 0;
            }
            .lead-capture-form label {
                display: block;
                margin-bottom: 4px;
                font-weight: 500;
                color: #333;
            }
            .lead-capture-form input,
            .lead-capture-form textarea {
                width: 100%;
                padding: 8px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-family: inherit;
                font-size: 14px;
                box-sizing: border-box;
            }
            .lead-capture-form input:focus,
            .lead-capture-form textarea:focus {
                outline: none;
                border-color: #4CAF50;
                background-color: #f0f8f0;
            }
            .lead-capture-form button {
                margin-right: 8px;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.3s ease;
            }
            .lead-capture-form .btn-submit {
                background-color: #4CAF50;
                color: white;
            }
            .lead-capture-form .btn-submit:hover:not(:disabled) {
                background-color: #45a049;
            }
            .lead-capture-form .btn-submit:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .lead-capture-form .btn-cancel {
                background-color: #f0f0f0;
                color: #333;
            }
            .lead-capture-form .btn-cancel:hover {
                background-color: #e0e0e0;
            }
            
            /* Confidence Badges */
            .confidence-badge {
                margin-top: 8px;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            .confidence-badge.high-confidence {
                background-color: #d4edda;
                color: #155724;
            }
            .confidence-badge.medium-confidence {
                background-color: #fff3cd;
                color: #856404;
            }
        `;
        document.head.appendChild(style);
    }
}

function removeTypingIndicator() {
    const typing = document.getElementById('typingIndicator');
    if (typing) {
        typing.remove();
    }
}

function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function minimizeChat() {
    const container = document.querySelector('.chat-container');
    const toggle = document.getElementById('chatToggle');

    if (container) container.style.display = 'none';
    if (toggle) toggle.style.display = 'flex';
}

function maximizeChat() {
    const container = document.querySelector('.chat-container');
    const toggle = document.getElementById('chatToggle');

    if (container) container.style.display = 'flex';
    if (toggle) toggle.style.display = 'none';

    // Focus input
    const input = document.getElementById('messageInput');
    if (input) input.focus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close chat on escape key
document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
        const container = document.querySelector('.chat-container');
        if (container && container.style.display !== 'none') {
            minimizeChat();
        }
    }
});
