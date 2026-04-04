"""Context journal: log in-person interactions and get AI-prompted questions."""

from database import get_recent_messages, get_journal_entries, save_journal_entry, get_senders
from claude_cli import ask_claude


def get_prompts(contact: str) -> list[str]:
    """Generate contextual journal prompts based on recent messages."""
    recent = get_recent_messages(50, contact)
    journal = get_journal_entries(contact)
    senders = get_senders(contact)
    them = next((s for s in senders if s != "Me"), "Them")

    if not recent:
        return [
            f"How are things going with {them} lately?",
            "Have you two hung out in person recently?",
            "What's on your mind about the relationship?",
        ]

    recent_text = "\n".join(
        f"[{m['timestamp']}] {m['sender']}: {m['content']}" for m in recent[-30:]
    )

    journal_text = ""
    if journal:
        journal_text = "\n\nPrevious journal entries:\n" + "\n".join(
            f"[{e['timestamp']}] {e['entry_text']}" for e in journal[:5]
        )

    system = "You are a relationship coach helping someone reflect on their connection. Generate thoughtful, specific journal prompts based on their recent text conversations."

    prompt = f"""Based on these recent messages between "Me" and "{them}", generate exactly 3 specific journal prompts.

The prompts should:
- Reference specific topics/events from the messages
- Ask about in-person interactions and feelings
- Help the user reflect on the relationship

Recent messages:
{recent_text}
{journal_text}

Return exactly 3 prompts, one per line. No numbering, no bullets, just the questions."""

    try:
        response = ask_claude(prompt, system_prompt=system)
        prompts = [line.strip() for line in response.strip().split("\n") if line.strip()]
        # Clean up any numbering or bullets
        cleaned = []
        for p in prompts:
            p = p.lstrip("0123456789.-) ").strip()
            if p:
                cleaned.append(p)
        return cleaned[:3] if cleaned else [
            "How are things going?",
            "Any in-person updates?",
            "What's on your mind?",
        ]
    except Exception:
        return [
            "How are things going lately?",
            "Have you two hung out in person recently?",
            "What's on your mind about the relationship?",
        ]


def save_entry(contact: str, entry_text: str, prompt_text: str = None):
    """Save a journal entry."""
    save_journal_entry(contact, entry_text, prompt_text)
