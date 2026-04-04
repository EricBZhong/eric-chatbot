// Journal: AI-prompted reflection + in-person context logging

let selectedPrompt = null;

async function init() {
    // Wait for contact selector to load
    await new Promise(r => setTimeout(r, 150));

    if (!getSelectedContact()) {
        document.getElementById('prompts-loading').style.display = 'none';
        document.getElementById('prompts-list').innerHTML =
            '<div style="color:var(--text-dim);">Select a contact first to generate prompts.</div>';
        return;
    }

    loadPrompts();
    loadEntries();
}

async function loadPrompts() {
    try {
        const res = await fetch(withContact('/api/journal/prompts'));
        const data = await res.json();

        document.getElementById('prompts-loading').style.display = 'none';
        const list = document.getElementById('prompts-list');

        if (data.prompts && data.prompts.length > 0) {
            list.innerHTML = data.prompts.map(p =>
                `<div class="journal-prompt" onclick="selectPrompt(this)">${p}</div>`
            ).join('');
        } else {
            list.innerHTML = '<div style="color:var(--text-dim);">No prompts available</div>';
        }
    } catch (e) {
        document.getElementById('prompts-loading').style.display = 'none';
        document.getElementById('prompts-list').innerHTML =
            '<div style="color:var(--text-dim);">Could not load prompts</div>';
    }
}

function selectPrompt(el) {
    // Deselect others
    document.querySelectorAll('.journal-prompt').forEach(p => {
        p.style.borderColor = 'rgba(180, 0, 255, 0.15)';
        p.style.color = 'var(--text-secondary)';
    });

    // Select this one
    el.style.borderColor = 'var(--neon-purple)';
    el.style.color = 'var(--text-primary)';
    selectedPrompt = el.textContent;
    document.getElementById('selected-prompt').textContent = `Responding to: "${selectedPrompt}"`;
    document.getElementById('journal-input').focus();
}

async function saveEntry() {
    const input = document.getElementById('journal-input');
    const text = input.value.trim();
    if (!text) return;

    if (!getSelectedContact()) {
        alert('Select a contact first.');
        return;
    }

    const btn = document.getElementById('save-btn');
    btn.disabled = true;
    btn.textContent = 'SAVING...';

    try {
        await fetch(withContact('/api/journal/entry'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                entry_text: text,
                prompt_text: selectedPrompt,
            }),
        });

        input.value = '';
        selectedPrompt = null;
        document.getElementById('selected-prompt').textContent = '';
        document.querySelectorAll('.journal-prompt').forEach(p => {
            p.style.borderColor = 'rgba(180, 0, 255, 0.15)';
            p.style.color = 'var(--text-secondary)';
        });

        loadEntries();
    } catch (e) {
        alert('Error saving entry');
    } finally {
        btn.disabled = false;
        btn.textContent = 'SAVE ENTRY';
    }
}

async function loadEntries() {
    if (!getSelectedContact()) return;

    try {
        const res = await fetch(withContact('/api/journal/entries'));
        const data = await res.json();

        const list = document.getElementById('entries-list');
        if (data.entries && data.entries.length > 0) {
            list.innerHTML = data.entries.map(e => {
                const date = new Date(e.timestamp).toLocaleDateString('en-US', {
                    year: 'numeric', month: 'short', day: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                });
                return `
                    <div class="journal-entry">
                        <div class="journal-entry-date">${date}</div>
                        ${e.ai_prompt_text ? `<div class="journal-entry-prompt">"${e.ai_prompt_text}"</div>` : ''}
                        <div class="journal-entry-text">${e.entry_text}</div>
                    </div>
                `;
            }).join('');
        } else {
            list.innerHTML = '<div style="color:var(--text-dim); padding:20px;">No entries yet. Write your first one above!</div>';
        }
    } catch (e) {
        // Silent fail
    }
}

init();
