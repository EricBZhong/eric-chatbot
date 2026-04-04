// Insight Engine: Q&A with Claude about your conversation

const history = [];

function askExample(el) {
    document.getElementById('insight-input').value = el.textContent;
    askInsight();
}

async function askInsight() {
    const input = document.getElementById('insight-input');
    const question = input.value.trim();
    if (!question) return;

    if (!getSelectedContact()) {
        alert('Select a contact first.');
        return;
    }

    const btn = document.getElementById('ask-btn');
    btn.disabled = true;
    btn.textContent = 'THINKING...';
    document.getElementById('insight-loading').style.display = 'flex';
    document.getElementById('insight-response').style.display = 'none';

    try {
        const res = await fetch(withContact('/api/insights'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
        });
        const data = await res.json();

        const responseDiv = document.getElementById('insight-response');
        responseDiv.textContent = data.answer;
        responseDiv.style.display = 'block';

        // Add to history
        history.unshift({ question, answer: data.answer });
        renderHistory();

        input.value = '';
    } catch (e) {
        document.getElementById('insight-response').textContent = `Error: ${e.message}`;
        document.getElementById('insight-response').style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.textContent = 'ASK';
        document.getElementById('insight-loading').style.display = 'none';
    }
}

function renderHistory() {
    const container = document.getElementById('insight-history');
    if (history.length <= 1) {
        container.innerHTML = '';
        return;
    }

    // Show older entries (skip first since it's shown above)
    container.innerHTML = `
        <div class="section-title" style="margin-top:24px;">PREVIOUS INSIGHTS</div>
        ${history.slice(1).map(h => `
            <div class="card" style="margin-bottom:16px;">
                <div style="color:var(--neon-cyan); font-size:0.85rem; margin-bottom:8px; font-weight:600;">${h.question}</div>
                <div style="font-size:0.9rem; color:var(--text-secondary); white-space:pre-wrap; line-height:1.6;">${h.answer}</div>
            </div>
        `).join('')}
    `;
}
