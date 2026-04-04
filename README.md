# iMessage Relationship Analyzer

**I was down bad for a girl and built an entire AI-powered analytics platform to figure out if she liked me back.**

It started as a "let me just check our texting ratio real quick" and turned into a full-stack app with Claude-powered personality analysis, real-time coaching, attachment style detection, and copy-paste-ready texts. As one does.

> The answer was no btw.

---

### What it does in 10 seconds

Drop in your iMessage conversations. Get back a full relationship intelligence dashboard — interest scoring, green/red flags, attachment styles, a game plan with exact texts to send, and a "WHAT'S MY MOVE?" button that reads the vibe and tells you what to do right now.

---

## Demo

*Screenshots removed for privacy. Run the app locally to see the full UI.*

---

## Features

### Core Analysis Engine
- **Chunked conversation analysis** — splits conversations into windows, analyzes each with Claude, then synthesizes a final comprehensive report
- **Relationship scoring** (0-100) with cited reasoning from actual messages
- **Interest classification** — romantic / platonic / flirty_undefined / situationship / early_stage
- **Attachment style detection** for both parties with confidence scores and compatibility notes
- **Green/red flag extraction** grounded in specific message patterns

### "WHAT SHOULD I DO?" Real-Time Coaching
- Reads your last 30 messages and current analysis
- Returns structured moves: `send_now`, `send_later`, `wait`, `in_person`
- Each move includes timing, a ready-to-copy message, and reasoning
- Factors in time of day, conversation momentum, and power dynamics

### Game Plan Generator
- **Texting strategy** — frequency, tone, do's/don'ts, weekly timeline
- **Example texts** — copy-paste messages based on actual conversation context
- **In-person tips** — body language, energy, specific advice
- **Date planning** — next date idea with word-for-word ask text
- **Your needs** — what you need from this connection and how to communicate it

### Multi-Contact Intelligence
- Analyze unlimited contacts with independent analysis pipelines
- **7 relationship categories** with tailored prompts — romantic interest, casual, close friend, new friend, coworker, family, ex
- **Gender/pronoun support** — set on import or in settings, injected into all AI prompts
- **Context notes** — free-text field to give the AI background ("we hooked up last weekend", "she just got out of a relationship")

### MY PROFILE — Global Personality Analysis
- Aggregates your texting patterns across ALL contacts
- Stats: messages/day, avg response time, emoji rate, initiative rate, double texts, late night count
- Claude-generated personality profile: title, strengths, growth areas, "texting zodiac"
- Busiest hours chart, character class assignment, level system

### Clone Chat
- AI that mimics the other person's texting style
- Built from their actual message patterns — vocabulary, emoji usage, response length, tone

### More
- **Insight Engine** — ask any natural language question about your conversations ("does she text first more on weekends?")
- **Journal** — AI-generated reflection prompts based on recent messages, with free-writing
- **Analysis History** — track score changes over time, re-analyze with user feedback
- **Live thinking sidebar** — watch Claude's analysis process in real-time with a progress bar

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, SQLite |
| Frontend | Vanilla JS, Chart.js, Jinja2 templates |
| AI | Claude (via Claude Code CLI) |
| Message Import | imessage-exporter (Rust binary), file upload |
| Styling | Custom CSS — cyberpunk dark theme with Space Grotesk / Inter / JetBrains Mono |

**~7,300 lines of code** across 11 source files. No React, no build step, no dependencies you don't need.

---

## Architecture

```
iMessage DB ──> imessage-exporter ──> .txt files ──> parser.py ──> SQLite
                                                                     │
                                              ┌──────────────────────┤
                                              │                      │
                                         analyzer.py            compute_stats()
                                              │                      │
                                    Claude API (chunked)        Pure Python
                                              │                      │
                                              └──────┬───────────────┘
                                                     │
                                                  app.py (FastAPI)
                                                     │
                                              ┌──────┼──────┐
                                              │      │      │
                                          dashboard  chat  profile ...
```

### Key Design Decisions

**Chunked analysis over single-prompt** — Conversations can be 10K+ messages. Instead of truncating, the analyzer splits into 50-message windows, analyzes a representative subset (first, middle, last chunks), then runs a synthesis pass. This preserves early-relationship vs. current-state context.

**Synchronous Claude calls in async server** — Analysis endpoints use `def` (not `async def`) so FastAPI runs them in a threadpool. This avoids blocking the event loop while Claude thinks for 30-60 seconds, while keeping the code simple (no async Claude client needed).

**Category-aware prompt system** — Each relationship category (romantic, friend, coworker, etc.) gets a completely different system prompt with tailored role, focus areas, tone, and which sections to include. A "romantic interest" analysis includes date planning and escalation tips; a "coworker" analysis focuses on professional rapport.

**SQLite with WAL mode** — Write-ahead logging for concurrent reads during analysis. No ORM — raw SQL for simplicity and control.

**No framework for frontend** — Vanilla JS with fetch calls. The UI is complex (dashboards, charts, modals, sidebars) but doesn't need React's overhead. Each page is a Jinja2 template with a dedicated JS file.

---

## Quick Start

```bash
# Clone and double-click the launcher
git clone <your-repo-url>
cd eric-chatbot

# Option A: One-click launcher (installs everything)
chmod +x start.command && open start.command

# Option B: Manual
pip3 install -r requirements.txt
python3 -m uvicorn app:app --port 8000
# Open http://localhost:8000
```

> Requires Claude Code CLI for AI features: `npm install -g @anthropic-ai/claude-code && claude auth login`

> iMessage import requires Full Disk Access for Terminal (System Settings > Privacy & Security > Full Disk Access)

---

## Project Structure

```
├── app.py                 # FastAPI routes and API endpoints
├── analyzer.py            # Claude analysis engine, stats computation, next-move coaching
├── database.py            # SQLite schema, migrations, CRUD operations
├── parser.py              # iMessage export parser with metadata computation
├── clone.py               # Clone chat — AI that mimics contact's texting style
├── claude_cli.py          # Claude Code CLI wrapper (JSON mode + streaming)
├── journal.py             # AI-generated reflection prompts
├── start.command           # One-click macOS launcher
├── static/
│   ├── css/style.css      # Cyberpunk dark theme (~2,300 lines)
│   └── js/
│       ├── dashboard.js   # Dashboard rendering, analysis, next-move UI
│       └── profile.js     # Global profile stats and personality analysis
└── templates/
    ├── base.html          # Nav, contact selector, add-contact modal
    ├── dashboard.html     # Main analysis dashboard
    ├── profile.html       # MY PROFILE — cross-contact personality analysis
    ├── chat.html          # Clone chat interface
    ├── insights.html      # Natural language Q&A
    ├── journal.html       # Reflection journal
    └── history.html       # Analysis history timeline
```

---

*Built with sleep deprivation, Claude, and an unreasonable amount of hope.*
