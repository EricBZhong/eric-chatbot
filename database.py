import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "db.sqlite")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS contacts (
            phone_number TEXT PRIMARY KEY,
            display_name TEXT,
            message_count INTEGER DEFAULT 0,
            last_message_at TEXT,
            created_at TEXT,
            user_attachment_style TEXT,
            category TEXT DEFAULT 'auto',
            context_notes TEXT DEFAULT '',
            gender TEXT DEFAULT 'auto'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            word_count INTEGER DEFAULT 0,
            has_emoji INTEGER DEFAULT 0,
            has_question INTEGER DEFAULT 0,
            response_time_seconds REAL
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact TEXT NOT NULL DEFAULT '',
            timestamp TEXT NOT NULL,
            entry_text TEXT NOT NULL,
            ai_prompt_text TEXT
        );

        CREATE TABLE IF NOT EXISTS analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact TEXT NOT NULL DEFAULT '',
            analysis_type TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(contact, analysis_type)
        );

        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact TEXT NOT NULL,
            analysis_type TEXT NOT NULL,
            result_json TEXT NOT NULL,
            user_feedback TEXT DEFAULT '',
            prompt_text TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_history_contact ON analysis_history(contact);
        CREATE INDEX IF NOT EXISTS idx_history_created ON analysis_history(created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);
        CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact);
        CREATE INDEX IF NOT EXISTS idx_journal_timestamp ON journal_entries(timestamp);
        CREATE INDEX IF NOT EXISTS idx_journal_contact ON journal_entries(contact);
    """)
    conn.commit()

    # Migration: add gender column for existing DBs
    try:
        conn.execute("ALTER TABLE contacts ADD COLUMN gender TEXT DEFAULT 'auto'")
        conn.commit()
    except Exception:
        pass  # Column already exists

    conn.close()


def drop_and_recreate():
    """Drop all tables and recreate — use during dev migrations."""
    conn = get_conn()
    conn.executescript("""
        DROP TABLE IF EXISTS messages;
        DROP TABLE IF EXISTS journal_entries;
        DROP TABLE IF EXISTS analysis_cache;
        DROP TABLE IF EXISTS analysis_history;
        DROP TABLE IF EXISTS contacts;
    """)
    conn.commit()
    conn.close()
    init_db()


# --- Settings ---

def get_setting(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_user_name() -> str:
    return get_setting("user_name", "Me")


def set_user_name(name: str):
    set_setting("user_name", name)


# --- Contacts ---

def get_contacts():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM contacts ORDER BY display_name ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_or_update_contact(phone_number: str, display_name: str, message_count: int, last_message_at: str, gender: str = "auto", category: str = "auto"):
    conn = get_conn()
    conn.execute(
        """INSERT INTO contacts (phone_number, display_name, message_count, last_message_at, created_at, gender, category)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(phone_number) DO UPDATE SET
               display_name = excluded.display_name,
               message_count = excluded.message_count,
               last_message_at = excluded.last_message_at,
               gender = CASE WHEN excluded.gender != 'auto' THEN excluded.gender ELSE contacts.gender END,
               category = CASE WHEN excluded.category != 'auto' THEN excluded.category ELSE contacts.category END""",
        (phone_number, display_name, message_count, last_message_at, datetime.now().isoformat(), gender, category),
    )
    conn.commit()
    conn.close()


def set_user_attachment_style(phone_number: str, style: str):
    conn = get_conn()
    conn.execute(
        "UPDATE contacts SET user_attachment_style = ? WHERE phone_number = ?",
        (style, phone_number),
    )
    conn.commit()
    conn.close()


def get_user_attachment_style(phone_number: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT user_attachment_style FROM contacts WHERE phone_number = ?",
        (phone_number,),
    ).fetchone()
    conn.close()
    return row["user_attachment_style"] if row else None


def set_contact_category(phone_number: str, category: str):
    conn = get_conn()
    conn.execute(
        "UPDATE contacts SET category = ? WHERE phone_number = ?",
        (category, phone_number),
    )
    conn.commit()
    conn.close()


def get_contact_category(phone_number: str) -> str:
    conn = get_conn()
    row = conn.execute(
        "SELECT category FROM contacts WHERE phone_number = ?",
        (phone_number,),
    ).fetchone()
    conn.close()
    return row["category"] if row and row["category"] else "auto"


def set_contact_gender(phone_number: str, gender: str):
    conn = get_conn()
    conn.execute(
        "UPDATE contacts SET gender = ? WHERE phone_number = ?",
        (gender, phone_number),
    )
    conn.commit()
    conn.close()


def get_contact_gender(phone_number: str) -> str:
    conn = get_conn()
    row = conn.execute(
        "SELECT gender FROM contacts WHERE phone_number = ?",
        (phone_number,),
    ).fetchone()
    conn.close()
    return row["gender"] if row and row["gender"] else "auto"


def set_context_notes(phone_number: str, notes: str):
    conn = get_conn()
    conn.execute(
        "UPDATE contacts SET context_notes = ? WHERE phone_number = ?",
        (notes, phone_number),
    )
    conn.commit()
    conn.close()


def get_context_notes(phone_number: str) -> str:
    conn = get_conn()
    row = conn.execute(
        "SELECT context_notes FROM contacts WHERE phone_number = ?",
        (phone_number,),
    ).fetchone()
    conn.close()
    return row["context_notes"] if row and row["context_notes"] else ""


# --- Messages ---

def insert_messages(messages: list[dict]):
    conn = get_conn()
    conn.executemany(
        """INSERT INTO messages (contact, timestamp, sender, content, word_count, has_emoji, has_question, response_time_seconds)
           VALUES (:contact, :timestamp, :sender, :content, :word_count, :has_emoji, :has_question, :response_time_seconds)""",
        messages,
    )
    conn.commit()
    conn.close()


def get_all_messages(contact: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE contact = ? ORDER BY timestamp ASC", (contact,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_messages_global():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM messages ORDER BY timestamp ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_messages_count(contact: str):
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE contact = ?", (contact,)
    ).fetchone()[0]
    conn.close()
    return count


def get_recent_messages(limit: int, contact: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM messages WHERE contact = ? ORDER BY timestamp DESC LIMIT ?",
        (contact, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_senders(contact: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT sender FROM messages WHERE contact = ?", (contact,)
    ).fetchall()
    conn.close()
    return [r["sender"] for r in rows]


def clear_messages_for_contact(contact: str):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE contact = ?", (contact,))
    conn.commit()
    conn.close()


def clear_messages():
    conn = get_conn()
    conn.execute("DELETE FROM messages")
    conn.commit()
    conn.close()


# --- Analysis Cache ---

def save_analysis(contact: str, analysis_type: str, result: dict):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO analysis_cache (contact, analysis_type, result_json, created_at)
           VALUES (?, ?, ?, ?)""",
        (contact, analysis_type, json.dumps(result), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_analysis(contact: str, analysis_type: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM analysis_cache WHERE contact = ? AND analysis_type = ?",
        (contact, analysis_type),
    ).fetchone()
    conn.close()
    if row:
        return {"result": json.loads(row["result_json"]), "created_at": row["created_at"]}
    return None


# --- Analysis History ---

def save_analysis_history(contact: str, analysis_type: str, result: dict, user_feedback: str = "", prompt_text: str = ""):
    conn = get_conn()
    conn.execute(
        """INSERT INTO analysis_history (contact, analysis_type, result_json, user_feedback, prompt_text, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (contact, analysis_type, json.dumps(result), user_feedback, prompt_text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_analysis_history(contact: str, analysis_type: str = "full_analysis", limit: int = 50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM analysis_history WHERE contact = ? AND analysis_type = ? ORDER BY created_at DESC LIMIT ?",
        (contact, analysis_type, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analysis_history_entry(entry_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM analysis_history WHERE id = ?", (entry_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Journal ---

def save_journal_entry(contact: str, entry_text: str, ai_prompt_text: str = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO journal_entries (contact, timestamp, entry_text, ai_prompt_text) VALUES (?, ?, ?, ?)",
        (contact, datetime.now().isoformat(), entry_text, ai_prompt_text),
    )
    conn.commit()
    conn.close()


def get_journal_entries(contact: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM journal_entries WHERE contact = ? ORDER BY timestamp DESC",
        (contact,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
