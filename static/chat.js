/**
 * Chat UI JavaScript
 * Handles real-time chat interactions for the main demo page
 */

document.addEventListener('DOMContentLoaded', function () {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    // DEFAULT SITE ID for the main demo page
    const DEFAULT_SITE_ID = 1; 

    function appendMessage(text, isUser) {
        if (!chatBox) return;
        const div = document.createElement('div');
        div.className = isUser ? 'user-message' : 'bot-message';
        div.textContent = text;
        chatBox.appendChild(div);
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
                    site_id: DEFAULT_SITE_ID
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Server Error');
            }

            const data = await response.json();
            appendMessage(data.reply, false);

        } catch (error) {
            console.error('Error:', error);
            appendMessage("⚠️ Error: " + error.message, false);
        }
    }

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
    if (userInput) userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
});