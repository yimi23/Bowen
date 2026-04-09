"""
tools/helen_tools.py — HELEN Google Calendar + personal accountability tools.
calendar_list, calendar_create, task_create, bible_check, notify, daily_briefing.

Google API calls are synchronous. They're executed inside tool_use_loop (also sync).
For Phase 5 async contexts outside tool_use_loop, wrap with asyncio.to_thread().
"""

import sqlite3
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tools.google_auth import build_calendar, google_configured


HELEN_TOOL_SCHEMAS = [
    {
        "name": "calendar_list",
        "description": (
            "List Google Calendar events for a date range. "
            "Use to check today's schedule, upcoming meetings, or plan ahead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to look (default: 1 = today only)",
                },
                "calendar_id": {
                    "type": "string",
                    "description": "Google Calendar ID (default: 'primary')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max events to return (default: 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "calendar_create",
        "description": "Create a new Google Calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "start_datetime": {
                    "type": "string",
                    "description": "Start in ISO 8601 format e.g. '2025-03-08T09:00:00'",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "End in ISO 8601 format e.g. '2025-03-08T10:00:00'",
                },
                "description": {"type": "string", "description": "Event notes (optional)"},
                "calendar_id": {"type": "string", "description": "Calendar ID (default: 'primary')"},
            },
            "required": ["title", "start_datetime", "end_datetime"],
        },
    },
    {
        "name": "task_create",
        "description": "Create a new task in BOWEN's task tracker (visible in /status).",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task description"},
                "agent": {
                    "type": "string",
                    "description": "Responsible agent: CAPTAIN, SCOUT, TAMARA, HELEN, or BOWEN",
                },
                "context": {"type": "string", "description": "Additional notes or context"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "bible_check",
        "description": (
            "Check or log daily Bible reading. "
            "action='check' → see if today is done. action='log' → mark it complete."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check", "log"],
                    "description": "'check' to query status, 'log' to mark today complete",
                },
                "passage": {
                    "type": "string",
                    "description": "What was read today (e.g. 'Psalm 23, Matthew 5'). Required when action='log'.",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "notify",
        "description": "Send a reminder or alert to Praise (printed to console; Phase 5 adds system notifications).",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The notification message"},
                "urgency": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "Urgency level — affects display color",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "daily_briefing",
        "description": (
            "Gather all data for the morning briefing: today's calendar, Bible status, and open tasks. "
            "Returns raw data — you compose the spoken briefing from it. "
            "Use at 7am or whenever Praise asks for a morning update."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_override": {
                    "type": "string",
                    "description": "Date to brief for in ISO format (default: today)",
                },
            },
            "required": [],
        },
    },
]


# ── Bible log table ───────────────────────────────────────────────────────────

_BIBLE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bible_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    log_date    TEXT NOT NULL UNIQUE,
    completed   INTEGER DEFAULT 0,
    passage     TEXT DEFAULT '',
    logged_at   TEXT
);
"""


def _ensure_bible_table(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(_BIBLE_TABLE_SQL)
        conn.commit()


def _not_configured_error(creds_path: Path) -> dict:
    return {
        "success": False,
        "error": (
            f"Google credentials.json not found at {creds_path}. "
            "Complete Google OAuth setup first (see tools/google_auth.py docstring)."
        ),
    }


# ── Tool implementations ──────────────────────────────────────────────────────

def calendar_list(
    credentials_path: Path,
    token_path: Path,
    timezone: str,
    days_ahead: int = 1,
    calendar_id: str = "primary",
    max_results: int = 20,
) -> dict[str, Any]:
    """List calendar events for the next N days."""
    if not google_configured(credentials_path):
        return _not_configured_error(credentials_path)
    try:
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=max(1, days_ahead))).isoformat()

        service = build_calendar(credentials_path, token_path)
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max(1, min(max_results, 50)),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = result.get("items", [])
        if not events:
            return {"success": True, "count": 0, "events": [], "note": "No events in this range."}

        formatted = []
        for ev in events:
            start = ev.get("start", {})
            end = ev.get("end", {})
            formatted.append({
                "title": ev.get("summary", "(untitled)"),
                "start": start.get("dateTime") or start.get("date", ""),
                "end": end.get("dateTime") or end.get("date", ""),
                "location": ev.get("location", ""),
                "description": ev.get("description", "")[:200],
                "id": ev.get("id", ""),
            })

        return {"success": True, "count": len(formatted), "events": formatted}

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Calendar list failed: {type(e).__name__}: {e}"}


def calendar_create(
    credentials_path: Path,
    token_path: Path,
    timezone: str,
    title: str,
    start_datetime: str,
    end_datetime: str,
    description: str = "",
    calendar_id: str = "primary",
) -> dict[str, Any]:
    """Create a new Google Calendar event."""
    if not google_configured(credentials_path):
        return _not_configured_error(credentials_path)
    try:
        service = build_calendar(credentials_path, token_path)
        event_body: dict = {
            "summary": title,
            "start": {"dateTime": start_datetime, "timeZone": timezone},
            "end": {"dateTime": end_datetime, "timeZone": timezone},
        }
        if description:
            event_body["description"] = description

        created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return {
            "success": True,
            "event_id": created.get("id", ""),
            "title": title,
            "start": start_datetime,
            "end": end_datetime,
            "link": created.get("htmlLink", ""),
        }

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Calendar create failed: {type(e).__name__}: {e}"}


def task_create(
    db_path: Path,
    title: str,
    agent: str = "BOWEN",
    context: str = "",
) -> dict[str, Any]:
    """Insert a task into BOWEN's tasks table (same DB as MemoryStore)."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, agent, status, context, created_at, updated_at) "
                "VALUES (?, ?, 'pending', ?, ?, ?)",
                (title, agent, context, now, now),
            )
            conn.commit()
            task_id = cursor.lastrowid
        return {
            "success": True,
            "task_id": task_id,
            "title": title,
            "agent": agent,
            "status": "pending",
        }
    except Exception as e:
        return {"success": False, "error": f"Task create failed: {type(e).__name__}: {e}"}


def bible_check(
    db_path: Path,
    action: str = "check",
    passage: str = "",
) -> dict[str, Any]:
    """Check or log daily Bible reading status."""
    _ensure_bible_table(db_path)
    today = date.today().isoformat()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            if action == "log":
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    """INSERT INTO bible_log (log_date, completed, passage, logged_at)
                       VALUES (?, 1, ?, ?)
                       ON CONFLICT(log_date) DO UPDATE
                       SET completed=1, passage=excluded.passage, logged_at=excluded.logged_at""",
                    (today, passage, now),
                )
                conn.commit()
                return {
                    "success": True,
                    "action": "log",
                    "date": today,
                    "passage": passage,
                    "completed": True,
                }
            else:
                row = conn.execute(
                    "SELECT completed, passage, logged_at FROM bible_log WHERE log_date = ?",
                    (today,),
                ).fetchone()
                if row:
                    return {
                        "success": True,
                        "action": "check",
                        "date": today,
                        "completed": bool(row[0]),
                        "passage": row[1],
                        "logged_at": row[2],
                    }
                return {
                    "success": True,
                    "action": "check",
                    "date": today,
                    "completed": False,
                    "passage": "",
                    "note": "No reading logged yet today.",
                }
    except Exception as e:
        return {"success": False, "error": f"Bible check failed: {type(e).__name__}: {e}"}


def notify(message: str, urgency: str = "normal") -> dict[str, Any]:
    """Print a prominent notification. Phase 5: swap with plyer system notification."""
    colors = {"low": "\033[90m", "normal": "\033[36m", "high": "\033[33m"}
    color = colors.get(urgency, "\033[36m")
    print(f"\n{color}╔══ HELEN REMINDER ══╗\033[0m")
    print(f"{color}  {message}\033[0m")
    print(f"{color}╚════════════════════╝\033[0m\n")
    return {"success": True, "message": message, "urgency": urgency}


def daily_briefing(
    credentials_path: Path,
    token_path: Path,
    db_path: Path,
    timezone: str,
    date_override: str = "",
) -> dict[str, Any]:
    """
    Gather all data for the morning briefing.
    Returns a structured dict — Claude composes the spoken text from it.
    """
    target_date = date_override or date.today().isoformat()

    cal_result = calendar_list(credentials_path, token_path, timezone, days_ahead=1)
    bible_result = bible_check(db_path, action="check")

    open_tasks: list[dict] = []
    try:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                "SELECT title, agent, status FROM tasks "
                "WHERE status != 'done' ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            open_tasks = [{"title": r[0], "agent": r[1], "status": r[2]} for r in rows]
    except Exception:
        pass

    return {
        "success": True,
        "date": target_date,
        "timezone": timezone,
        "bible_completed": bible_result.get("completed", False),
        "bible_passage": bible_result.get("passage", ""),
        "events": cal_result.get("events", []),
        "event_count": cal_result.get("count", 0),
        "open_tasks": open_tasks,
        "open_task_count": len(open_tasks),
        "calendar_error": cal_result.get("error") if not cal_result.get("success") else None,
    }


# ── Registry entry ────────────────────────────────────────────────────────────

def make_helen_tool_map(
    credentials_path: Path,
    token_path: Path,
    db_path: Path,
    timezone: str,
) -> dict:
    """Returns tool map with credentials and paths bound."""
    return {
        "calendar_list":   lambda **kw: calendar_list(credentials_path, token_path, timezone, **kw),
        "calendar_create": lambda **kw: calendar_create(credentials_path, token_path, timezone, **kw),
        "task_create":     lambda **kw: task_create(db_path, **kw),
        "bible_check":     lambda **kw: bible_check(db_path, **kw),
        "notify":          notify,
        "daily_briefing":  lambda **kw: daily_briefing(credentials_path, token_path, db_path, timezone, **kw),
    }
