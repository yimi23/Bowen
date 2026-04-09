"""
tools/tamara_tools.py — TAMARA Gmail tool implementations.
gmail_read, gmail_send, gmail_draft.

All google-api-python-client calls are synchronous (blocking).
They're called from tool_use_loop which is also synchronous — this is fine for CLI.
For Phase 5 async pipeline, wrap call sites with asyncio.to_thread().

TAMARA RULE: gmail_send prompts for explicit user approval before transmitting.
             No email leaves without confirmation. No exceptions.
"""

import base64
import email.mime.text
from pathlib import Path
from typing import Any

from tools.google_auth import build_gmail, google_configured


TAMARA_TOOL_SCHEMAS = [
    {
        "name": "gmail_read",
        "description": (
            "Read recent emails from the inbox. Returns subject, sender, date, and snippet. "
            "Use to surface urgent emails, check inbox status, or find a specific thread."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Max emails to return (default: 10)",
                },
                "query": {
                    "type": "string",
                    "description": "Gmail search query (e.g. 'is:unread', 'from:boss@company.com', 'subject:invoice')",
                },
                "include_body": {
                    "type": "string",
                    "description": "'yes' to include full body text (default: snippet only)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "gmail_draft",
        "description": (
            "Create a Gmail draft. Does NOT send — always safe to call. "
            "Use to prepare a reply or new email for Praise to review before sending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body text (plain text)"},
                "reply_to_id": {
                    "type": "string",
                    "description": "Message-ID header of the email being replied to (optional)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_send",
        "description": (
            "Send an email. ALWAYS surfaces a preview and requires explicit user approval "
            "before transmitting — the tool itself prompts before calling the API. "
            "Never assume approval has been granted before calling this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body text (plain text)"},
                "reply_to_id": {
                    "type": "string",
                    "description": "Message-ID header of the email being replied to (optional)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_raw_message(to: str, subject: str, body: str, reply_to_id: str = "") -> dict:
    """Build a base64url-encoded Gmail message payload."""
    msg = email.mime.text.MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    if reply_to_id:
        msg["In-Reply-To"] = reply_to_id
        msg["References"] = reply_to_id
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def _extract_body(payload: dict) -> str:
    """Recursively pull plain-text body from Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _not_configured_error(creds_path: Path) -> dict:
    return {
        "success": False,
        "error": (
            f"Google credentials not found at {creds_path}. "
            "Run the Google OAuth setup first (see tools/google_auth.py)."
        ),
    }


# ── Tool implementations ──────────────────────────────────────────────────────

def gmail_read(
    credentials_path: Path,
    token_path: Path,
    max_results: int = 10,
    query: str = "in:inbox",
    include_body: str = "no",
) -> dict[str, Any]:
    """Fetch recent emails. Returns list of summaries with headers + snippet."""
    if not google_configured(credentials_path):
        return _not_configured_error(credentials_path)
    try:
        service = build_gmail(credentials_path, token_path)
        q = query or "in:inbox"
        results = service.users().messages().list(
            userId="me", q=q, maxResults=max(1, min(max_results, 50))
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return {"success": True, "count": 0, "emails": [], "note": "No emails matched."}

        emails = []
        fmt = "full" if include_body == "yes" else "metadata"
        meta_headers = ["Subject", "From", "To", "Date", "Message-ID"]

        for m in messages:
            detail = service.users().messages().get(
                userId="me",
                id=m["id"],
                format=fmt,
                metadataHeaders=meta_headers,
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in detail.get("payload", {}).get("headers", [])
            }
            entry = {
                "id": m["id"],
                "message_id": headers.get("Message-ID", ""),
                "subject": headers.get("Subject", "(no subject)"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "snippet": detail.get("snippet", ""),
            }
            if include_body == "yes":
                body_text = _extract_body(detail.get("payload", {}))
                entry["body"] = body_text[:3000]
            emails.append(entry)

        return {"success": True, "count": len(emails), "emails": emails}

    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Gmail read failed: {type(e).__name__}: {e}"}


def gmail_draft(
    credentials_path: Path,
    token_path: Path,
    to: str,
    subject: str,
    body: str,
    reply_to_id: str = "",
) -> dict[str, Any]:
    """Create a Gmail draft. Safe — does not send."""
    if not google_configured(credentials_path):
        return _not_configured_error(credentials_path)
    try:
        service = build_gmail(credentials_path, token_path)
        raw_msg = _build_raw_message(to, subject, body, reply_to_id)
        draft = service.users().drafts().create(
            userId="me",
            body={"message": raw_msg},
        ).execute()

        return {
            "success": True,
            "draft_id": draft.get("id", ""),
            "to": to,
            "subject": subject,
            "body_preview": body[:300],
            "note": "Draft saved in Gmail. Call gmail_send to send after Praise approves.",
        }
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Draft failed: {type(e).__name__}: {e}"}


def gmail_send(
    credentials_path: Path,
    token_path: Path,
    to: str,
    subject: str,
    body: str,
    reply_to_id: str = "",
) -> dict[str, Any]:
    """
    Send an email — but ONLY after explicit terminal approval.
    TAMARA rule: never transmits without user confirmation. No exceptions.
    """
    if not google_configured(credentials_path):
        return _not_configured_error(credentials_path)

    # Surface the draft for approval before touching the API
    print("\n\033[33m[TAMARA] Ready to send — approval required:\033[0m")
    print(f"  To:      {to}")
    print(f"  Subject: {subject}")
    print(f"  Body:\n{_indent(body)}")
    try:
        answer = input("\n  Send this email? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"

    if answer != "y":
        return {
            "success": False,
            "sent": False,
            "error": "Send cancelled by user — no email transmitted.",
        }

    try:
        service = build_gmail(credentials_path, token_path)
        raw_msg = _build_raw_message(to, subject, body, reply_to_id)
        sent = service.users().messages().send(
            userId="me", body=raw_msg
        ).execute()

        return {
            "success": True,
            "sent": True,
            "message_id": sent.get("id", ""),
            "to": to,
            "subject": subject,
        }
    except FileNotFoundError as e:
        return {"success": False, "sent": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "sent": False, "error": f"Send failed: {type(e).__name__}: {e}"}


# ── Registry entry ────────────────────────────────────────────────────────────

def make_tamara_tool_map(credentials_path: Path, token_path: Path) -> dict:
    """Returns tool map with credentials bound."""
    return {
        "gmail_read":  lambda **kw: gmail_read(credentials_path, token_path, **kw),
        "gmail_draft": lambda **kw: gmail_draft(credentials_path, token_path, **kw),
        "gmail_send":  lambda **kw: gmail_send(credentials_path, token_path, **kw),
    }
