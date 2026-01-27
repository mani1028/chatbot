/**
 * Chat UI JavaScript
 * Handles real-time chat interactions
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
            displayBotMessage(data.message, data.confidence, data.is_answered);
        } else {
            // Display error
            displayBotMessage('Sorry, something went wrong. Please try again.', 0, false);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        removeTypingIndicator();
        displayBotMessage('Sorry, I couldn\'t connect to the server. Please check your connection.', 0, false);
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

function displayBotMessage(message, confidence, isAnswered) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';

    let confidenceInfo = '';
    if (confidence > 0) {
        const badge = isAnswered ? '✅' : '❓';
        confidenceInfo = `<div class="confidence-badge">${badge} Confidence: ${(confidence * 100).toFixed(0)}%</div>`;
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

function displayTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');

    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `
        <div class="message-content">
            <p>Bot is thinking<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></p>
        </div>
    `;

    chatMessages.appendChild(typingDiv);
    scrollToBottom();

    // Add animation
    const style = document.createElement('style');
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
    `;
    document.head.appendChild(style);
}

function removeTypingIndicator() {
    const typing = document.getElementById('typingIndicator');
    if (typing) {
        typing.remove();
    }
}

function scrollToBottom() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function minimizeChat() {
    const container = document.querySelector('.chat-container');
    const toggle = document.getElementById('chatToggle');

    container.style.display = 'none';
    toggle.style.display = 'flex';
}

function maximizeChat() {
    const container = document.querySelector('.chat-container');
    const toggle = document.getElementById('chatToggle');

    container.style.display = 'flex';
    toggle.style.display = 'none';

    // Focus input
    document.getElementById('messageInput').focus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close chat on escape key (optional)
document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
        const container = document.querySelector('.chat-container');
        if (container && container.style.display !== 'none') {
            minimizeChat();
        }
    }
});
