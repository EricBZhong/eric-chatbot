import os
import re
import emoji
from datetime import datetime
from database import (
    insert_messages,
    clear_messages_for_contact,
    insert_or_update_contact,
    get_conn,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "export")

# imessage-exporter txt format:
# Jan 01, 2024  12:00:00 PM
# Sender Name
# Message content (can be multiline)
#
# (blank line separates messages)

TIMESTAMP_PATTERN = re.compile(
    r"^([A-Z][a-z]{2} \d{1,2}, \d{4}\s+\d{1,2}:\d{2}:\d{2}\s*[AP]M)$"
)

TIMESTAMP_FORMATS = [
    "%b %d, %Y  %I:%M:%S %p",
    "%b %d, %Y %I:%M:%S %p",
    "%b %d, %Y  %I:%M:%S%p",
]

PHONE_PATTERN = re.compile(r"^(\+?\d[\d\-]+)\.txt$")


def parse_timestamp(ts_str: str) -> datetime | None:
    ts_str = ts_str.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def has_emoji_check(text: str) -> bool:
    return any(c in emoji.EMOJI_DATA for c in text)


def has_question(text: str) -> bool:
    return "?" in text


def parse_txt_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    messages = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Try to match a timestamp
        match = TIMESTAMP_PATTERN.match(line)
        if match:
            ts = parse_timestamp(match.group(1))
            if ts and i + 1 < len(lines):
                sender = lines[i + 1].strip()
                i += 2

                # Collect message content lines until next timestamp or end
                content_lines = []
                while i < len(lines):
                    next_line = lines[i].strip()
                    if TIMESTAMP_PATTERN.match(next_line):
                        break
                    if next_line or content_lines:  # skip leading blanks
                        content_lines.append(lines[i].rstrip())
                    i += 1

                # Trim trailing blank lines
                while content_lines and not content_lines[-1].strip():
                    content_lines.pop()

                msg_content = "\n".join(content_lines).strip()
                if msg_content and sender:
                    messages.append(
                        {
                            "timestamp": ts.isoformat(),
                            "sender": sender,
                            "content": msg_content,
                        }
                    )
                continue
        i += 1

    return messages


def compute_metadata(messages: list[dict]) -> list[dict]:
    """Add computed fields to each message."""
    for i, msg in enumerate(messages):
        msg["word_count"] = len(msg["content"].split())
        msg["has_emoji"] = 1 if has_emoji_check(msg["content"]) else 0
        msg["has_question"] = 1 if has_question(msg["content"]) else 0

        # Response time: time since last message from a different sender
        msg["response_time_seconds"] = None
        if i > 0:
            prev = messages[i - 1]
            if prev["sender"] != msg["sender"]:
                try:
                    curr_ts = datetime.fromisoformat(msg["timestamp"])
                    prev_ts = datetime.fromisoformat(prev["timestamp"])
                    delta = (curr_ts - prev_ts).total_seconds()
                    if delta >= 0:
                        msg["response_time_seconds"] = delta
                except (ValueError, TypeError):
                    pass

    return messages


def derive_display_name(messages: list[dict]) -> str:
    """Get the first non-'Me' sender name from messages."""
    for msg in messages:
        if msg["sender"] != "Me":
            return msg["sender"]
    return "Unknown"


def parse_single_file(filepath: str, contact_id: str, gender: str = "auto", category: str = "auto") -> dict:
    """Parse a single txt file and store as a specific contact.

    contact_id can be a phone number or any unique identifier.
    Returns { display_name, message_count } or None if no messages.
    """
    messages = parse_txt_file(filepath)
    if not messages:
        return None

    messages.sort(key=lambda m: m["timestamp"])
    display_name = derive_display_name(messages)

    for msg in messages:
        msg["contact"] = contact_id

    messages = compute_metadata(messages)

    clear_messages_for_contact(contact_id)
    insert_messages(messages)

    last_message_at = messages[-1]["timestamp"] if messages else None
    insert_or_update_contact(contact_id, display_name, len(messages), last_message_at, gender=gender, category=category)

    return {
        "display_name": display_name,
        "message_count": len(messages),
    }


def parse_all_exports() -> dict:
    """Parse all txt files in the export directory, one per contact.

    Returns dict: { phone_number: { display_name, message_count } }
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        return {}

    results = {}

    for filename in sorted(os.listdir(DATA_DIR)):
        # Skip orphaned.txt and non-txt files
        if filename == "orphaned.txt" or not filename.endswith(".txt"):
            continue

        # Extract phone number from filename
        phone_match = PHONE_PATTERN.match(filename)
        if not phone_match:
            continue

        phone_number = phone_match.group(1)
        filepath = os.path.join(DATA_DIR, filename)

        # Parse messages from file
        messages = parse_txt_file(filepath)
        if not messages:
            continue

        # Sort by timestamp
        messages.sort(key=lambda m: m["timestamp"])

        # Derive display name
        display_name = derive_display_name(messages)

        # Tag each message with contact
        for msg in messages:
            msg["contact"] = phone_number

        # Compute metadata
        messages = compute_metadata(messages)

        # Clear old messages for this contact and insert new
        clear_messages_for_contact(phone_number)
        insert_messages(messages)

        # Upsert contact record
        last_message_at = messages[-1]["timestamp"] if messages else None
        insert_or_update_contact(phone_number, display_name, len(messages), last_message_at)

        results[phone_number] = {
            "display_name": display_name,
            "message_count": len(messages),
        }

    return results
