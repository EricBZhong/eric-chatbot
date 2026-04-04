// Clone Chat: AI that mimics her texting style

const chatHistory = [];

async function init() {
    // Wait for contact selector to load
    await new Promise(r => setTimeout(r, 150));

    if (!getSelectedContact()) {
        document.getElementById('clone-name').textContent = 'SELECT A CONTACT FIRST';
        document.getElementById('send-btn').disabled = true;
        return;
    }

    try {
        const res = await fetch(withContact('/api/chat/profile'));
        const profile = await res.json();
        if (profile.name) {
            document.getElementById('clone-name').textContent = `CLONE: ${profile.name.toUpperCase()}`;
            document.getElementById('clone-info').textContent =
                `Style: ${profile.cap_style} | Avg ${profile.avg_words} words/msg | ${profile.top_emojis?.join('') || 'minimal emoji'}`;
        }
    } catch (e) {
        // Profile load failed, not critical
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    if (!getSelectedContact()) {
        alert('Select a contact first.');
        return;
    }

    const btn = document.getElementById('send-btn');
    btn.disabled = true;

    // Add user message
    chatHistory.push({ role: 'user', content: message });
    addBubble(message, 'user');
    input.value = '';

    // Show typing indicator
    const typingId = addTypingIndicator();

    try {
        const res = await fetch(withContact('/api/chat'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, history: chatHistory }),
        });
        const data = await res.json();

        removeTypingIndicator(typingId);
        chatHistory.push({ role: 'assistant', content: data.response });
        addBubble(data.response, 'clone');
    } catch (e) {
        removeTypingIndicator(typingId);
        addBubble(`Error: ${e.message}`, 'clone');
    } finally {
        btn.disabled = false;
        input.focus();
    }
}

function addBubble(text, type) {
    const container = document.getElementById('chat-messages');

    // Remove placeholder if present
    const placeholder = container.querySelector('.chat-placeholder');
    if (placeholder) placeholder.remove();

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${type}`;
    bubble.textContent = text;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

function addTypingIndicator() {
    const container = document.getElementById('chat-messages');
    const indicator = document.createElement('div');
    indicator.className = 'chat-bubble clone';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = '<div class="loading-spinner" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></div> <span style="color:var(--text-dim);font-size:0.85rem;">typing...</span>';
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
    return 'typing-indicator';
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

init();
