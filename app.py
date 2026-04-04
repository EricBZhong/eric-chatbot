"""FastAPI main server for Eric-Chatbot."""

import subprocess
import os
import shutil
import uuid
import tempfile
from fastapi import FastAPI, Request, Query, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import (
    init_db, drop_and_recreate, get_messages_count, get_senders, get_contacts,
    set_user_attachment_style, get_user_attachment_style,
    set_contact_category, get_contact_category,
    set_contact_gender, get_contact_gender,
    set_context_notes, get_context_notes,
    get_user_name, set_user_name,
    get_analysis_history, get_analysis_history_entry,
)
from parser import parse_all_exports, parse_single_file, DATA_DIR, PHONE_PATTERN
from analyzer import compute_stats, run_claude_analysis, ask_insight, get_progress, get_next_move, compute_global_stats, run_global_profile_analysis
from clone import chat_as_clone, build_style_profile
from journal import get_prompts, save_entry
from database import get_journal_entries

app = FastAPI(title="Eric-Chatbot")

# Static files & templates
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
async def startup():
    init_db()


# --- Page Routes ---

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(name="dashboard.html", request=request)


@app.get("/insights")
async def insights_page(request: Request):
    return templates.TemplateResponse(name="insights.html", request=request)


@app.get("/chat")
async def chat_page(request: Request):
    return templates.TemplateResponse(name="chat.html", request=request)


@app.get("/journal")
async def journal_page(request: Request):
    return templates.TemplateResponse(name="journal.html", request=request)


@app.get("/history")
async def history_page(request: Request):
    return templates.TemplateResponse(name="history.html", request=request)


# --- API Routes ---

@app.get("/api/contacts")
async def api_contacts():
    contacts = get_contacts()
    return {"contacts": contacts}


class UserNameRequest(BaseModel):
    name: str


@app.get("/api/profile")
async def api_get_profile():
    return {"name": get_user_name()}


@app.post("/api/profile")
async def api_set_profile(req: UserNameRequest):
    set_user_name(req.name)
    return {"status": "ok", "name": req.name}


@app.post("/api/parse")
async def api_parse():
    results = parse_all_exports()
    total = sum(r["message_count"] for r in results.values())
    return {"status": "ok", "messages_parsed": total, "contacts": results}


def find_exporter():
    """Find imessage-exporter: bundled binary first, then system PATH."""
    bundled = os.path.join(os.path.dirname(__file__), "bin", "imessage-exporter")
    if os.path.isfile(bundled) and os.access(bundled, os.X_OK):
        return bundled
    return shutil.which("imessage-exporter")


class ImportRequest(BaseModel):
    filter: str = ""
    gender: str = "auto"
    category: str = "auto"


@app.post("/api/import")
async def api_import(req: ImportRequest = None):
    """Run imessage-exporter to refresh export files, then parse."""
    import logging
    logger = logging.getLogger("eric-chatbot.import")

    contact_filter = req.filter.strip() if req and req.filter else ""
    import_gender = req.gender if req and req.gender else "auto"
    import_category = req.category if req and req.category else "auto"
    logger.info(f"[import] Starting import. filter={contact_filter!r}")

    exporter = find_exporter()
    if not exporter:
        logger.error("[import] imessage-exporter not found")
        return JSONResponse(
            status_code=500,
            content={"error": "imessage-exporter not found. Restart the app to auto-download it, or install with: brew install imessage-exporter"},
        )

    os.makedirs(DATA_DIR, exist_ok=True)

    # For single-contact import, export to a temp dir to avoid polluting main dir
    export_dir = DATA_DIR
    tmp_dir = None
    if contact_filter:
        tmp_dir = tempfile.mkdtemp(prefix="imessage-export-")
        export_dir = tmp_dir

    cmd = [
        exporter,
        "--format", "txt",
        "--export-path", export_dir,
        "--copy-method", "disabled",
    ]
    if contact_filter:
        cmd.extend(["--conversation-filter", contact_filter])

    logger.info(f"[import] Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()

        logger.info(f"[import] Exit code: {result.returncode}")
        if stdout:
            logger.info(f"[import] stdout: {stdout[:500]}")
        if stderr:
            logger.info(f"[import] stderr: {stderr[:500]}")

        if result.returncode != 0:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            if "chat.db" in stderr.lower() or "permission denied" in stderr.lower() or "operation not permitted" in stderr.lower() or "could not open" in stderr.lower():
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "full_disk_access",
                        "message": "iMessage export needs Full Disk Access permission.",
                        "details": stderr[:500],
                    },
                )
            return JSONResponse(
                status_code=500,
                content={"error": f"imessage-exporter failed: {stderr}"},
            )

        # Check stderr for permission issues even on exit code 0
        stderr_lower = stderr.lower()
        if "chat.db" in stderr_lower or "permission denied" in stderr_lower or "operation not permitted" in stderr_lower or "could not open" in stderr_lower:
            logger.info(f"[import] Permission issue detected in stderr: {stderr[:200]}")
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return JSONResponse(
                status_code=403,
                content={
                    "error": "full_disk_access",
                    "message": "iMessage export needs Full Disk Access permission.",
                    "details": stderr[:500],
                },
            )

        # Check if filter matched nothing (exporter prints error to stderr but exits 0)
        if contact_filter and "does not match any participants" in stderr:
            logger.info("[import] No matching participants found")
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return {"status": "ok", "messages_parsed": 0, "contacts": {}, "no_match": True}

    except subprocess.TimeoutExpired:
        logger.error("[import] Timed out after 120s")
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return JSONResponse(
            status_code=500,
            content={"error": "imessage-exporter timed out after 120s"},
        )

    if contact_filter and tmp_dir:
        # Single-contact: parse only 1-on-1 files from tmp dir, skip group chats
        exported_files = sorted(os.listdir(tmp_dir))
        logger.info(f"[import] Files in tmp dir: {exported_files}")

        parse_results = {}
        first_contact = None
        for filename in exported_files:
            if filename == "orphaned.txt" or not filename.endswith(".txt"):
                logger.info(f"[import] Skipping non-txt or orphaned: {filename}")
                continue
            # Only import 1-on-1 conversations (single phone number filenames)
            phone_match = PHONE_PATTERN.match(filename)
            if not phone_match:
                logger.info(f"[import] Skipping non-phone filename: {filename}")
                continue
            contact_id = phone_match.group(1)
            filepath = os.path.join(tmp_dir, filename)
            logger.info(f"[import] Parsing {filename} as contact {contact_id}")
            result_data = parse_single_file(filepath, contact_id, gender=import_gender, category=import_category)
            if result_data:
                parse_results[contact_id] = result_data
                if first_contact is None:
                    first_contact = contact_id
                logger.info(f"[import] Parsed {result_data['message_count']} messages for {contact_id}")
            else:
                logger.info(f"[import] No messages parsed from {filename}")
            # Move file to main export dir
            shutil.move(filepath, os.path.join(DATA_DIR, filename))
        shutil.rmtree(tmp_dir, ignore_errors=True)

        total = sum(r["message_count"] for r in parse_results.values())
        logger.info(f"[import] Single-contact import done. total={total}, first_contact={first_contact}")

        # If exporter ran fine but found nothing, might be a permissions issue
        if total == 0 and not exported_files:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "full_disk_access",
                    "message": "No messages exported. This usually means Full Disk Access is needed.",
                },
            )

        return {
            "status": "ok",
            "messages_parsed": total,
            "contacts": parse_results,
            "selected_contact": first_contact,
        }
    else:
        # Full import: parse all files as before
        parse_results = parse_all_exports()
        total = sum(r["message_count"] for r in parse_results.values())
        logger.info(f"[import] Full import done. total={total}")

        # If exporter ran fine but found nothing, might be a permissions issue
        if total == 0:
            txt_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt") and f != "orphaned.txt"]
            if not txt_files:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "full_disk_access",
                        "message": "No messages exported. This usually means Full Disk Access is needed.",
                    },
                )

        return {
            "status": "ok",
            "messages_parsed": total,
            "contacts": parse_results,
        }


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), name: str = Form(""), gender: str = Form("auto"), category: str = Form("auto")):
    """Upload a .txt conversation export file to add a new contact."""
    if not file.filename.endswith(".txt"):
        return JSONResponse(status_code=400, content={"error": "Only .txt files are supported"})

    os.makedirs(DATA_DIR, exist_ok=True)

    # Read file content
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return JSONResponse(status_code=400, content={"error": "File must be UTF-8 encoded text"})

    if not text.strip():
        return JSONResponse(status_code=400, content={"error": "File is empty"})

    # Determine contact ID from filename or generate one
    import re
    phone_match = re.match(r"^(\+?\d[\d\-]+)\.txt$", file.filename)
    if phone_match:
        contact_id = phone_match.group(1)
    else:
        # Use a sanitized version of the filename or generate an ID
        contact_id = "upload-" + re.sub(r"[^a-zA-Z0-9]", "-", file.filename.rsplit(".", 1)[0])[:30]

    # Save file to export directory
    filepath = os.path.join(DATA_DIR, f"{contact_id}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

    # Parse the single file
    result = parse_single_file(filepath, contact_id, gender=gender, category=category)
    if not result:
        return JSONResponse(status_code=400, content={"error": "No messages found in file. Make sure it's in imessage-exporter txt format."})

    # If user provided a custom name, update the contact display name
    if name.strip():
        from database import insert_or_update_contact
        insert_or_update_contact(contact_id, name.strip(), result["message_count"],
                                  result.get("last_message_at", ""), gender=gender, category=category)

    return {
        "status": "ok",
        "contact_id": contact_id,
        "display_name": name.strip() or result["display_name"],
        "message_count": result["message_count"],
    }


@app.post("/api/reset-db")
async def api_reset_db():
    """Drop and recreate all tables."""
    drop_and_recreate()
    return {"status": "ok"}


@app.get("/api/stats")
async def api_stats(contact: str = Query(...)):
    count = get_messages_count(contact)
    if count == 0:
        return {"error": "No messages found. Run /api/parse first."}
    stats = compute_stats(contact)
    return stats


@app.get("/api/analysis")
def api_analysis(contact: str = Query(...)):
    count = get_messages_count(contact)
    if count == 0:
        return {"error": "No messages found. Run /api/parse first."}
    result = run_claude_analysis(contact)
    return result


class AnalysisRefreshRequest(BaseModel):
    feedback: str = ""


@app.post("/api/analysis/refresh")
def api_analysis_refresh(contact: str = Query(...), req: AnalysisRefreshRequest = None):
    feedback = req.feedback if req and req.feedback else ""
    result = run_claude_analysis(contact, force_refresh=True, user_feedback=feedback)
    return result


@app.get("/api/analysis/progress")
async def api_analysis_progress(contact: str = Query(...)):
    return get_progress(contact)


class InsightRequest(BaseModel):
    question: str


@app.post("/api/insights")
def api_insights(req: InsightRequest, contact: str = Query(...)):
    name = get_user_name()
    answer = ask_insight(contact, req.question, user_name=name)
    return {"answer": answer}


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/chat")
def api_chat(req: ChatRequest, contact: str = Query(...)):
    response = chat_as_clone(contact, req.message, req.history)
    return {"response": response}


@app.get("/api/chat/profile")
async def api_chat_profile(contact: str = Query(...)):
    profile = build_style_profile(contact)
    return profile


@app.get("/api/journal/prompts")
async def api_journal_prompts(contact: str = Query(...)):
    prompts = get_prompts(contact)
    return {"prompts": prompts}


class JournalEntryRequest(BaseModel):
    entry_text: str
    prompt_text: str = None


@app.post("/api/journal/entry")
async def api_journal_entry(req: JournalEntryRequest, contact: str = Query(...)):
    save_entry(contact, req.entry_text, req.prompt_text)
    return {"status": "ok"}


@app.get("/api/journal/entries")
async def api_journal_entries(contact: str = Query(...)):
    entries = get_journal_entries(contact)
    return {"entries": entries}


class AttachmentStyleRequest(BaseModel):
    style: str


@app.post("/api/attachment-style")
async def api_set_attachment_style(req: AttachmentStyleRequest, contact: str = Query(...)):
    valid = ["secure", "anxious-preoccupied", "dismissive-avoidant", "fearful-avoidant"]
    if req.style not in valid:
        return JSONResponse(status_code=400, content={"error": f"Invalid style. Must be one of: {valid}"})
    set_user_attachment_style(contact, req.style)
    return {"status": "ok", "style": req.style}


@app.get("/api/attachment-style")
async def api_get_attachment_style(contact: str = Query(...)):
    style = get_user_attachment_style(contact)
    return {"style": style}


VALID_CATEGORIES = [
    "auto", "romantic_interest", "casual_interest", "close_friend", "new_friend",
    "coworker", "family_parent", "family_sibling", "ex", "other",
]


class CategoryRequest(BaseModel):
    category: str


@app.post("/api/category")
async def api_set_category(req: CategoryRequest, contact: str = Query(...)):
    if req.category not in VALID_CATEGORIES:
        return JSONResponse(status_code=400, content={"error": f"Invalid category. Must be one of: {VALID_CATEGORIES}"})
    set_contact_category(contact, req.category)
    return {"status": "ok", "category": req.category}


@app.get("/api/category")
async def api_get_category(contact: str = Query(...)):
    category = get_contact_category(contact)
    return {"category": category}


VALID_GENDERS = ["auto", "he/him", "she/her", "they/them"]


class GenderRequest(BaseModel):
    gender: str


@app.post("/api/gender")
async def api_set_gender(req: GenderRequest, contact: str = Query(...)):
    if req.gender not in VALID_GENDERS:
        return JSONResponse(status_code=400, content={"error": f"Invalid gender. Must be one of: {VALID_GENDERS}"})
    set_contact_gender(contact, req.gender)
    return {"status": "ok", "gender": req.gender}


@app.get("/api/gender")
async def api_get_gender(contact: str = Query(...)):
    gender = get_contact_gender(contact)
    return {"gender": gender}


class ContextNotesRequest(BaseModel):
    notes: str


@app.post("/api/context-notes")
async def api_set_context_notes(req: ContextNotesRequest, contact: str = Query(...)):
    set_context_notes(contact, req.notes)
    return {"status": "ok"}


@app.get("/api/context-notes")
async def api_get_context_notes(contact: str = Query(...)):
    notes = get_context_notes(contact)
    return {"notes": notes}


@app.post("/api/next-move")
def api_next_move(contact: str = Query(...)):
    count = get_messages_count(contact)
    if count == 0:
        return {"error": "No messages found."}
    result = get_next_move(contact)
    return result


# --- Profile Routes ---

@app.get("/profile")
async def profile_page(request: Request):
    return templates.TemplateResponse(name="profile.html", request=request)


@app.get("/api/profile/stats")
async def api_profile_stats():
    stats = compute_global_stats()
    return stats


@app.get("/api/profile/analysis")
def api_profile_analysis():
    result = run_global_profile_analysis()
    return result


@app.post("/api/profile/analysis/refresh")
def api_profile_analysis_refresh():
    result = run_global_profile_analysis(force_refresh=True)
    return result


@app.get("/api/history")
async def api_history(contact: str = Query(...), limit: int = Query(50)):
    entries = get_analysis_history(contact, limit=limit)
    # Parse result_json for each entry
    import json
    for entry in entries:
        try:
            entry["result"] = json.loads(entry["result_json"])
        except Exception:
            entry["result"] = {}
        del entry["result_json"]
    return {"history": entries}


@app.get("/api/history/{entry_id}")
async def api_history_entry(entry_id: int):
    import json
    entry = get_analysis_history_entry(entry_id)
    if not entry:
        return JSONResponse(status_code=404, content={"error": "Not found"})
    try:
        entry["result"] = json.loads(entry["result_json"])
    except Exception:
        entry["result"] = {}
    del entry["result_json"]
    return entry
