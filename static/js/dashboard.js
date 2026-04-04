// Dashboard: RPG stats, charts, analysis

let statsData = null;
let analysisData = null;

// Thinking sidebar state
let thinkingLogCount = 0;
let sidebarDismissed = false;

async function init() {
    // Wait a tick for contact selector to load
    await new Promise(r => setTimeout(r, 100));

    if (!getSelectedContact()) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('parse-banner').style.display = 'flex';
        return;
    }

    try {
        const res = await fetch(withContact('/api/stats'));
        const data = await res.json();

        if (data.error) {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('parse-banner').style.display = 'flex';
            return;
        }

        statsData = data;
        renderDashboard(data);
        document.getElementById('loading').style.display = 'none';
        document.getElementById('dashboard-content').style.display = 'block';

        // Try loading cached analysis
        loadAnalysis();
    } catch (e) {
        document.getElementById('loading').innerHTML = `<span style="color:var(--neon-red);">Error loading stats: ${e.message}</span>`;
    }
}

async function parseMessages() {
    const btn = document.querySelector('#parse-banner .btn-parse');
    btn.disabled = true;
    btn.textContent = 'PARSING...';

    try {
        const res = await fetch('/api/parse', { method: 'POST' });
        const data = await res.json();
        if (data.messages_parsed > 0) {
            location.reload();
        } else {
            btn.textContent = 'NO MESSAGES FOUND';
            setTimeout(() => { btn.textContent = 'PARSE MESSAGES'; btn.disabled = false; }, 2000);
        }
    } catch (e) {
        btn.textContent = 'ERROR';
        setTimeout(() => { btn.textContent = 'PARSE MESSAGES'; btn.disabled = false; }, 2000);
    }
}

async function importMessages() {
    // Find whichever import button was clicked
    const btns = document.querySelectorAll('[onclick*="importMessages"]');
    btns.forEach(b => { b.disabled = true; b.textContent = 'IMPORTING...'; });

    // Use the selected contact's phone number as the filter for re-import
    const contact = getSelectedContact();
    const body = contact ? { filter: contact } : {};

    try {
        const res = await fetch('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await res.json();
        if (data.error) {
            btns.forEach(b => { b.textContent = 'ERROR'; });
            alert(typeof data.error === 'string' ? data.error : data.message || 'Import failed');
            setTimeout(() => { btns.forEach(b => { b.textContent = 'RE-IMPORT iMESSAGE'; b.disabled = false; }); }, 2000);
        } else if (data.messages_parsed > 0) {
            location.reload();
        } else {
            btns.forEach(b => { b.textContent = 'NO MESSAGES FOUND'; });
            setTimeout(() => { btns.forEach(b => { b.textContent = 'RE-IMPORT iMESSAGE'; b.disabled = false; }); }, 2000);
        }
    } catch (e) {
        btns.forEach(b => { b.textContent = 'ERROR'; });
        setTimeout(() => { btns.forEach(b => { b.textContent = 'RE-IMPORT iMESSAGE'; b.disabled = false; }); }, 2000);
    }
}

function formatTime(seconds) {
    if (seconds == null) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
    return `${(seconds / 86400).toFixed(1)}d`;
}

function renderDashboard(data) {
    renderHUD(data);
    renderCharacterCards(data);
    renderAchievements(data);
    renderStatsGrid(data);
    renderTrendChart(data);
}

function renderHUD(data) {
    const hud = document.getElementById('hud');
    hud.innerHTML = `
        <div class="hud-item">
            <div class="hud-label">TOTAL MESSAGES</div>
            <div class="hud-value cyan">${data.total_messages.toLocaleString()}</div>
            <div class="hud-bar"><div class="hud-bar-fill" style="width:100%; background:var(--neon-cyan);"></div></div>
        </div>
        <div class="hud-item">
            <div class="hud-label">CONVERSATION DAYS</div>
            <div class="hud-value green">${data.total_days}</div>
            <div class="hud-bar"><div class="hud-bar-fill" style="width:${Math.min(data.total_days / 365 * 100, 100)}%; background:var(--neon-green);"></div></div>
        </div>
        <div class="hud-item">
            <div class="hud-label">MAX STREAK</div>
            <div class="hud-value yellow">${data.max_streak} days</div>
            <div class="hud-bar"><div class="hud-bar-fill" style="width:${Math.min(data.max_streak / 30 * 100, 100)}%; background:var(--neon-yellow);"></div></div>
        </div>
    `;
}

function renderCharacterCards(data) {
    const container = document.getElementById('character-cards');
    const me = data.me;
    const them = data.them;

    function makeCard(sender, cssClass, color) {
        const initial = sender === 'Me' ? 'ME' : sender.charAt(0).toUpperCase();
        const initiative = data.initiative[sender] || 0;
        const avgResp = data.avg_response_seconds[sender];
        const avgLen = data.avg_message_length[sender] || 0;
        const msgsDay = data.msgs_per_day[sender] || 0;
        const questions = data.questions_asked[sender] || 0;
        const emojis = data.emoji_count[sender] || 0;
        const charClass = data.character_class[sender] || 'Unknown';
        const level = data.level[sender] || 1;
        const totalMsgs = data.message_count[sender] || 0;

        // Normalize values for bars (0-100)
        const initiativeBar = initiative;
        const speedBar = avgResp ? Math.max(0, 100 - (avgResp / 36)) : 50; // Lower is better
        const lengthBar = Math.min(avgLen / 20 * 100, 100);
        const activityBar = Math.min(msgsDay / 10 * 100, 100);

        return `
            <div class="character-card ${cssClass}">
                <div class="character-header">
                    <div class="avatar">${initial}</div>
                    <div>
                        <div class="character-name">${sender}</div>
                        <div class="character-class">${charClass}</div>
                        <div class="character-level">LVL ${level} &middot; ${totalMsgs} msgs</div>
                    </div>
                </div>
                <div class="stat-bar-container">
                    <div class="stat-bar-label"><span>Initiative</span><span>${initiative}%</span></div>
                    <div class="stat-bar"><div class="stat-bar-fill ${color}" style="width:${initiativeBar}%"></div></div>
                </div>
                <div class="stat-bar-container">
                    <div class="stat-bar-label"><span>Response Speed</span><span>${formatTime(avgResp)}</span></div>
                    <div class="stat-bar"><div class="stat-bar-fill ${color}" style="width:${speedBar}%"></div></div>
                </div>
                <div class="stat-bar-container">
                    <div class="stat-bar-label"><span>Message Length</span><span>${avgLen} words</span></div>
                    <div class="stat-bar"><div class="stat-bar-fill ${color}" style="width:${lengthBar}%"></div></div>
                </div>
                <div class="stat-bar-container">
                    <div class="stat-bar-label"><span>Activity</span><span>${msgsDay}/day</span></div>
                    <div class="stat-bar"><div class="stat-bar-fill ${color}" style="width:${activityBar}%"></div></div>
                </div>
            </div>
        `;
    }

    container.innerHTML = makeCard(me, 'me', 'cyan') + makeCard(them, 'her', 'pink');

    // Animate bars
    setTimeout(() => {
        document.querySelectorAll('.stat-bar-fill').forEach(bar => {
            const w = bar.style.width;
            bar.style.width = '0%';
            requestAnimationFrame(() => { bar.style.width = w; });
        });
    }, 100);
}

function renderAchievements(data) {
    const container = document.getElementById('achievements');
    if (!data.achievements || data.achievements.length === 0) {
        container.innerHTML = '<span style="color:var(--text-dim); font-size:0.9rem;">No achievements yet. Keep texting!</span>';
        return;
    }
    container.innerHTML = data.achievements.map(a =>
        `<div class="achievement"><span>${a.icon}</span> ${a.name}</div>`
    ).join('');
}

function renderStatsGrid(data) {
    const grid = document.getElementById('stats-grid');
    const me = data.me;
    const them = data.them;

    const cards = [
        { label: 'Total Convos', value: data.total_conversations, color: 'cyan' },
        { label: `${them}'s Questions`, value: data.questions_asked[them] || 0, color: 'pink' },
        { label: 'My Questions', value: data.questions_asked[me] || 0, color: 'cyan' },
        { label: `${them}'s Emojis`, value: data.emoji_count[them] || 0, color: 'pink' },
        { label: 'My Emojis', value: data.emoji_count[me] || 0, color: 'cyan' },
        { label: 'My Double Texts', value: data.double_texts[me] || 0, color: 'yellow' },
        { label: `${them}'s Double Texts`, value: data.double_texts[them] || 0, color: 'yellow' },
        { label: 'Late Night Texts', value: (data.late_night_texts[me] || 0) + (data.late_night_texts[them] || 0), color: 'purple' },
    ];

    grid.innerHTML = cards.map(c => `
        <div class="stat-card">
            <div class="stat-number" style="color:var(--neon-${c.color})">${c.value.toLocaleString()}</div>
            <div class="stat-label">${c.label}</div>
        </div>
    `).join('');
}

function renderTrendChart(data) {
    if (!data.weekly_trends || data.weekly_trends.length === 0) return;

    const ctx = document.getElementById('trend-chart').getContext('2d');
    const weeks = data.weekly_trends;
    const me = data.me;
    const them = data.them;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: weeks.map(w => w._week),
            datasets: [
                {
                    label: me,
                    data: weeks.map(w => w[me] || 0),
                    borderColor: '#00f0ff',
                    backgroundColor: 'rgba(0, 240, 255, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                },
                {
                    label: them,
                    data: weeks.map(w => w[them] || 0),
                    borderColor: '#ff00aa',
                    backgroundColor: 'rgba(255, 0, 170, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: true,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: { color: '#8888aa', font: { family: 'Inter' } }
                }
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

async function loadAnalysis() {
    try {
        const res = await fetch(withContact('/api/analysis'));
        const data = await res.json();
        if (!data.error) {
            analysisData = data;
            renderAnalysis(data);
            document.getElementById('analyze-btn').style.display = 'none';
            document.getElementById('refresh-btn').style.display = 'inline-block';
        }
    } catch (e) {
        // No cached analysis - that's fine
    }
}

let progressInterval = null;

function startProgressPolling() {
    const loadingEl = document.getElementById('analysis-loading');
    showThinkingSidebar();
    progressInterval = setInterval(async () => {
        try {
            const res = await fetch(withContact('/api/analysis/progress'));
            const p = await res.json();
            if (p.step && p.step !== 'idle') {
                loadingEl.innerHTML = `
                    <div style="text-align:center; width:100%;">
                        <div class="loading-spinner" style="margin:0 auto 12px;"></div>
                        <div style="color:var(--neon-cyan); font-family:var(--font-display); font-size:0.75rem; letter-spacing:2px; margin-bottom:8px;">${p.step.toUpperCase()}</div>
                        <div style="color:var(--text-secondary); font-size:0.9rem; margin-bottom:12px;">${p.detail}</div>
                        <div class="progress-bar-outer"><div class="progress-bar-inner" style="width:${p.pct}%"></div></div>
                        <div style="color:var(--text-dim); font-size:0.8rem; margin-top:4px;">${p.pct}%</div>
                    </div>`;
                updateThinkingSidebar(p);
            }
            if (p.step === 'done') {
                stopProgressPolling();
            }
        } catch (e) {
            // Silent
        }
    }, 1500);
}

function stopProgressPolling() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

async function runAnalysis() {
    const btn = document.getElementById('analyze-btn');
    btn.disabled = true;
    btn.textContent = 'ANALYZING...';
    document.getElementById('analysis-loading').style.display = 'flex';
    startProgressPolling();

    try {
        const res = await fetch(withContact('/api/analysis'));
        const data = await res.json();
        if (!data.error) {
            analysisData = data;
            renderAnalysis(data);
            btn.style.display = 'none';
            document.getElementById('refresh-btn').style.display = 'inline-block';
        }
    } catch (e) {
        btn.textContent = 'ERROR - RETRY';
    } finally {
        stopProgressPolling();
        btn.disabled = false;
        document.getElementById('analysis-loading').style.display = 'none';
    }
}

function toggleFeedbackInput() {
    const container = document.getElementById('feedback-container');
    if (container.style.display === 'none' || !container.style.display) {
        container.style.display = 'block';
        container.querySelector('textarea').focus();
    } else {
        container.style.display = 'none';
    }
}

async function refreshAnalysis() {
    const btn = document.getElementById('refresh-btn');
    const feedbackInput = document.getElementById('analysis-feedback');
    const feedback = feedbackInput ? feedbackInput.value.trim() : '';

    btn.disabled = true;
    btn.textContent = 'REFRESHING...';
    document.getElementById('analysis-loading').style.display = 'flex';
    document.getElementById('feedback-container').style.display = 'none';
    startProgressPolling();

    try {
        const res = await fetch(withContact('/api/analysis/refresh'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ feedback }),
        });
        const data = await res.json();
        if (!data.error) {
            analysisData = data;
            renderAnalysis(data);
        }
        if (feedbackInput) feedbackInput.value = '';
    } catch (e) {
        // Error handling
    } finally {
        stopProgressPolling();
        btn.disabled = false;
        btn.textContent = 'REFRESH ANALYSIS';
        document.getElementById('analysis-loading').style.display = 'none';
    }
}

function renderAnalysis(data) {
    document.getElementById('analysis-content').style.display = 'block';

    // Interest type (romantic vs platonic)
    const it = data.interest_type;
    if (it) {
        const hud = document.getElementById('hud');
        hud.querySelectorAll('.hud-item-interest').forEach(el => el.remove());
        const romanticPct = it.romantic_score || 0;
        const romanticColor = romanticPct >= 70 ? 'pink' : romanticPct >= 40 ? 'purple' : 'cyan';
        const classLabel = (it.classification || 'unknown').replace(/_/g, ' ').toUpperCase();
        hud.innerHTML += `
            <div class="hud-item hud-item-interest">
                <div class="hud-label">VIBE CHECK</div>
                <div class="hud-value ${romanticColor}" style="font-size:1.4rem;">${classLabel}</div>
                <div class="hud-bar"><div class="hud-bar-fill" style="width:${romanticPct}%; background:var(--neon-${romanticColor});"></div></div>
                <div class="hud-reasoning">${romanticPct}% romantic energy${it.reasoning ? ' — ' + it.reasoning : ''}</div>
            </div>
        `;
    }

    // Update HUD with relationship score
    if (data.relationship_score) {
        const hud = document.getElementById('hud');
        // Remove previously added analysis HUD items to avoid duplicates
        hud.querySelectorAll('.hud-item-analysis').forEach(el => el.remove());
        const scoreColor = data.relationship_score >= 70 ? 'green' : data.relationship_score >= 40 ? 'yellow' : 'pink';
        hud.innerHTML += `
            <div class="hud-item hud-item-analysis">
                <div class="hud-label">RELATIONSHIP SCORE</div>
                <div class="hud-value ${scoreColor}">${data.relationship_score}</div>
                <div class="hud-bar"><div class="hud-bar-fill" style="width:${data.relationship_score}%; background:var(--neon-${scoreColor});"></div></div>
                ${data.relationship_reasoning ? `<div class="hud-reasoning">${data.relationship_reasoning}</div>` : ''}
            </div>
            <div class="hud-item hud-item-analysis">
                <div class="hud-label">AFFECTION LEVEL</div>
                <div class="hud-value pink">${data.affection_level || '?'}</div>
                <div class="hud-bar"><div class="hud-bar-fill" style="width:${data.affection_level || 0}%; background:var(--neon-pink);"></div></div>
                ${data.affection_reasoning ? `<div class="hud-reasoning">${data.affection_reasoning}</div>` : ''}
            </div>
        `;
    }

    // Flags
    const flagsContainer = document.getElementById('flags');
    const greenFlags = (data.green_flags || []).map(f =>
        `<div class="flag-item"><span class="flag-icon green">&#10003;</span><span>${f}</span></div>`
    ).join('');
    const redFlags = (data.red_flags || []).map(f =>
        `<div class="flag-item"><span class="flag-icon red">&#9888;</span><span>${f}</span></div>`
    ).join('');

    flagsContainer.innerHTML = `
        <div class="flags-panel green">
            <div class="card-title" style="color:var(--neon-green);">GREEN FLAGS</div>
            ${greenFlags || '<div style="color:var(--text-dim);">None detected yet</div>'}
        </div>
        <div class="flags-panel red">
            <div class="card-title" style="color:var(--neon-red);">RED FLAGS</div>
            ${redFlags || '<div style="color:var(--text-dim);">None detected</div>'}
        </div>
    `;

    // Attachment styles
    const attachPanel = document.getElementById('attachment-styles');
    const as = data.attachment_styles;
    if (as && attachPanel) {
        const styleColors = {
            'secure': 'green',
            'anxious-preoccupied': 'pink',
            'dismissive-avoidant': 'cyan',
            'fearful-avoidant': 'yellow',
        };
        const theirColor = styleColors[as.their_style] || 'purple';
        const meColor = styleColors[as.me_style] || 'purple';
        const theirBehaviors = (as.their_behaviors || []).map(b => `<li>${b}</li>`).join('');
        const meBehaviors = (as.me_behaviors || []).map(b => `<li>${b}</li>`).join('');

        attachPanel.innerHTML = `
            <div class="gameplan-grid">
                <div class="gameplan-card" style="border-color: var(--neon-${theirColor});">
                    <div class="card-title" style="color:var(--neon-${theirColor});">THEIR STYLE: ${(as.their_style || 'unknown').toUpperCase()}</div>
                    <div class="attachment-confidence">Confidence: ${as.their_style_confidence || '?'}%</div>
                    <div class="gameplan-text" style="margin:12px 0;">${as.their_reasoning || ''}</div>
                    <ul class="gameplan-list" style="margin-top:8px;">${theirBehaviors}</ul>
                </div>
                <div class="gameplan-card" style="border-color: var(--neon-${meColor});">
                    <div class="card-title" style="color:var(--neon-${meColor});">YOUR STYLE: ${(as.me_style || 'unknown').toUpperCase()}</div>
                    <div class="attachment-confidence">Confidence: ${as.me_style_confidence || '?'}%</div>
                    <div class="gameplan-text" style="margin:12px 0;">${as.me_reasoning || ''}</div>
                    <ul class="gameplan-list" style="margin-top:8px;">${meBehaviors}</ul>
                </div>
            </div>
            ${as.compatibility_note ? `
            <div class="gameplan-card" style="border-color: rgba(180, 0, 255, 0.2); margin-top:-8px;">
                <div class="card-title" style="color:var(--neon-purple);">COMPATIBILITY</div>
                <div class="gameplan-text">${as.compatibility_note}</div>
            </div>` : ''}
        `;
    }

    // Intel grid
    const intelContainer = document.getElementById('intel');
    const unresolved = (data.unresolved_topics || []).map(t =>
        `<div class="intel-item"><span class="intel-icon">&#8635;</span><span>${t}</span></div>`
    ).join('');
    const starters = (data.conversation_starters || []).map(t =>
        `<div class="intel-item"><span class="intel-icon">&#9729;</span><span>${t}</span></div>`
    ).join('');
    const remember = (data.things_to_remember || []).map(t =>
        `<div class="intel-item"><span class="intel-icon">&#9733;</span><span>${t}</span></div>`
    ).join('');

    intelContainer.innerHTML = `
        <div class="intel-panel unresolved">
            <div class="card-title" style="color:var(--neon-yellow);">UNRESOLVED TOPICS</div>
            ${unresolved || '<div style="color:var(--text-dim);">All caught up</div>'}
        </div>
        <div class="intel-panel starters">
            <div class="card-title" style="color:var(--neon-cyan);">CONVERSATION STARTERS</div>
            ${starters || '<div style="color:var(--text-dim);">No suggestions yet</div>'}
        </div>
        <div class="intel-panel remember">
            <div class="card-title" style="color:var(--neon-pink);">THINGS TO REMEMBER</div>
            ${remember || '<div style="color:var(--text-dim);">Nothing yet</div>'}
        </div>
    `;

    // Game Plan — expanded with all sections
    const gamePlan = document.getElementById('game-plan');
    const gp = data.game_plan;
    if (gp) {
        gamePlan.innerHTML = renderExpandedGamePlan(gp);
    } else {
        gamePlan.innerHTML = '';
    }

    // Moves
    const movesPanel = document.getElementById('moves');
    const moves = (data.moves_to_make || []).map((m, i) =>
        `<div class="advice-item"><span class="advice-marker" style="color:var(--neon-green); background:rgba(0,255,136,0.1);">MOVE ${i + 1}</span><span>${m}</span></div>`
    ).join('');
    movesPanel.innerHTML = moves || '<div style="color:var(--text-dim);">No moves generated</div>';

    // Quests
    const advicePanel = document.getElementById('advice');
    const quests = (data.quests || data.advice || []).map((q, i) =>
        `<div class="advice-item"><span class="advice-marker">QUEST ${i + 1}</span><span>${q}</span></div>`
    ).join('');
    advicePanel.innerHTML = quests || '<div style="color:var(--text-dim);">No quests generated</div>';

    // Summary
    if (data.summary) {
        advicePanel.innerHTML += `
            <div style="margin-top:16px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.05); color:var(--text-secondary); font-style:italic;">
                ${data.summary}
            </div>
        `;
    }
}

function renderExpandedGamePlan(gp) {
    // Handle both old flat format and new nested format
    const texting = gp.texting || gp;
    const inPerson = gp.in_person || {};
    const mental = gp.mental || {};
    const dates = gp.dates || {};
    const yourNeeds = gp.your_needs || {};

    // Texting section
    const doList = (texting.do || []).map(d => `<li>${d}</li>`).join('');
    const dontList = (texting.dont || []).map(d => `<li>${d}</li>`).join('');
    const timeline = (texting.timeline || []).map(t =>
        `<div class="timeline-item">
            <span class="timeline-day">${t.day}</span>
            <span class="timeline-action">${t.action}</span>
        </div>`
    ).join('');

    // Example texts (click to copy)
    const exampleTexts = (texting.example_texts || []).map(t =>
        `<div class="example-text-item" onclick="copyText(this, '${t.replace(/'/g, "\\'").replace(/"/g, '&quot;')}')">"${t}"</div>`
    ).join('');

    // In-person tips
    const inPersonTips = (inPerson.tips || []).map(t =>
        `<li>${t}</li>`
    ).join('');

    // Date ideas
    const futureIdeas = (dates.future_ideas || []).map(d =>
        `<li>${d}</li>`
    ).join('');

    // Boundaries
    const boundaries = (yourNeeds.boundaries || []).map(b =>
        `<li>${b}</li>`
    ).join('');

    return `
        <!-- TEXTING STRATEGY -->
        <div class="gp-section-header">TEXTING STRATEGY</div>
        <div class="gameplan-grid">
            <div class="gameplan-card">
                <div class="card-title" style="color:var(--neon-cyan);">FREQUENCY</div>
                <div class="gameplan-text">${texting.frequency || texting.texting_frequency || 'No recommendation'}</div>
            </div>
            <div class="gameplan-card">
                <div class="card-title" style="color:var(--neon-pink);">TONE & ENERGY</div>
                <div class="gameplan-text">${texting.tone || 'No recommendation'}</div>
            </div>
        </div>
        <div class="gameplan-grid">
            <div class="gameplan-card do">
                <div class="card-title" style="color:var(--neon-green);">DO THIS</div>
                <ul class="gameplan-list green">${doList || '<li>No suggestions</li>'}</ul>
            </div>
            <div class="gameplan-card dont">
                <div class="card-title" style="color:var(--neon-red);">DON'T DO THIS</div>
                <ul class="gameplan-list red">${dontList || '<li>No warnings</li>'}</ul>
            </div>
        </div>
        ${exampleTexts ? `
        <div class="gameplan-card example-texts-card">
            <div class="card-title" style="color:var(--neon-purple);">EXAMPLE TEXTS TO SEND</div>
            <div class="example-texts-list">${exampleTexts}</div>
        </div>` : ''}
        <div class="gameplan-card timeline-card">
            <div class="card-title" style="color:var(--neon-yellow);">THIS WEEK'S TIMELINE</div>
            <div class="timeline">${timeline || '<div style="color:var(--text-dim);">No timeline</div>'}</div>
        </div>

        <!-- IN PERSON -->
        ${(inPerson.how_to_act || inPersonTips) ? `
        <div class="gp-section-header">IN PERSON</div>
        <div class="gameplan-grid">
            <div class="gameplan-card" style="border-color: rgba(0, 255, 136, 0.2);">
                <div class="card-title" style="color:var(--neon-green);">HOW TO ACT</div>
                <div class="gameplan-text">${inPerson.how_to_act || 'No recommendation'}</div>
            </div>
            <div class="gameplan-card" style="border-color: rgba(0, 255, 136, 0.2);">
                <div class="card-title" style="color:var(--neon-green);">IRL TIPS</div>
                <ul class="gameplan-list green">${inPersonTips || '<li>No tips</li>'}</ul>
            </div>
        </div>` : ''}

        <!-- MINDSET -->
        ${(mental.mindset || mental.confidence || mental.frame) ? `
        <div class="gp-section-header">MINDSET</div>
        <div class="gameplan-grid">
            <div class="gameplan-card" style="border-color: rgba(180, 0, 255, 0.2);">
                <div class="card-title" style="color:var(--neon-purple);">MINDSET</div>
                <div class="gameplan-text">${mental.mindset || 'No suggestion'}</div>
            </div>
            <div class="gameplan-card" style="border-color: rgba(180, 0, 255, 0.2);">
                <div class="card-title" style="color:var(--neon-purple);">CONFIDENCE</div>
                <div class="gameplan-text">${mental.confidence || 'No suggestion'}</div>
            </div>
        </div>
        ${mental.frame ? `
        <div class="gameplan-card" style="border-color: rgba(180, 0, 255, 0.2); margin-bottom: 24px;">
            <div class="card-title" style="color:var(--neon-purple);">FRAME</div>
            <div class="gameplan-text">${mental.frame}</div>
        </div>` : ''}
        ` : ''}

        <!-- DATE PLANNING -->
        ${(dates.next_date || futureIdeas) ? `
        <div class="gp-section-header">DATE PLANNING</div>
        <div class="date-plan-card">
            <div class="card-title" style="color:var(--neon-pink);">NEXT DATE</div>
            <div class="gameplan-text" style="font-size:1.05rem;">${dates.next_date || 'No date planned'}</div>
            ${futureIdeas ? `
            <div class="card-title" style="color:var(--neon-pink); margin-top:20px;">FUTURE IDEAS</div>
            <ul class="gameplan-list pink">${futureIdeas}</ul>` : ''}
        </div>` : ''}

        <!-- YOUR NEEDS -->
        ${(yourNeeds.what_you_need || yourNeeds.how_to_communicate || boundaries) ? `
        <div class="gp-section-header">YOUR NEEDS</div>
        <div class="needs-panel">
            ${yourNeeds.what_you_need ? `
            <div class="needs-section">
                <div class="card-title" style="color:var(--neon-yellow);">WHAT YOU NEED</div>
                <div class="gameplan-text">${yourNeeds.what_you_need}</div>
            </div>` : ''}
            ${yourNeeds.how_to_communicate ? `
            <div class="needs-section">
                <div class="card-title" style="color:var(--neon-yellow);">HOW TO COMMUNICATE IT</div>
                <div class="gameplan-text">${yourNeeds.how_to_communicate}</div>
            </div>` : ''}
            ${boundaries ? `
            <div class="needs-section">
                <div class="card-title" style="color:var(--neon-yellow);">BOUNDARIES TO SET</div>
                <ul class="gameplan-list yellow">${boundaries}</ul>
            </div>` : ''}
        </div>` : ''}
    `;
}

async function getNextMove() {
    const btn = document.getElementById('next-move-btn');
    const panel = document.getElementById('next-move-panel');
    btn.disabled = true;
    btn.textContent = 'THINKING...';
    panel.innerHTML = '<div class="loading"><div class="loading-spinner"></div><span>Reading the vibe...</span></div>';

    try {
        const res = await fetch(withContact('/api/next-move'), { method: 'POST' });
        const data = await res.json();

        if (data.error) {
            panel.innerHTML = `<div style="color:var(--neon-red); text-align:center; padding:20px;">${data.error}</div>`;
            btn.textContent = "WHAT'S MY MOVE?";
            btn.disabled = false;
            return;
        }

        let html = '';

        // Situation + vibe check
        if (data.situation) {
            html += `<div class="next-move-situation">${data.situation}</div>`;
        }

        // Moves
        if (data.moves && data.moves.length > 0) {
            html += '<div class="next-move-cards">';
            data.moves.forEach(move => {
                const actionColors = {
                    'send_now': 'green',
                    'send_later': 'yellow',
                    'wait': 'cyan',
                    'in_person': 'pink'
                };
                const actionLabels = {
                    'send_now': 'SEND NOW',
                    'send_later': 'SEND LATER',
                    'wait': 'WAIT',
                    'in_person': 'IN PERSON'
                };
                const color = actionColors[move.action] || 'cyan';
                const label = actionLabels[move.action] || move.action.toUpperCase();

                html += `<div class="next-move-card">
                    <div class="move-header">
                        <span class="move-timing ${color}">${move.timing || label}</span>
                        <span class="move-action-label">${label}</span>
                    </div>`;

                if (move.message) {
                    const escaped = move.message.replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    html += `<div class="move-message" onclick="copyText(this, '${escaped}')">"${move.message}"</div>`;
                }

                if (move.reasoning) {
                    html += `<div class="move-reasoning">${move.reasoning}</div>`;
                }

                html += '</div>';
            });
            html += '</div>';
        }

        // Vibe check
        if (data.vibe_check) {
            html += `<div class="next-move-vibe">${data.vibe_check}</div>`;
        }

        panel.innerHTML = html;
        btn.textContent = "REFRESH MY MOVE";
    } catch (e) {
        panel.innerHTML = `<div style="color:var(--neon-red); text-align:center; padding:20px;">Error: ${e.message}</div>`;
        btn.textContent = "WHAT'S MY MOVE?";
    } finally {
        btn.disabled = false;
    }
}

async function setMyAttachmentStyle() {
    const select = document.getElementById('my-attachment-style');
    const style = select.value;
    if (!style || !getSelectedContact()) return;

    try {
        await fetch(withContact('/api/attachment-style'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ style }),
        });
        select.style.borderColor = 'var(--neon-green)';
        setTimeout(() => { select.style.borderColor = ''; }, 1500);
    } catch (e) {
        // Silent fail
    }
}

async function loadMyAttachmentStyle() {
    if (!getSelectedContact()) return;
    try {
        const res = await fetch(withContact('/api/attachment-style'));
        const data = await res.json();
        if (data.style) {
            document.getElementById('my-attachment-style').value = data.style;
        }
    } catch (e) {
        // Silent
    }
}

async function setGender() {
    const select = document.getElementById('contact-gender');
    const gender = select.value;
    if (!getSelectedContact()) return;

    try {
        await fetch(withContact('/api/gender'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gender }),
        });
        select.style.borderColor = 'var(--neon-green)';
        setTimeout(() => { select.style.borderColor = ''; }, 1500);
    } catch (e) { /* Silent */ }
}

async function loadGender() {
    if (!getSelectedContact()) return;
    try {
        const res = await fetch(withContact('/api/gender'));
        const data = await res.json();
        if (data.gender) {
            document.getElementById('contact-gender').value = data.gender;
        }
    } catch (e) { /* Silent */ }
}

async function setCategory() {
    const select = document.getElementById('contact-category');
    const category = select.value;
    if (!getSelectedContact()) return;

    try {
        await fetch(withContact('/api/category'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category }),
        });
        select.style.borderColor = 'var(--neon-green)';
        setTimeout(() => { select.style.borderColor = ''; }, 1500);
    } catch (e) { /* Silent */ }
}

async function loadCategory() {
    if (!getSelectedContact()) return;
    try {
        const res = await fetch(withContact('/api/category'));
        const data = await res.json();
        if (data.category) {
            document.getElementById('contact-category').value = data.category;
        }
    } catch (e) { /* Silent */ }
}

async function saveContextNotes() {
    const textarea = document.getElementById('context-notes');
    const notes = textarea.value.trim();
    if (!getSelectedContact()) return;

    const btn = textarea.nextElementSibling;
    btn.textContent = 'SAVING...';
    try {
        await fetch(withContact('/api/context-notes'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notes }),
        });
        btn.textContent = 'SAVED!';
        btn.style.borderColor = 'var(--neon-green)';
        btn.style.color = 'var(--neon-green)';
        setTimeout(() => {
            btn.textContent = 'SAVE NOTES';
            btn.style.borderColor = '';
            btn.style.color = '';
        }, 2000);
    } catch (e) {
        btn.textContent = 'ERROR';
        setTimeout(() => { btn.textContent = 'SAVE NOTES'; }, 2000);
    }
}

async function loadContextNotes() {
    if (!getSelectedContact()) return;
    try {
        const res = await fetch(withContact('/api/context-notes'));
        const data = await res.json();
        if (data.notes) {
            document.getElementById('context-notes').value = data.notes;
        }
    } catch (e) { /* Silent */ }
}

async function checkUserName() {
    const name = getUserName();
    if (!name || name === 'Me') {
        const input = prompt('Welcome! What\'s your name?');
        if (input && input.trim()) {
            const trimmed = input.trim();
            localStorage.setItem('userName', trimmed);
            try {
                await fetch('/api/profile', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: trimmed }),
                });
                document.getElementById('app-brand').textContent = trimmed.toUpperCase() + "'S CHATBOT";
            } catch (e) { /* Silent */ }
        }
    }
}

function copyText(el, text) {
    navigator.clipboard.writeText(text).then(() => {
        el.style.borderColor = 'var(--neon-green)';
        el.style.boxShadow = '0 0 10px rgba(0, 255, 136, 0.3)';
        const orig = el.innerHTML;
        el.innerHTML = '<span style="color:var(--neon-green); font-style:normal;">Copied!</span>';
        setTimeout(() => {
            el.innerHTML = orig;
            el.style.borderColor = '';
            el.style.boxShadow = '';
        }, 1500);
    });
}

// === Thinking Sidebar ===

function showThinkingSidebar() {
    const sidebar = document.getElementById('thinking-sidebar');
    if (!sidebar) return;
    thinkingLogCount = 0;
    sidebarDismissed = false;
    document.getElementById('thinking-log').innerHTML = '';
    document.getElementById('thinking-step-label').textContent = 'INITIALIZING';
    document.getElementById('thinking-step-detail').textContent = 'Waiting to start...';
    document.getElementById('thinking-progress-fill').style.width = '0%';
    document.getElementById('thinking-pct').textContent = '0%';
    sidebar.classList.remove('closing', 'complete');
    sidebar.classList.add('open');
}

function hideThinkingSidebar() {
    const sidebar = document.getElementById('thinking-sidebar');
    if (!sidebar) return;
    sidebar.classList.add('closing');
    setTimeout(() => {
        sidebar.classList.remove('open', 'closing');
    }, 400);
}

function dismissThinkingSidebar() {
    sidebarDismissed = true;
    hideThinkingSidebar();
}

function updateThinkingSidebar(p) {
    if (sidebarDismissed) return;
    const sidebar = document.getElementById('thinking-sidebar');
    if (!sidebar || !sidebar.classList.contains('open')) return;

    // Update step/detail/progress
    const stepLabel = document.getElementById('thinking-step-label');
    const stepDetail = document.getElementById('thinking-step-detail');
    const progressFill = document.getElementById('thinking-progress-fill');
    const pctEl = document.getElementById('thinking-pct');

    if (p.step && p.step !== 'idle') {
        stepLabel.textContent = p.step.toUpperCase();
        stepDetail.textContent = p.detail || '';
        progressFill.style.width = p.pct + '%';
        pctEl.textContent = p.pct + '%';
    }

    // Append only new log entries
    const log = p.log || [];
    if (log.length > thinkingLogCount) {
        const logContainer = document.getElementById('thinking-log');
        for (let i = thinkingLogCount; i < log.length; i++) {
            const entry = log[i];
            const el = document.createElement('div');
            el.className = 'thinking-log-entry ' + (entry.type === 'insight' ? 'insight' : 'status');
            el.innerHTML = `<span class="thinking-log-ts">${entry.ts}</span><span class="thinking-log-text">${entry.text}</span>`;
            logContainer.appendChild(el);
            // Trigger fade-in
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    el.classList.add('visible');
                });
            });
        }
        thinkingLogCount = log.length;
        // Auto-scroll
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Completion state
    if (p.step === 'done') {
        sidebar.classList.add('complete');
        stepLabel.textContent = 'COMPLETE';
        setTimeout(() => {
            if (!sidebarDismissed) {
                hideThinkingSidebar();
            }
        }, 3000);
    }
}

// Init on load
init();
loadMyAttachmentStyle();
loadGender();
loadCategory();
loadContextNotes();
checkUserName();
