"""Conversation analysis: computed stats + Claude-powered insights."""

import json
from datetime import datetime, timedelta
from collections import Counter
from database import get_all_messages, get_all_messages_global, get_recent_messages, get_senders, save_analysis, get_analysis, get_journal_entries, get_contact_category, get_contact_gender, get_context_notes, get_user_name, save_analysis_history, get_contacts
from claude_cli import ask_claude, ask_claude_json

CONVO_GAP_SECONDS = 4 * 3600  # 4 hours = new conversation


def get_pronoun_instruction(gender: str) -> str:
    """Build a pronoun instruction string based on gender setting."""
    if gender == "he/him":
        return "Use he/him pronouns when referring to this contact."
    elif gender == "she/her":
        return "Use she/her pronouns when referring to this contact."
    elif gender == "they/them":
        return "Use they/them pronouns when referring to this contact."
    return ""

CATEGORY_LABELS = {
    "auto": "auto-detected relationship",
    "romantic_interest": "romantic interest / someone the user is dating or pursuing",
    "casual_interest": "casual / low-key connection — keeping it light and fun",
    "close_friend": "close friend",
    "new_friend": "new friend / acquaintance getting to know",
    "coworker": "coworker / professional relationship",
    "family_parent": "parent (family)",
    "family_sibling": "sibling (family)",
    "ex": "ex-partner",
    "other": "general contact",
}

def get_category_context(category: str, name: str = "the user") -> dict:
    """Return category-specific prompt tweaks."""
    if category in ("romantic_interest", "auto"):
        return {
            "role": "dating coach and wing-man",
            "focus": "romantic connection, flirting, escalation, date planning",
            "include_romantic": True,
            "include_dates": True,
            "include_physical": False,
            "tone_note": f"Hype {name} up. Be their wing-man. Advocate for their romantic needs.",
        }
    elif category == "casual_interest":
        return {
            "role": "social coach",
            "focus": "keeping things fun and light, maintaining attraction without over-investing, setting clear expectations",
            "include_romantic": True,
            "include_dates": True,
            "include_physical": False,
            "tone_note": f"Keep the vibe chill. Help {name} maintain a fun, low-pressure dynamic. Don't overthink it — just keep it smooth.",
        }
    elif category == "close_friend":
        return {
            "role": "friendship coach",
            "focus": "deepening the friendship, quality hangouts, being a better friend",
            "include_romantic": False,
            "include_dates": False,
            "include_physical": False,
            "tone_note": "Be supportive about maintaining and growing this friendship. Focus on shared interests and quality time.",
        }
    elif category == "new_friend":
        return {
            "role": "social skills coach",
            "focus": "building rapport, finding common ground, turning acquaintance into real friend",
            "include_romantic": False,
            "include_dates": False,
            "include_physical": False,
            "tone_note": f"Help {name} build this new connection naturally. Focus on finding shared interests and making plans.",
        }
    elif category == "coworker":
        return {
            "role": "professional relationship coach",
            "focus": "professional rapport, networking, appropriate boundaries, career building",
            "include_romantic": False,
            "include_dates": False,
            "include_physical": False,
            "tone_note": "Keep advice professional. Focus on building good working relationships and career networking.",
        }
    elif category in ("family_parent", "family_sibling"):
        label = "parent" if category == "family_parent" else "sibling"
        return {
            "role": "family relationship coach",
            "focus": f"healthy {label} relationship, communication, appreciation, setting boundaries when needed",
            "include_romantic": False,
            "include_dates": False,
            "include_physical": False,
            "tone_note": f"Be warm and supportive about the {label} relationship. Focus on communication and connection.",
        }
    elif category == "ex":
        return {
            "role": "post-breakup advisor",
            "focus": "healthy boundaries, emotional processing, moving forward, whether/how to maintain contact",
            "include_romantic": False,
            "include_dates": False,
            "include_physical": False,
            "tone_note": f"Be honest about whether this contact is healthy. Advocate for {name}'s emotional wellbeing above all.",
        }
    else:
        return {
            "role": "life coach",
            "focus": "improving this relationship based on what the conversation reveals",
            "include_romantic": False,
            "include_dates": False,
            "include_physical": False,
            "tone_note": "Be generally supportive and helpful.",
        }


def compute_stats(contact: str) -> dict:
    """Compute all stats from raw message data (no AI needed)."""
    messages = get_all_messages(contact)
    if not messages:
        return {"error": "No messages found. Parse your export first."}

    senders = get_senders(contact)
    me = "Me"
    them = next((s for s in senders if s != "Me"), senders[0] if senders else "Them")

    total = len(messages)
    by_sender = {s: [m for m in messages if m["sender"] == s] for s in senders}

    # --- Initiative: who starts conversations ---
    convos_started = Counter()
    prev_ts = None
    for msg in messages:
        ts = datetime.fromisoformat(msg["timestamp"])
        if prev_ts is None or (ts - prev_ts).total_seconds() > CONVO_GAP_SECONDS:
            convos_started[msg["sender"]] += 1
        prev_ts = ts

    total_convos = sum(convos_started.values()) or 1

    # --- Response Speed ---
    response_times = {s: [] for s in senders}
    for msg in messages:
        if msg["response_time_seconds"] is not None and msg["response_time_seconds"] < CONVO_GAP_SECONDS:
            response_times[msg["sender"]].append(msg["response_time_seconds"])

    avg_response = {}
    median_response = {}
    for s in senders:
        times = response_times[s]
        if times:
            avg_response[s] = sum(times) / len(times)
            sorted_times = sorted(times)
            mid = len(sorted_times) // 2
            median_response[s] = sorted_times[mid]
        else:
            avg_response[s] = None
            median_response[s] = None

    # --- Engagement ---
    avg_length = {}
    questions_asked = {}
    for s in senders:
        msgs = by_sender.get(s, [])
        if msgs:
            avg_length[s] = sum(m["word_count"] for m in msgs) / len(msgs)
            questions_asked[s] = sum(1 for m in msgs if m["has_question"])
        else:
            avg_length[s] = 0
            questions_asked[s] = 0

    # --- Consistency: messages per day ---
    if messages:
        first_ts = datetime.fromisoformat(messages[0]["timestamp"])
        last_ts = datetime.fromisoformat(messages[-1]["timestamp"])
        days = max((last_ts - first_ts).days, 1)
    else:
        days = 1

    msgs_per_day = {s: len(by_sender.get(s, [])) / days for s in senders}

    # --- Weekly message counts for trends ---
    weekly_counts = {}
    for msg in messages:
        ts = datetime.fromisoformat(msg["timestamp"])
        week = ts.strftime("%Y-W%W")
        if week not in weekly_counts:
            weekly_counts[week] = {s: 0 for s in senders}
            weekly_counts[week]["_week"] = week
        weekly_counts[week][msg["sender"]] = weekly_counts[week].get(msg["sender"], 0) + 1

    # --- Emoji stats ---
    emoji_count = {}
    for s in senders:
        emoji_count[s] = sum(m["has_emoji"] for m in by_sender.get(s, []))

    # --- Double texts (consecutive messages by same person) ---
    double_texts = Counter()
    for i in range(1, len(messages)):
        if messages[i]["sender"] == messages[i - 1]["sender"]:
            double_texts[messages[i]["sender"]] += 1

    # --- Streaks: consecutive days with messages ---
    msg_dates = set()
    for msg in messages:
        ts = datetime.fromisoformat(msg["timestamp"])
        msg_dates.add(ts.date())
    sorted_dates = sorted(msg_dates)
    max_streak = 0
    current_streak = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
    max_streak = max(max_streak, current_streak) if sorted_dates else 0

    # --- 3AM texter ---
    late_night = {s: 0 for s in senders}
    for msg in messages:
        ts = datetime.fromisoformat(msg["timestamp"])
        if 0 <= ts.hour < 5:
            late_night[msg["sender"]] += 1

    # --- Build character classes ---
    def get_class(sender):
        traits = []
        if convos_started.get(sender, 0) / total_convos > 0.6:
            traits.append("The Initiator")
        if emoji_count.get(sender, 0) > total * 0.2:
            traits.append("Emoji Royalty")
        if avg_response.get(sender) and avg_response[sender] > 1800:
            traits.append("The Late Replier")
        if avg_response.get(sender) and avg_response[sender] < 300:
            traits.append("Speed Demon")
        if avg_length.get(sender, 0) > 15:
            traits.append("The Novelist")
        if avg_length.get(sender, 0) < 5:
            traits.append("The Minimalist")
        if double_texts.get(sender, 0) > total * 0.1:
            traits.append("Double Texter")
        if late_night.get(sender, 0) > 10:
            traits.append("3AM Texter")
        return traits[0] if traits else "The Balanced One"

    # --- Level calculation ---
    def get_level(sender):
        msgs = len(by_sender.get(sender, []))
        return min(99, max(1, msgs // 50 + 1))

    # --- Achievements ---
    achievements = []
    if double_texts.get(me, 0) > 0:
        achievements.append({"name": "First Double Text", "icon": "💬"})
    if max_streak >= 7:
        achievements.append({"name": "7-Day Streak", "icon": "🔥"})
    if max_streak >= 30:
        achievements.append({"name": "30-Day Streak", "icon": "⚡"})
    if late_night.get(me, 0) > 0:
        achievements.append({"name": "3AM Texter", "icon": "🌙"})
    if total > 1000:
        achievements.append({"name": "1K Messages", "icon": "📱"})
    if total > 5000:
        achievements.append({"name": "5K Messages", "icon": "🏆"})
    if questions_asked.get(me, 0) > 50:
        achievements.append({"name": "Curious Mind", "icon": "❓"})

    return {
        "total_messages": total,
        "total_days": days,
        "total_conversations": sum(convos_started.values()),
        "max_streak": max_streak,
        "senders": senders,
        "me": me,
        "them": them,
        "initiative": {s: round(convos_started.get(s, 0) / total_convos * 100, 1) for s in senders},
        "avg_response_seconds": {s: round(avg_response[s], 1) if avg_response[s] else None for s in senders},
        "median_response_seconds": {s: round(median_response[s], 1) if median_response[s] else None for s in senders},
        "avg_message_length": {s: round(avg_length.get(s, 0), 1) for s in senders},
        "questions_asked": questions_asked,
        "msgs_per_day": {s: round(msgs_per_day.get(s, 0), 2) for s in senders},
        "emoji_count": emoji_count,
        "double_texts": double_texts,
        "late_night_texts": late_night,
        "message_count": {s: len(by_sender.get(s, [])) for s in senders},
        "character_class": {s: get_class(s) for s in senders},
        "level": {s: get_level(s) for s in senders},
        "achievements": achievements,
        "weekly_trends": sorted(weekly_counts.values(), key=lambda w: w.get("_week", "")),
    }


# Global progress tracker
_analysis_progress = {}

def get_progress(contact: str) -> dict:
    return _analysis_progress.get(contact, {"step": "idle", "detail": "", "pct": 0, "log": []})

def run_claude_analysis(contact: str, force_refresh=False, user_feedback: str = "") -> dict:
    """Run Claude-powered analysis on the conversation."""
    if not force_refresh:
        cached = get_analysis(contact, "full_analysis")
        if cached:
            return cached["result"]

    _log = []

    def progress(step, detail, pct, log_type="status"):
        ts = datetime.now().strftime("%H:%M:%S")
        _log.append({"ts": ts, "type": log_type, "text": detail})
        _analysis_progress[contact] = {"step": step, "detail": detail, "pct": pct, "log": list(_log)}

    progress("loading", "Loading messages...", 5)
    messages = get_all_messages(contact)
    if not messages:
        _analysis_progress.pop(contact, None)
        return {"error": "No messages found."}

    progress("stats", "Computing conversation stats...", 10)
    stats = compute_stats(contact)
    senders = stats["senders"]
    them = stats["them"]

    # Get user + category + gender context
    user_name = get_user_name()
    category = get_contact_category(contact)
    cat_ctx = get_category_context(category, user_name)
    cat_label = CATEGORY_LABELS.get(category, "contact")
    context_notes = get_context_notes(contact)
    gender = get_contact_gender(contact)
    pronoun_instruction = get_pronoun_instruction(gender)

    # Chunk messages into ~50 message windows
    chunk_size = 50
    chunks = [messages[i : i + chunk_size] for i in range(0, len(messages), chunk_size)]

    # Analyze a subset of chunks (first, middle, last few) to keep cost reasonable
    selected_chunks = []
    if len(chunks) <= 6:
        selected_chunks = chunks
    else:
        selected_chunks = [chunks[0], chunks[1]] + [chunks[len(chunks) // 2]] + chunks[-3:]

    chunk_summaries = []
    total_chunks = len(selected_chunks)
    for idx, chunk in enumerate(selected_chunks):
        pct = 15 + int((idx / total_chunks) * 55)
        progress("chunks", f"Analyzing conversation chunk {idx + 1}/{total_chunks}...", pct)

        chunk_text = "\n".join(
            f"[{m['timestamp']}] {m['sender']}: {m['content']}" for m in chunk
        )

        system = "You are a relationship analyst AI. Analyze text message conversations and provide insights. Respond in JSON format only."
        prompt = f"""Analyze this conversation chunk between "Me" and "{them}".

{chunk_text}

Respond with JSON:
{{
  "affection_level": <1-100>,
  "interest_signals": ["signal1", "signal2"],
  "tone": "description of overall tone",
  "notable_patterns": ["pattern1", "pattern2"]
}}"""

        try:
            result = ask_claude_json(prompt, system_prompt=system)
            chunk_summaries.append(result)
            # Extract insight snippet from chunk result
            parts = []
            if "affection_level" in result:
                parts.append(f"Affection: {result['affection_level']}/100")
            if "interest_signals" in result and isinstance(result["interest_signals"], list):
                parts.append(f"{len(result['interest_signals'])} interest signals")
            if "tone" in result:
                tone = result["tone"]
                if len(tone) > 40:
                    tone = tone[:40].rsplit(" ", 1)[0] + "..."
                parts.append(f"Tone: {tone}")
            if "notable_patterns" in result and isinstance(result["notable_patterns"], list):
                parts.append(f"{len(result['notable_patterns'])} patterns")
            snippet = f"Chunk {idx + 1}/{total_chunks}: {' | '.join(parts)}" if parts else f"Chunk {idx + 1}/{total_chunks}: analyzed"
            progress("chunks", snippet, pct, log_type="insight")
        except Exception as e:
            chunk_summaries.append({"error": str(e)})
            progress("chunks", f"Chunk {idx + 1}/{total_chunks}: error — {str(e)[:60]}", pct, log_type="status")

    progress("synthesis", "Synthesizing full analysis with Claude...", 75)

    # Final summary pass
    summary_text = json.dumps(chunk_summaries, indent=2)
    stats_summary = json.dumps(
        {
            "total_messages": stats["total_messages"],
            "initiative": stats["initiative"],
            "avg_response_seconds": stats["avg_response_seconds"],
            "avg_message_length": stats["avg_message_length"],
            "msgs_per_day": stats["msgs_per_day"],
        },
        indent=2,
    )

    system = f"""You are {user_name}'s personal {cat_ctx['role']}. You're supportive, direct, and encouraging.
You hype {user_name} up while keeping it real. You advocate for {user_name}'s needs and happiness.
Be specific, cite actual messages when possible, and give actionable advice.
You're analyzing {user_name}'s text conversation with "{them}" (categorized as: {cat_label}).
{pronoun_instruction}
{cat_ctx['tone_note']}
Focus on: {cat_ctx['focus']}.
{"Analyze whether the interest seems romantic vs platonic." if category == "auto" else f"This is a {cat_label} — tailor all advice to this relationship type."}
Respond in JSON format only."""

    context_block = ""
    if context_notes:
        context_block += f"""
{user_name}'s notes about this relationship:
{context_notes}

Use these notes to inform your analysis and tailor advice to what {user_name} wants from this connection.
"""
    if user_feedback:
        context_block += f"""
{user_name}'s feedback for this analysis:
{user_feedback}

IMPORTANT: Incorporate this feedback into your analysis. If they mention something that happened in person, factor it in. If they want you to focus on something specific, do that.
"""

    prompt = f"""Based on these chunk analyses and conversation stats, provide a comprehensive relationship analysis and lifestyle game plan.

Chunk analyses:
{summary_text}

Stats:
{stats_summary}
{context_block}
Respond with JSON:
{{
  "interest_type": {{
    "classification": "romantic" or "platonic" or "flirty_undefined" or "situationship" or "early_stage",
    "romantic_score": <0-100, where 0=purely platonic, 100=deeply romantic>,
    "reasoning": "2-3 sentence explanation of why you classified it this way, citing specific messages or patterns that indicate romantic vs platonic energy",
    "signals_romantic": ["specific evidence of romantic interest from the conversation"],
    "signals_platonic": ["specific evidence this might be just friendly"]
  }},
  "attachment_styles": {{
    "their_style": "secure" or "anxious-preoccupied" or "dismissive-avoidant" or "fearful-avoidant",
    "their_style_confidence": <0-100, how confident you are in this assessment>,
    "their_reasoning": "2-3 sentences explaining what texting patterns suggest this attachment style (e.g. double texting when no reply = anxious, going cold for days = avoidant, etc.)",
    "their_behaviors": ["specific behavior pattern 1 that indicates this style", "pattern 2"],
    "me_style": "secure" or "anxious-preoccupied" or "dismissive-avoidant" or "fearful-avoidant",
    "me_style_confidence": <0-100>,
    "me_reasoning": "2-3 sentences explaining the user's texting patterns and what they suggest",
    "me_behaviors": ["specific behavior pattern 1", "pattern 2"],
    "compatibility_note": "1-2 sentences on how these two attachment styles interact and what to watch out for"
  }},
  "affection_level": <1-100 overall>,
  "affection_reasoning": "1-2 sentence explanation citing specific patterns or messages",
  "relationship_score": <1-100>,
  "relationship_reasoning": "1-2 sentence explanation citing specific patterns or messages",
  "interest_signals": ["signal1", "signal2", ...],
  "green_flags": ["flag1", "flag2", ...],
  "red_flags": ["flag1", "flag2", ...],
  "communication_style": {{
    "them": "description",
    "me": "description"
  }},
  "quests": [
    "a specific activity or hangout idea based on shared interests from the conversation",
    "another specific activity based on things they've talked about",
    "another specific activity or outing idea that fits their vibe"
  ],
  "unresolved_topics": [
    "something they brought up that never got proper follow-up",
    "a plan or idea mentioned but never followed through on"
  ],
  "conversation_starters": [
    "a specific topic to bring up based on their interests",
    "another topic they'd be excited to talk about"
  ],
  "things_to_remember": [
    "an important detail about them (preference, upcoming event, something they care about)",
    "another personal detail worth remembering"
  ],
  "moves_to_make": [
    "a specific, actionable next move to escalate or deepen the connection",
    "another concrete step to take soon"
  ],
  "game_plan": {{
    "texting": {{
      "frequency": "detailed recommendation: how often to text, ideal times of day, how long to wait before replying, with specific reasoning from current patterns (e.g. 'they usually text back within 20 min so matching that energy is good')",
      "tone": "detailed tone guide: specific adjectives for the vibe to aim for, what energy to bring, how casual vs serious, with examples from the convo of what works well",
      "do": ["specific thing to do in texts this week with reasoning", "another actionable tip"],
      "dont": ["specific thing to avoid with reasoning", "another thing to avoid"],
      "example_texts": [
        "an actual example text the user could send right now based on recent convo context — word for word, ready to copy-paste",
        "another example text for a different scenario (e.g. flirty opener, callback to something they mentioned, asking to hang)",
        "a third example for a different situation"
      ],
      "timeline": [
        {{"day": "Today/Tomorrow", "action": "exactly what to do or text, with a specific example message"}},
        {{"day": "In 2-3 days", "action": "what to do next, with context on why this timing works"}},
        {{"day": "End of week", "action": "where you should be by then and what to aim for"}}
      ]
    }},
    "in_person": {{
      "how_to_act": "how to carry yourself next time you see them — energy, body language, vibe, what to wear",
      "tips": ["specific in-person tip based on their dynamic", "another tip", "a third tip"]
    }},
    "mental": {{
      "mindset": "mental frame to hold this week — how to think about things",
      "confidence": "specific confidence tip based on the conversation dynamics",
      "frame": "how to think about the relationship right now — what to focus on, what to let go"
    }},
    "dates": {{
      "next_date": "specific next hangout/date idea with exactly how to ask (word for word text to send)",
      "future_ideas": ["future idea 1 with brief reasoning", "future idea 2 with brief reasoning"]
    }},
    "your_needs": {{
      "what_you_need": "what the user seems to need from this person based on conversation patterns",
      "how_to_communicate": "how to bring it up naturally without being needy — with an example of what to say",
      "boundaries": ["a boundary to set or maintain with reasoning", "another boundary"]
    }}
  }},
  "summary": "2-3 sentence overall assessment — hype the user up, be honest, advocate for their happiness. Include whether this seems romantic or platonic."
}}"""

    full_prompt_log = f"SYSTEM:\n{system}\n\nPROMPT:\n{prompt}"

    try:
        result = ask_claude_json(prompt, system_prompt=system)
        progress("saving", "Saving results...", 95)
    except Exception as e:
        result = {
            "affection_level": 50,
            "relationship_score": 50,
            "interest_signals": [],
            "green_flags": [],
            "red_flags": [],
            "communication_style": {"them": "unknown", "me": "unknown"},
            "affection_reasoning": "Analysis failed.",
            "relationship_reasoning": "Analysis failed.",
            "quests": [f"Analysis failed: {e}"],
            "summary": "Could not complete analysis.",
        }

    save_analysis(contact, "full_analysis", result)
    save_analysis_history(contact, "full_analysis", result, user_feedback=user_feedback, prompt_text=full_prompt_log)
    progress("done", "Analysis complete!", 100)
    return result


def ask_insight(contact: str, question: str, user_name: str = "the user") -> str:
    """Answer a user's question about their conversation using Claude."""
    stats = compute_stats(contact)
    recent = get_recent_messages(200, contact)
    journal = get_journal_entries(contact)
    category = get_contact_category(contact)
    cat_ctx = get_category_context(category, user_name)
    cat_label = CATEGORY_LABELS.get(category, "contact")
    context_notes = get_context_notes(contact)

    recent_text = "\n".join(
        f"[{m['timestamp']}] {m['sender']}: {m['content']}" for m in recent
    )

    journal_text = ""
    if journal:
        journal_text = "\n\nJournal entries (user's notes about in-person interactions):\n"
        journal_text += "\n".join(
            f"[{e['timestamp']}] {e['entry_text']}" for e in journal[:10]
        )

    context_block = ""
    if context_notes:
        context_block = f"\n\n{user_name}'s notes about this relationship:\n{context_notes}"

    stats_text = json.dumps(
        {
            "total_messages": stats.get("total_messages"),
            "initiative": stats.get("initiative"),
            "avg_response_seconds": stats.get("avg_response_seconds"),
            "msgs_per_day": stats.get("msgs_per_day"),
            "them": stats.get("them"),
        },
        indent=2,
    )

    gender = get_contact_gender(contact)
    pronoun_instruction = get_pronoun_instruction(gender)

    system = f"""You are {user_name}'s personal {cat_ctx['role']} analyzing their text conversation with "{stats.get('them', 'them')}" (categorized as: {cat_label}).
You have access to their conversation stats and recent messages. Give specific, actionable advice grounded in actual message examples.
Cite specific messages when relevant. Be direct and honest but supportive.
{pronoun_instruction}
{cat_ctx['tone_note']}"""

    prompt = f"""Conversation stats:
{stats_text}

Recent messages:
{recent_text}
{journal_text}
{context_block}

User's question: {question}

Provide a thorough, specific answer based on the actual conversation data."""

    return ask_claude(prompt, system_prompt=system)


def get_next_move(contact: str) -> dict:
    """Get real-time coaching on what to text/do next."""
    recent = get_recent_messages(30, contact)
    if not recent:
        return {"error": "No messages found."}

    user_name = get_user_name()
    category = get_contact_category(contact)
    cat_ctx = get_category_context(category, user_name)
    cat_label = CATEGORY_LABELS.get(category, "contact")
    context_notes = get_context_notes(contact)
    gender = get_contact_gender(contact)
    pronoun_instruction = get_pronoun_instruction(gender)

    senders = get_senders(contact)
    them = next((s for s in senders if s != "Me"), "Them")

    # Get cached analysis for context
    cached = get_analysis(contact, "full_analysis")
    analysis_context = ""
    if cached:
        r = cached["result"]
        analysis_context = f"""
Current analysis context:
- Relationship score: {r.get('relationship_score', '?')}/100
- Affection level: {r.get('affection_level', '?')}/100
- Summary: {r.get('summary', 'N/A')}
"""

    recent_text = "\n".join(
        f"[{m['timestamp']}] {m['sender']}: {m['content']}" for m in recent
    )

    context_block = ""
    if context_notes:
        context_block = f"\n{user_name}'s notes: {context_notes}\n"

    system = f"""You are {user_name}'s personal {cat_ctx['role']}. You look at the latest messages and tell {user_name} exactly what to do RIGHT NOW — like a big brother giving real-time coaching.
{pronoun_instruction}
{cat_ctx['tone_note']}
Be specific. Give copy-paste ready messages when applicable. Consider timing, energy, and power dynamics.
Respond in JSON format only."""

    prompt = f"""Here are the most recent messages between {user_name} and "{them}" ({cat_label}):

{recent_text}
{analysis_context}{context_block}
Current time: {datetime.now().strftime("%A, %B %d at %I:%M %p")}

Based on this conversation state, what should {user_name} do RIGHT NOW?

Respond with JSON:
{{
  "situation": "Brief read of the current moment (e.g. 'They left you on read 3 hours ago' or 'You just had a great back-and-forth')",
  "recommendation": "primary" or "wait" or "silence",
  "moves": [
    {{
      "action": "send_now" or "send_later" or "wait" or "in_person",
      "timing": "Now" or "In ~1 hour" or "Tomorrow morning" or "Next time you see them",
      "message": "The exact text to send (if applicable, empty string if wait/in_person with no message)",
      "reasoning": "Why this is the move"
    }}
  ],
  "vibe_check": "1 sentence on the current energy/dynamic"
}}

Give 2-4 moves. At least one should be a ready-to-send message. Be creative and specific to their conversation."""

    try:
        result = ask_claude_json(prompt, system_prompt=system)
        return result
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}


def compute_global_stats() -> dict:
    """Aggregate stats across ALL contacts for the user's global profile."""
    messages = get_all_messages_global()
    if not messages:
        return {"error": "No messages found."}

    contacts = get_contacts()
    my_msgs = [m for m in messages if m["sender"] == "Me"]
    their_msgs = [m for m in messages if m["sender"] != "Me"]

    total_sent = len(my_msgs)
    total_received = len(their_msgs)

    # Avg message length (my messages)
    avg_msg_length = round(sum(m["word_count"] for m in my_msgs) / max(total_sent, 1), 1)

    # Emoji rate
    emoji_msgs = sum(1 for m in my_msgs if m["has_emoji"])
    emoji_rate = round(emoji_msgs / max(total_sent, 1) * 100, 1)

    # Question rate
    question_msgs = sum(1 for m in my_msgs if m["has_question"])
    question_rate = round(question_msgs / max(total_sent, 1) * 100, 1)

    # Avg response time (my responses)
    my_response_times = [m["response_time_seconds"] for m in my_msgs if m["response_time_seconds"] is not None and m["response_time_seconds"] < CONVO_GAP_SECONDS]
    avg_response_time = round(sum(my_response_times) / max(len(my_response_times), 1), 1)

    # Double texts
    double_texts = 0
    for i in range(1, len(messages)):
        if messages[i]["sender"] == "Me" and messages[i - 1]["sender"] == "Me":
            double_texts += 1

    # Late night count
    late_night = sum(1 for m in my_msgs if 0 <= datetime.fromisoformat(m["timestamp"]).hour < 5)

    # Initiative rate
    prev_ts = None
    convos_started_me = 0
    total_convos = 0
    for msg in messages:
        ts = datetime.fromisoformat(msg["timestamp"])
        if prev_ts is None or (ts - prev_ts).total_seconds() > CONVO_GAP_SECONDS:
            total_convos += 1
            if msg["sender"] == "Me":
                convos_started_me += 1
        prev_ts = ts
    initiative_rate = round(convos_started_me / max(total_convos, 1) * 100, 1)

    # Most-texted contact
    contact_msg_counts = Counter(m["contact"] for m in my_msgs)
    most_texted_id = contact_msg_counts.most_common(1)[0][0] if contact_msg_counts else None
    most_texted = most_texted_id
    for c in contacts:
        if c["phone_number"] == most_texted_id:
            most_texted = c["display_name"]
            break

    # Busiest hours
    hour_counts = Counter(datetime.fromisoformat(m["timestamp"]).hour for m in my_msgs)
    busiest_hours = dict(hour_counts.most_common())

    # Busiest days
    day_counts = Counter(datetime.fromisoformat(m["timestamp"]).strftime("%A") for m in my_msgs)
    busiest_days = dict(day_counts.most_common())

    # Days span
    if messages:
        first_ts = datetime.fromisoformat(messages[0]["timestamp"])
        last_ts = datetime.fromisoformat(messages[-1]["timestamp"])
        total_days = max((last_ts - first_ts).days, 1)
    else:
        total_days = 1

    msgs_per_day = round(total_sent / max(total_days, 1), 2)

    # Character class + level (reuse logic)
    level = min(99, max(1, total_sent // 100 + 1))
    character_class = "The Balanced One"
    if initiative_rate > 60:
        character_class = "The Initiator"
    elif emoji_rate > 30:
        character_class = "Emoji Royalty"
    elif avg_msg_length > 15:
        character_class = "The Novelist"
    elif avg_msg_length < 5:
        character_class = "The Minimalist"

    return {
        "total_sent": total_sent,
        "total_received": total_received,
        "total_messages": total_sent + total_received,
        "total_contacts": len(contacts),
        "total_days": total_days,
        "avg_response_time": avg_response_time,
        "avg_message_length": avg_msg_length,
        "emoji_rate": emoji_rate,
        "question_rate": question_rate,
        "initiative_rate": initiative_rate,
        "double_texts": double_texts,
        "late_night_count": late_night,
        "most_texted": most_texted,
        "busiest_hours": busiest_hours,
        "busiest_days": busiest_days,
        "msgs_per_day": msgs_per_day,
        "character_class": character_class,
        "level": level,
    }


def run_global_profile_analysis(force_refresh=False) -> dict:
    """Run Claude personality analysis across all contacts."""
    if not force_refresh:
        cached = get_analysis("__global__", "profile_analysis")
        if cached:
            return cached["result"]

    stats = compute_global_stats()
    if "error" in stats:
        return stats

    # Sample recent messages from top contacts
    contacts = get_contacts()
    contacts_sorted = sorted(contacts, key=lambda c: c.get("message_count", 0), reverse=True)
    top_contacts = contacts_sorted[:5]

    sample_msgs = []
    for c in top_contacts:
        recent = get_recent_messages(20, c["phone_number"])
        my_recent = [m for m in recent if m["sender"] == "Me"]
        sample_msgs.extend(my_recent[:10])

    sample_text = "\n".join(
        f"[to {m['contact']}] {m['content']}" for m in sample_msgs[:50]
    )

    user_name = get_user_name()
    stats_text = json.dumps(stats, indent=2)

    system = f"""You are a personality analyst. Analyze {user_name}'s texting patterns across ALL their conversations to build a comprehensive personality profile.
Be insightful, fun, and specific. This is about who {user_name} is as a texter and communicator.
Respond in JSON format only."""

    prompt = f"""Here are {user_name}'s global texting stats across all contacts:

{stats_text}

Sample of {user_name}'s recent messages across different contacts:
{sample_text}

Build a personality profile. Respond with JSON:
{{
  "personality_title": "A fun 2-4 word title (e.g. 'The Midnight Philosopher', 'Chaotic Good Texter')",
  "personality_summary": "2-3 sentence personality summary based on texting patterns",
  "communication_style": "1-2 sentence description of how they communicate",
  "strengths": ["strength 1 as a communicator", "strength 2", "strength 3"],
  "growth_areas": ["area for improvement 1", "area 2", "area 3"],
  "fun_facts": ["fun observation about their texting 1", "fun fact 2", "fun fact 3"],
  "texting_zodiac": "A made-up texting zodiac sign with a 1-sentence description (e.g. 'Double-Text Scorpio: You sting with a follow-up')",
  "who_you_are": "A 2-3 sentence warm, honest description of who this person is based on how they text — their values, energy, and vibe"
}}"""

    try:
        result = ask_claude_json(prompt, system_prompt=system)
        save_analysis("__global__", "profile_analysis", result)
        return result
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}
