// History: analysis trends over time

let historyData = [];

async function init() {
    await new Promise(r => setTimeout(r, 100));

    if (!getSelectedContact()) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('no-history').style.display = 'block';
        return;
    }

    try {
        const res = await fetch(withContact('/api/history'));
        const data = await res.json();
        historyData = (data.history || []).reverse(); // Oldest first for charts

        document.getElementById('loading').style.display = 'none';

        if (historyData.length === 0) {
            document.getElementById('no-history').style.display = 'block';
            return;
        }

        document.getElementById('history-content').style.display = 'block';
        renderTrendChart();
        renderScoreCards();
        renderTimeline();
    } catch (e) {
        document.getElementById('loading').innerHTML = `<span style="color:var(--neon-red);">Error: ${e.message}</span>`;
    }
}

function renderTrendChart() {
    const ctx = document.getElementById('trend-chart').getContext('2d');

    const labels = historyData.map((h, i) => {
        const d = new Date(h.created_at);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });

    const relationshipScores = historyData.map(h => h.result.relationship_score || null);
    const affectionLevels = historyData.map(h => h.result.affection_level || null);
    const romanticScores = historyData.map(h => h.result.interest_type?.romantic_score || null);

    const datasets = [
        {
            label: 'Relationship Score',
            data: relationshipScores,
            borderColor: '#00ff88',
            backgroundColor: 'rgba(0, 255, 136, 0.1)',
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 6,
        },
        {
            label: 'Affection Level',
            data: affectionLevels,
            borderColor: '#ff00aa',
            backgroundColor: 'rgba(255, 0, 170, 0.1)',
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 6,
        },
    ];

    // Only include romantic score if any values exist
    if (romanticScores.some(s => s !== null)) {
        datasets.push({
            label: 'Romantic Energy',
            data: romanticScores,
            borderColor: '#b400ff',
            backgroundColor: 'rgba(180, 0, 255, 0.1)',
            borderWidth: 2,
            tension: 0.3,
            fill: true,
            pointRadius: 4,
            pointHoverRadius: 6,
        });
    }

    new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            interaction: {
                intersect: false,
                mode: 'index',
            },
            plugins: {
                legend: {
                    labels: { color: '#8888aa', font: { family: 'Rajdhani', size: 12 } }
                },
                tooltip: {
                    backgroundColor: 'rgba(10, 10, 20, 0.9)',
                    titleColor: '#00f0ff',
                    bodyColor: '#ccccdd',
                    borderColor: 'rgba(0, 240, 255, 0.3)',
                    borderWidth: 1,
                }
            },
            scales: {
                x: {
                    ticks: { color: '#555577', maxTicksLimit: 10 },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                },
                y: {
                    min: 0,
                    max: 100,
                    ticks: { color: '#555577' },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                }
            }
        }
    });
}

function renderScoreCards() {
    const container = document.getElementById('score-cards');
    if (historyData.length < 2) {
        container.innerHTML = '<div style="color:var(--text-dim); font-size:0.9rem;">Need at least 2 analyses to show trends.</div>';
        return;
    }

    const latest = historyData[historyData.length - 1].result;
    const prev = historyData[historyData.length - 2].result;

    function delta(current, previous) {
        if (current == null || previous == null) return '';
        const d = current - previous;
        if (d > 0) return `<span style="color:var(--neon-green);">+${d}</span>`;
        if (d < 0) return `<span style="color:var(--neon-red);">${d}</span>`;
        return `<span style="color:var(--text-dim);">0</span>`;
    }

    const scores = [
        {
            label: 'RELATIONSHIP SCORE',
            value: latest.relationship_score || '—',
            change: delta(latest.relationship_score, prev.relationship_score),
            color: 'green',
        },
        {
            label: 'AFFECTION LEVEL',
            value: latest.affection_level || '—',
            change: delta(latest.affection_level, prev.affection_level),
            color: 'pink',
        },
        {
            label: 'ROMANTIC ENERGY',
            value: latest.interest_type?.romantic_score || '—',
            change: delta(latest.interest_type?.romantic_score, prev.interest_type?.romantic_score),
            color: 'purple',
        },
        {
            label: 'GREEN FLAGS',
            value: (latest.green_flags || []).length,
            change: delta((latest.green_flags || []).length, (prev.green_flags || []).length),
            color: 'green',
        },
        {
            label: 'RED FLAGS',
            value: (latest.red_flags || []).length,
            change: delta((latest.red_flags || []).length, (prev.red_flags || []).length),
            color: 'red',
        },
    ];

    container.innerHTML = scores.map(s => `
        <div class="history-score-card">
            <div class="stat-label">${s.label}</div>
            <div class="stat-number" style="color:var(--neon-${s.color});">${s.value}</div>
            ${s.change ? `<div class="history-delta">${s.change} since last</div>` : ''}
        </div>
    `).join('');
}

function renderTimeline() {
    const container = document.getElementById('timeline');
    // Show newest first
    const reversed = [...historyData].reverse();

    container.innerHTML = reversed.map((entry, i) => {
        const d = new Date(entry.created_at);
        const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const timeStr = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        const r = entry.result;

        const relScore = r.relationship_score || '—';
        const affection = r.affection_level || '—';
        const romantic = r.interest_type?.romantic_score || '—';
        const classification = (r.interest_type?.classification || '').replace(/_/g, ' ');
        const greenCount = (r.green_flags || []).length;
        const redCount = (r.red_flags || []).length;
        const hasFeedback = entry.user_feedback ? true : false;

        return `
            <div class="history-entry" onclick="showDetail(${entry.id})">
                <div class="history-entry-header">
                    <div class="history-entry-date">${dateStr} <span style="color:var(--text-dim);">${timeStr}</span></div>
                    ${hasFeedback ? '<span class="history-badge">HAS FEEDBACK</span>' : ''}
                    ${i === 0 ? '<span class="history-badge latest">LATEST</span>' : ''}
                </div>
                <div class="history-entry-scores">
                    <span class="history-score green">${relScore}</span>
                    <span class="history-score-label">Relationship</span>
                    <span class="history-score pink">${affection}</span>
                    <span class="history-score-label">Affection</span>
                    <span class="history-score purple">${romantic}</span>
                    <span class="history-score-label">Romantic</span>
                </div>
                <div class="history-entry-meta">
                    ${classification ? `<span class="history-tag">${classification}</span>` : ''}
                    <span style="color:var(--neon-green);">${greenCount} green</span>
                    <span style="color:var(--neon-red);">${redCount} red</span>
                </div>
                ${r.summary ? `<div class="history-summary">${r.summary}</div>` : ''}
            </div>
        `;
    }).join('');
}

async function showDetail(entryId) {
    const modal = document.getElementById('detail-modal');
    const body = document.getElementById('detail-body');
    modal.style.display = 'flex';

    body.innerHTML = '<div class="loading"><div class="loading-spinner"></div><span>Loading...</span></div>';

    try {
        const res = await fetch(`/api/history/${entryId}`);
        const entry = await res.json();
        const r = entry.result || {};
        const d = new Date(entry.created_at);
        const dateStr = d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });

        let html = `<h2 style="color:var(--neon-cyan); font-family:var(--font-display); margin-bottom:8px;">Analysis — ${dateStr}</h2>`;

        if (entry.user_feedback) {
            html += `<div class="history-feedback-block"><strong>Your Feedback:</strong> ${entry.user_feedback}</div>`;
        }

        // Scores
        html += `
            <div class="history-detail-scores">
                <div class="stat-card"><div class="stat-number" style="color:var(--neon-green);">${r.relationship_score || '—'}</div><div class="stat-label">Relationship</div></div>
                <div class="stat-card"><div class="stat-number" style="color:var(--neon-pink);">${r.affection_level || '—'}</div><div class="stat-label">Affection</div></div>
                <div class="stat-card"><div class="stat-number" style="color:var(--neon-purple);">${r.interest_type?.romantic_score || '—'}</div><div class="stat-label">Romantic</div></div>
            </div>
        `;

        // Summary
        if (r.summary) {
            html += `<div class="history-detail-section"><h3>Summary</h3><p>${r.summary}</p></div>`;
        }

        // Classification
        if (r.interest_type) {
            html += `<div class="history-detail-section"><h3>Vibe Check</h3><p><strong>${(r.interest_type.classification || '').replace(/_/g, ' ').toUpperCase()}</strong> — ${r.interest_type.reasoning || ''}</p></div>`;
        }

        // Flags
        if (r.green_flags?.length || r.red_flags?.length) {
            html += `<div class="history-detail-section"><h3>Flags</h3>`;
            (r.green_flags || []).forEach(f => { html += `<div class="flag-item"><span class="flag-icon green">&#10003;</span>${f}</div>`; });
            (r.red_flags || []).forEach(f => { html += `<div class="flag-item"><span class="flag-icon red">&#9888;</span>${f}</div>`; });
            html += `</div>`;
        }

        // Moves
        if (r.moves_to_make?.length) {
            html += `<div class="history-detail-section"><h3>Moves</h3>`;
            r.moves_to_make.forEach((m, i) => { html += `<div class="advice-item"><span class="advice-marker" style="color:var(--neon-green); background:rgba(0,255,136,0.1);">MOVE ${i + 1}</span>${m}</div>`; });
            html += `</div>`;
        }

        // Game plan summary
        if (r.game_plan?.texting?.frequency) {
            html += `<div class="history-detail-section"><h3>Texting Strategy</h3><p>${r.game_plan.texting.frequency}</p></div>`;
        }

        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<div style="color:var(--neon-red);">Error loading details: ${e.message}</div>`;
    }
}

function closeDetail() {
    document.getElementById('detail-modal').style.display = 'none';
}

// Close modal on escape or outside click
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDetail(); });
document.addEventListener('click', e => {
    if (e.target.id === 'detail-modal') closeDetail();
});

init();
