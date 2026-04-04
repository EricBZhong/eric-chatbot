// Profile page: global stats + personality analysis

let profileStats = null;
let profileAnalysis = null;

function formatTime(seconds) {
    if (seconds == null) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
    return `${(seconds / 86400).toFixed(1)}d`;
}

async function initProfile() {
    try {
        const res = await fetch('/api/profile/stats');
        const data = await res.json();

        if (data.error) {
            document.getElementById('loading').innerHTML = `<span style="color:var(--neon-red);">${data.error}</span>`;
            return;
        }

        profileStats = data;
        renderProfileStats(data);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('profile-content').style.display = 'block';

        // Load analysis
        loadProfileAnalysis();
    } catch (e) {
        document.getElementById('loading').innerHTML = `<span style="color:var(--neon-red);">Error loading profile: ${e.message}</span>`;
    }
}

function renderProfileStats(data) {
    // HUD
    const hud = document.getElementById('profile-hud');
    hud.innerHTML = `
        <div class="hud-item">
            <div class="hud-label">MESSAGES SENT</div>
            <div class="hud-value cyan">${(data.total_sent || 0).toLocaleString()}</div>
        </div>
        <div class="hud-item">
            <div class="hud-label">MESSAGES RECEIVED</div>
            <div class="hud-value pink">${(data.total_received || 0).toLocaleString()}</div>
        </div>
        <div class="hud-item">
            <div class="hud-label">CONTACTS</div>
            <div class="hud-value green">${data.total_contacts || 0}</div>
        </div>
        <div class="hud-item">
            <div class="hud-label">MOST TEXTED</div>
            <div class="hud-value yellow" style="font-size:1.2rem;">${data.most_texted || '—'}</div>
        </div>
    `;

    // Stats Grid
    const grid = document.getElementById('profile-stats-grid');
    const cards = [
        { label: 'Messages/Day', value: data.msgs_per_day || 0, color: 'cyan' },
        { label: 'Avg Response', value: formatTime(data.avg_response_time), color: 'green' },
        { label: 'Avg Length', value: `${data.avg_message_length || 0} words`, color: 'cyan' },
        { label: 'Emoji Rate', value: `${data.emoji_rate || 0}%`, color: 'pink' },
        { label: 'Question Rate', value: `${data.question_rate || 0}%`, color: 'yellow' },
        { label: 'Initiative Rate', value: `${data.initiative_rate || 0}%`, color: 'green' },
        { label: 'Double Texts', value: data.double_texts || 0, color: 'purple' },
        { label: 'Late Night Texts', value: data.late_night_count || 0, color: 'pink' },
    ];

    grid.innerHTML = cards.map(c => `
        <div class="stat-card">
            <div class="stat-number" style="color:var(--neon-${c.color})">${c.value}</div>
            <div class="stat-label">${c.label}</div>
        </div>
    `).join('');

    // Character Sheet
    const charContainer = document.getElementById('profile-character');
    const level = data.level || 1;
    const charClass = data.character_class || 'The Balanced One';
    charContainer.innerHTML = `
        <div class="character-card me">
            <div class="character-header">
                <div class="avatar">ME</div>
                <div>
                    <div class="character-name">${getUserName()}</div>
                    <div class="character-class">${charClass}</div>
                    <div class="character-level">LVL ${level} &middot; ${(data.total_sent || 0).toLocaleString()} msgs sent</div>
                </div>
            </div>
            <div class="stat-bar-container">
                <div class="stat-bar-label"><span>Initiative</span><span>${data.initiative_rate || 0}%</span></div>
                <div class="stat-bar"><div class="stat-bar-fill cyan" style="width:${data.initiative_rate || 0}%"></div></div>
            </div>
            <div class="stat-bar-container">
                <div class="stat-bar-label"><span>Emoji Game</span><span>${data.emoji_rate || 0}%</span></div>
                <div class="stat-bar"><div class="stat-bar-fill pink" style="width:${data.emoji_rate || 0}%"></div></div>
            </div>
            <div class="stat-bar-container">
                <div class="stat-bar-label"><span>Question Rate</span><span>${data.question_rate || 0}%</span></div>
                <div class="stat-bar"><div class="stat-bar-fill yellow" style="width:${data.question_rate || 0}%"></div></div>
            </div>
        </div>
    `;

    // Hours chart
    renderHoursChart(data.busiest_hours || {});
}

function renderHoursChart(hoursData) {
    const ctx = document.getElementById('hours-chart').getContext('2d');
    const labels = [];
    const values = [];

    for (let h = 0; h < 24; h++) {
        const label = h === 0 ? '12am' : h < 12 ? `${h}am` : h === 12 ? '12pm' : `${h - 12}pm`;
        labels.push(label);
        values.push(hoursData[h] || 0);
    }

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Messages Sent',
                data: values,
                backgroundColor: values.map((v, i) => {
                    const max = Math.max(...values);
                    const intensity = max > 0 ? v / max : 0;
                    return `rgba(0, 240, 255, ${0.2 + intensity * 0.6})`;
                }),
                borderColor: 'rgba(0, 240, 255, 0.5)',
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: '#555577', maxTicksLimit: 12 },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                },
                y: {
                    ticks: { color: '#555577' },
                    grid: { color: 'rgba(255,255,255,0.03)' }
                }
            }
        }
    });
}

async function loadProfileAnalysis() {
    try {
        const res = await fetch('/api/profile/analysis');
        const data = await res.json();
        if (!data.error) {
            profileAnalysis = data;
            renderProfileAnalysis(data);
        }
    } catch (e) {
        // No analysis yet
    }
}

function renderProfileAnalysis(data) {
    // Personality card
    document.getElementById('profile-title').textContent = data.personality_title || 'Your Profile';
    document.getElementById('profile-summary').textContent = data.personality_summary || '';
    document.getElementById('profile-zodiac').textContent = data.texting_zodiac || '';

    // Communication style
    const commStyle = document.getElementById('profile-comm-style');
    if (data.communication_style) {
        commStyle.innerHTML = `
            <div class="section-title">COMMUNICATION STYLE</div>
            <div class="gameplan-card" style="border-color: rgba(0, 240, 255, 0.2); margin-bottom:32px;">
                <div class="gameplan-text">${data.communication_style}</div>
            </div>
        `;
    }

    // Strengths & Growth Areas
    const flagsContainer = document.getElementById('profile-flags');
    const strengths = (data.strengths || []).map(s =>
        `<div class="flag-item"><span class="flag-icon green">&#10003;</span><span>${s}</span></div>`
    ).join('');
    const growth = (data.growth_areas || []).map(g =>
        `<div class="flag-item"><span class="flag-icon" style="color:var(--neon-yellow);">&#9733;</span><span>${g}</span></div>`
    ).join('');

    flagsContainer.innerHTML = `
        <div class="section-title">STRENGTHS & GROWTH</div>
        <div class="flags-container" style="margin-bottom:32px;">
            <div class="flags-panel green">
                <div class="card-title" style="color:var(--neon-green);">STRENGTHS</div>
                ${strengths || '<div style="color:var(--text-dim);">Run analysis first</div>'}
            </div>
            <div class="flags-panel" style="border: 1px solid rgba(255, 225, 0, 0.2);">
                <div class="card-title" style="color:var(--neon-yellow);">GROWTH AREAS</div>
                ${growth || '<div style="color:var(--text-dim);">Run analysis first</div>'}
            </div>
        </div>
    `;

    // Fun facts
    const factsContainer = document.getElementById('profile-facts');
    factsContainer.innerHTML = (data.fun_facts || []).map(f =>
        `<div class="profile-fact">${f}</div>`
    ).join('') || '<div style="color:var(--text-dim);">Run analysis first</div>';

    // Who you are
    document.getElementById('profile-who').textContent = data.who_you_are || 'Run the profile analysis to see your personality breakdown.';
}

async function refreshProfile() {
    const btn = document.getElementById('profile-refresh-btn');
    btn.disabled = true;
    btn.textContent = 'ANALYZING...';

    try {
        const res = await fetch('/api/profile/analysis/refresh', { method: 'POST' });
        const data = await res.json();
        if (!data.error) {
            profileAnalysis = data;
            renderProfileAnalysis(data);
        }
    } catch (e) {
        // Error
    } finally {
        btn.disabled = false;
        btn.textContent = 'REFRESH PROFILE ANALYSIS';
    }
}

// Init
initProfile();
