"""
tools/captain_tools.py — CAPTAIN tool implementations.
execute_code, read_file, write_file, run_shell, web_fetch.
All destructive operations require approval=True on the AgentMessage.
"""

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Paths that are NEVER accessible regardless of user or context.
# read_file and write_file reject any path under these trees.
BLOCKED_ROOTS: list[Path] = [
    Path("/System"),
    Path("/etc"),
    Path("/Library"),
    Path("/usr"),
    Path("/sbin"),
    Path("/bin"),
    Path("/private/etc"),
]

SHELL_BLOCKLIST = [
    "rm -rf /", "rm -rf ~", ":(){:|:&};:", "dd if=",
    "mkfs", "fdisk", "shutdown", "reboot", "halt",
]


def _check_path_blocked(p: Path) -> str | None:
    """Return an error string if the resolved path is inside a blocked root, else None."""
    for root in BLOCKED_ROOTS:
        try:
            p.relative_to(root)
            return f"Access denied: '{p}' is inside a protected system directory ({root})."
        except ValueError:
            continue
    return None


# ── Anthropic tool schemas ────────────────────────────────────────────────────

CAPTAIN_TOOL_SCHEMAS = [
    {
        "name": "execute_code",
        "description": (
            "Execute Python code and return the output. "
            "Use for running scripts, testing functions, data processing. "
            "Code runs in an isolated subprocess with a 30s timeout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "description": {"type": "string", "description": "One-line description of what this code does"},
            },
            "required": ["code", "description"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file. Returns the file content as a string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file"},
                "lines": {"type": "integer", "description": "Max lines to return (default: all)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
            "Always show the user what will be written before calling this."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file"},
                "content": {"type": "string", "description": "Content to write"},
                "description": {"type": "string", "description": "What this file does"},
            },
            "required": ["path", "content", "description"],
        },
    },
    {
        "name": "run_shell",
        "description": (
            "Run a shell command and return stdout + stderr. "
            "Use for git, npm, pip, file system operations, system info. "
            "Destructive commands (rm, format) require explicit user approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Working directory (optional)"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch a URL and return its text content. Use for reading documentation, APIs, or web pages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "extract": {"type": "string", "description": "What to extract from the page (optional hint)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "dispatch_create",
        "description": "Log a new task dispatch for tracking. Use to record work being started or delegated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title of the dispatch"},
                "description": {"type": "string", "description": "What is being done and why"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "dispatch_update",
        "description": "Update the status of an existing dispatch. Status values: pending, in_progress, done, failed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispatch_id": {"type": "string", "description": "ID of the dispatch to update"},
                "status": {"type": "string", "description": "New status: pending, in_progress, done, failed"},
                "result": {"type": "string", "description": "Result or outcome summary (optional)"},
            },
            "required": ["dispatch_id", "status"],
        },
    },
    {
        "name": "dispatch_list",
        "description": "List recent task dispatches and their statuses. Use to check what's in flight.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max dispatches to return (default: 10)"},
            },
            "required": [],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def execute_code(code: str, description: str = "") -> dict[str, Any]:
    """Execute Python code in a subprocess. 30s timeout."""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "Timeout: code ran > 30 seconds.", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}
    finally:
        os.unlink(tmp_path)


def read_file(path: str, lines: int | None = None) -> dict[str, Any]:
    """Read a file. Returns content or error."""
    try:
        p = Path(path).expanduser().resolve()
        blocked = _check_path_blocked(p)
        if blocked:
            return {"success": False, "error": blocked}
        if not p.exists():
            return {"success": False, "error": f"File not found: {path}"}
        content = p.read_text(errors="replace")
        if lines:
            content = "\n".join(content.splitlines()[:lines])
        return {"success": True, "content": content, "path": str(p), "size": p.stat().st_size}
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(path: str, content: str, description: str = "") -> dict[str, Any]:
    """Write content to a file."""
    try:
        p = Path(path).expanduser().resolve()
        blocked = _check_path_blocked(p)
        if blocked:
            return {"success": False, "error": blocked}
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content)
        return {
            "success": True,
            "path": str(p),
            "action": "overwritten" if existed else "created",
            "bytes": len(content.encode()),
        }
    except PermissionError:
        return {"success": False, "error": f"Permission denied: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_shell(command: str, cwd: str | None = None, timeout: int = 30) -> dict[str, Any]:
    """Run a shell command. Blocks dangerous commands."""
    cmd_lower = command.lower()
    for blocked in SHELL_BLOCKLIST:
        if blocked in cmd_lower:
            return {"success": False, "error": f"Blocked: '{blocked}' is a destructive command."}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout: command ran > {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def web_fetch(url: str, extract: str = "") -> dict[str, Any]:
    """Fetch a URL and return cleaned text."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BOWEN/1.0)"}
        resp = requests.get(url, headers=headers, timeout=15, verify="/etc/ssl/cert.pem")
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)[:8000]

        return {"success": True, "url": url, "content": content, "status_code": resp.status_code}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


# ── Registry entry ────────────────────────────────────────────────────────────

CAPTAIN_TOOL_MAP = {
    "execute_code": execute_code,
    "read_file": read_file,
    "write_file": write_file,
    "run_shell": run_shell,
    "web_fetch": web_fetch,
}


def make_captain_dispatch_map(db_path) -> dict:
    """
    Sync dispatch tools for CAPTAIN. Uses sqlite3 directly — safe since
    these run in asyncio.to_thread (off the event loop) inside base.py.
    """
    _db = str(db_path)

    def dispatch_create(title: str, description: str = "") -> dict:
        import sqlite3, uuid as _uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        dispatch_id = str(_uuid.uuid4())
        conn = sqlite3.connect(_db)
        try:
            conn.execute(
                "INSERT INTO dispatches (id, title, agent, description, topic_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (dispatch_id, title, "CAPTAIN", description, "default", now, now),
            )
            conn.commit()
            return {"success": True, "dispatch_id": dispatch_id, "title": title}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def dispatch_update(dispatch_id: str, status: str, result: str = "") -> dict:
        import sqlite3
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(_db)
        try:
            conn.execute(
                "UPDATE dispatches SET status = ?, result = ?, updated_at = ? WHERE id = ?",
                (status, result, now, dispatch_id),
            )
            conn.commit()
            return {"success": True, "dispatch_id": dispatch_id, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def dispatch_list(limit: int = 10) -> dict:
        import sqlite3
        conn = sqlite3.connect(_db)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, title, agent, status, description, result, created_at "
                "FROM dispatches ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return {"success": True, "dispatches": [dict(r) for r in rows], "count": len(rows)}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    return {
        "dispatch_create": dispatch_create,
        "dispatch_update": dispatch_update,
        "dispatch_list": dispatch_list,
    }
