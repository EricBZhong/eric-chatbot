"""Clone chat: AI that mimics the contact's texting style."""

from collections import Counter
from database import get_all_messages, get_senders
from claude_cli import ask_claude


def build_style_profile(contact: str) -> dict:
    """Analyze the contact's messages to build a texting style profile."""
    messages = get_all_messages(contact)
    senders = get_senders(contact)
    them = next((s for s in senders if s != "Me"), "Them")
    their_msgs = [m for m in messages if m["sender"] == them]

    if not their_msgs:
        return {"name": them, "profile": "No messages from them found."}

    # Average message length
    avg_words = sum(m["word_count"] for m in their_msgs) / len(their_msgs)

    # Common phrases (2+ word combos)
    word_freq = Counter()
    for m in their_msgs:
        words = m["content"].lower().split()
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            word_freq[bigram] += 1
    common_phrases = [phrase for phrase, count in word_freq.most_common(20) if count >= 3]

    # Emoji usage
    import emoji as emoji_lib
    emoji_freq = Counter()
    for m in their_msgs:
        for c in m["content"]:
            if c in emoji_lib.EMOJI_DATA:
                emoji_freq[c] += 1
    top_emojis = [e for e, _ in emoji_freq.most_common(10)]

    # Capitalization style
    lowercase_count = sum(1 for m in their_msgs if m["content"] == m["content"].lower())
    lowercase_ratio = lowercase_count / len(their_msgs)
    cap_style = "mostly lowercase" if lowercase_ratio > 0.7 else "proper capitalization" if lowercase_ratio < 0.3 else "mixed capitalization"

    # Message length distribution
    short = sum(1 for m in their_msgs if m["word_count"] <= 3)
    medium = sum(1 for m in their_msgs if 4 <= m["word_count"] <= 15)
    long_ = sum(1 for m in their_msgs if m["word_count"] > 15)
    total = len(their_msgs)
    length_style = f"{round(short/total*100)}% short (1-3 words), {round(medium/total*100)}% medium (4-15 words), {round(long_/total*100)}% long (15+ words)"

    # Question frequency
    question_ratio = sum(1 for m in their_msgs if m["has_question"]) / len(their_msgs)

    return {
        "name": them,
        "avg_words": round(avg_words, 1),
        "common_phrases": common_phrases[:10],
        "top_emojis": top_emojis,
        "cap_style": cap_style,
        "length_style": length_style,
        "question_ratio": round(question_ratio * 100, 1),
        "total_messages": len(their_msgs),
    }


def get_example_messages(contact: str, limit=100) -> list[str]:
    """Get recent messages from the contact as few-shot examples."""
    messages = get_all_messages(contact)
    senders = get_senders(contact)
    them = next((s for s in senders if s != "Me"), "Them")

    their_msgs = [m for m in messages if m["sender"] == them]
    recent = their_msgs[-limit:] if len(their_msgs) > limit else their_msgs
    return [m["content"] for m in recent]


def chat_as_clone(contact: str, user_message: str, history: list[dict] = None) -> str:
    """Send a message and get a response in the contact's style."""
    profile = build_style_profile(contact)
    examples = get_example_messages(contact, 100)

    examples_text = "\n".join(f"- {msg}" for msg in examples[-50:])

    system = f"""You are roleplaying as {profile['name']} in a text conversation. Here is their texting style:
- Average message length: {profile['avg_words']} words
- Common phrases: {', '.join(profile['common_phrases'][:10]) if profile['common_phrases'] else 'none detected'}
- Emoji usage: {' '.join(profile['top_emojis']) if profile['top_emojis'] else 'minimal'}
- Capitalization: {profile['cap_style']}
- Message length distribution: {profile['length_style']}
- Asks questions {profile['question_ratio']}% of the time

Here are example messages they've sent:
{examples_text}

Respond as they would. Match their tone, length, capitalization, and emoji usage exactly.
Stay in character. Keep responses natural and conversational.
IMPORTANT: You are an AI simulation for practice purposes only."""

    # Build conversation context
    convo = ""
    if history:
        for msg in history[-20:]:  # Last 20 messages for context
            role = "Me" if msg.get("role") == "user" else profile["name"]
            convo += f"{role}: {msg['content']}\n"

    convo += f"Me: {user_message}\n{profile['name']}:"

    response = ask_claude(convo, system_prompt=system)
    return response
