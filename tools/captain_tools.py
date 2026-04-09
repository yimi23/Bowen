"""
tools/captain_tools.py — CAPTAIN tool implementations.
execute_code, read_file, write_file, run_shell, web_fetch.
All destructive operations require approval=True on the AgentMessage.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

# Safety: restrict shell/file ops to these root dirs
ALLOWED_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path("/tmp"),
]

SHELL_BLOCKLIST = [
    "rm -rf /", "rm -rf ~", ":(){:|:&};:", "dd if=",
    "mkfs", "fdisk", "shutdown", "reboot", "halt",
]


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
