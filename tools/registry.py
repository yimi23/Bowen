"""
tools/registry.py — Per-agent tool enforcement + schema lookup.
Agents cannot call tools outside their allowed set.
"""

import json
from typing import Any, Callable

from tools.captain_tools import CAPTAIN_TOOL_MAP, CAPTAIN_TOOL_SCHEMAS
from tools.scout_tools import make_scout_tool_map, SCOUT_TOOL_SCHEMAS
from tools.tamara_tools import make_tamara_tool_map, TAMARA_TOOL_SCHEMAS
from tools.helen_tools import make_helen_tool_map, HELEN_TOOL_SCHEMAS
from tools.bowen_tools import make_bowen_tool_map, BOWEN_TOOL_SCHEMAS

TOOL_REGISTRY: dict[str, list[str]] = {
    "CAPTAIN": ["execute_code", "read_file", "write_file", "run_shell", "web_fetch"],
    "SCOUT":   ["web_search", "web_fetch", "document_parse", "structured_extract"],
    "TAMARA":  ["gmail_read", "gmail_send", "gmail_draft"],
    "HELEN":   ["calendar_list", "calendar_create", "task_create", "bible_check", "notify", "daily_briefing"],
    "BOWEN":   ["memory_search", "task_create", "task_list"],
}

_TOOL_IMPLEMENTATIONS: dict[str, Callable] = {}
_TOOL_SCHEMAS: dict[str, list[dict]] = {}


def initialize(
    brave_api_key: str = "",
    google_credentials_path=None,
    google_token_path=None,
    db_path=None,
    user_timezone: str = "America/Detroit",
    memory_store=None,
) -> None:
    """Register all tool implementations. Call once at startup."""
    global _TOOL_IMPLEMENTATIONS, _TOOL_SCHEMAS

    # CAPTAIN
    _TOOL_IMPLEMENTATIONS.update(CAPTAIN_TOOL_MAP)
    _TOOL_SCHEMAS["CAPTAIN"] = CAPTAIN_TOOL_SCHEMAS

    # SCOUT — bind Brave Search key (1,000 free searches/month)
    scout_map = make_scout_tool_map(brave_api_key)
    _TOOL_IMPLEMENTATIONS.update(scout_map)
    _TOOL_SCHEMAS["SCOUT"] = SCOUT_TOOL_SCHEMAS

    # TAMARA — Gmail (requires Google credentials)
    if google_credentials_path is not None and google_token_path is not None:
        tamara_map = make_tamara_tool_map(google_credentials_path, google_token_path)
        _TOOL_IMPLEMENTATIONS.update(tamara_map)
        _TOOL_SCHEMAS["TAMARA"] = TAMARA_TOOL_SCHEMAS
    else:
        _TOOL_SCHEMAS["TAMARA"] = []

    # HELEN — Calendar + personal tools
    if (
        google_credentials_path is not None
        and google_token_path is not None
        and db_path is not None
    ):
        from pathlib import Path
        helen_map = make_helen_tool_map(
            google_credentials_path,
            google_token_path,
            Path(db_path),
            user_timezone,
        )
        _TOOL_IMPLEMENTATIONS.update(helen_map)
        _TOOL_SCHEMAS["HELEN"] = HELEN_TOOL_SCHEMAS
    else:
        _TOOL_SCHEMAS["HELEN"] = []

    # BOWEN — memory search + task management
    if db_path is not None and memory_store is not None:
        from pathlib import Path
        bowen_map = make_bowen_tool_map(Path(db_path), memory_store)
        _TOOL_IMPLEMENTATIONS.update(bowen_map)
        _TOOL_SCHEMAS["BOWEN"] = BOWEN_TOOL_SCHEMAS
    else:
        _TOOL_SCHEMAS["BOWEN"] = []


def call_tool(agent_name: str, tool_name: str, **kwargs) -> Any:
    """Execute a tool, enforcing per-agent permissions and input validation."""
    # Permission check
    allowed = TOOL_REGISTRY.get(agent_name, [])
    if tool_name not in allowed:
        return {
            "success": False,
            "error": f"{agent_name} is not permitted to call '{tool_name}'. Allowed: {allowed}",
        }

    # Implementation check
    fn = _TOOL_IMPLEMENTATIONS.get(tool_name)
    if fn is None:
        return {
            "success": False,
            "error": f"Tool '{tool_name}' not yet implemented (check Google OAuth setup).",
        }

    # Input validation against schema
    schemas = _TOOL_SCHEMAS.get(agent_name, [])
    schema = next((s for s in schemas if s["name"] == tool_name), None)
    if schema:
        validation_error = _validate_inputs(tool_name, schema, kwargs)
        if validation_error:
            return {"success": False, "error": validation_error}

    try:
        return fn(**kwargs)
    except TypeError as e:
        return {"success": False, "error": f"Invalid arguments for '{tool_name}': {e}"}
    except Exception as e:
        return {"success": False, "error": f"Tool '{tool_name}' failed: {type(e).__name__}: {e}"}


def _validate_inputs(tool_name: str, schema: dict, kwargs: dict) -> str | None:
    """Validate kwargs against the tool's input_schema. Returns error string or None."""
    input_schema = schema.get("input_schema", {})
    required = input_schema.get("required", [])
    properties = input_schema.get("properties", {})

    # Check required fields are present and non-empty
    for field in required:
        if field not in kwargs:
            return f"'{tool_name}' missing required field: '{field}'"
        val = kwargs[field]
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"'{tool_name}' field '{field}' must not be empty"

    # Check types for known fields
    for field, val in kwargs.items():
        if field not in properties:
            continue  # extra kwargs are ok
        expected = properties[field].get("type")
        if expected == "string" and not isinstance(val, str):
            return f"'{tool_name}' field '{field}' must be a string, got {type(val).__name__}"
        if expected == "integer" and not isinstance(val, int):
            return f"'{tool_name}' field '{field}' must be an integer, got {type(val).__name__}"
        if expected == "array" and not isinstance(val, list):
            return f"'{tool_name}' field '{field}' must be a list, got {type(val).__name__}"

    # Sanity limits on string lengths
    for field, val in kwargs.items():
        if isinstance(val, str) and len(val) > 100_000:
            return f"'{tool_name}' field '{field}' exceeds 100K character limit"

    return None


def get_schemas(agent_name: str) -> list[dict]:
    """Return Anthropic tool schemas for this agent's allowed tools."""
    return _TOOL_SCHEMAS.get(agent_name, [])
