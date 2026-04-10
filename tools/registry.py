"""
tools/registry.py — Per-agent tool enforcement + schema lookup.

Agents cannot call tools outside their allowed set (TOOL_REGISTRY).
Global registry is initialized once at startup via initialize().
Per-connection UserRegistry overrides DB-sensitive tools with user-specific versions.

Architecture:
  - TOOL_REGISTRY        : agent → allowed tool names (permission whitelist)
  - _TOOL_IMPLEMENTATIONS: tool name → callable (global, stateless tools)
  - _TOOL_SCHEMAS        : agent name → [Anthropic schema dicts]
  - _build_user_tool_maps: shared factory — called by both initialize() and UserRegistry
  - UserRegistry         : per-connection, wraps _build_user_tool_maps with user context
"""

import logging
from typing import Any, Callable

from agents.constants import AgentName
from tools.captain_tools import CAPTAIN_TOOL_MAP, CAPTAIN_TOOL_SCHEMAS, make_captain_dispatch_map
from tools.scout_tools import make_scout_tool_map, SCOUT_TOOL_SCHEMAS
from tools.tamara_tools import make_tamara_tool_map, TAMARA_TOOL_SCHEMAS
from tools.helen_tools import make_helen_tool_map, HELEN_TOOL_SCHEMAS
from tools.bowen_tools import make_bowen_tool_map, BOWEN_TOOL_SCHEMAS

logger = logging.getLogger(__name__)

# ── Permission whitelist ───────────────────────────────────────────────────────
# Defines which tools each agent is allowed to call.
# Any call not in this list is rejected before execution.

TOOL_REGISTRY: dict[str, list[str]] = {
    AgentName.CAPTAIN: [
        "execute_code", "read_file", "write_file", "run_shell", "web_fetch",
        "dispatch_create", "dispatch_update", "dispatch_list",
    ],
    AgentName.SCOUT:  ["web_search", "web_fetch", "document_parse", "structured_extract"],
    AgentName.TAMARA: ["gmail_read", "gmail_send", "gmail_draft"],
    AgentName.HELEN:  ["calendar_list", "calendar_create", "task_create", "bible_check", "notify", "daily_briefing"],
    AgentName.BOWEN:  ["memory_search", "task_create", "task_list"],
    AgentName.DEVOPS: ["execute_code", "read_file", "run_shell", "web_fetch"],
}

_TOOL_IMPLEMENTATIONS: dict[str, Callable] = {}
_TOOL_SCHEMAS: dict[str, list[dict]] = {}


# ── Shared user-scoped tool factory ───────────────────────────────────────────

def _build_user_tool_maps(
    db_path,
    memory_store,
    google_credentials_path,
    google_token_path,
    user_timezone: str,
) -> tuple[dict, dict]:
    """
    Build tool implementations and schemas for a specific user's DB + credentials.
    Returns (impls, schemas).

    Called by both initialize() (global/admin) and UserRegistry (per-connection).
    This is the single source of truth for user-scoped tool construction —
    avoids duplicating logic in two places.
    """
    from pathlib import Path as _Path

    impls: dict[str, Callable] = {}
    schemas: dict[str, list] = {}

    # BOWEN tools — memory search + task management on user's DB
    if db_path is not None and memory_store is not None:
        bowen_map = make_bowen_tool_map(_Path(db_path), memory_store)
        impls.update(bowen_map)
        schemas[AgentName.BOWEN] = BOWEN_TOOL_SCHEMAS
    else:
        schemas[AgentName.BOWEN] = []

    # CAPTAIN dispatch tools — task tracking on user's DB
    if db_path is not None:
        dispatch_map = make_captain_dispatch_map(_Path(db_path))
        impls.update(dispatch_map)

    # HELEN tools — calendar + Bible + tasks on user's DB
    creds_ok = (
        google_credentials_path is not None
        and google_token_path is not None
        and _Path(google_credentials_path).exists()
    )
    if creds_ok and db_path is not None:
        helen_map = make_helen_tool_map(
            _Path(google_credentials_path),
            _Path(google_token_path),
            _Path(db_path),
            user_timezone,
        )
        impls.update(helen_map)
        schemas[AgentName.HELEN] = HELEN_TOOL_SCHEMAS
    else:
        schemas[AgentName.HELEN] = []

    # TAMARA — Gmail (bound to the provided Google credentials)
    if creds_ok:
        tamara_map = make_tamara_tool_map(
            _Path(google_credentials_path),
            _Path(google_token_path),
        )
        impls.update(tamara_map)
        schemas[AgentName.TAMARA] = TAMARA_TOOL_SCHEMAS
    else:
        schemas[AgentName.TAMARA] = []

    return impls, schemas


# ── Global registry initialization ────────────────────────────────────────────

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

    # CAPTAIN base tools (stateless: execute_code, read_file, write_file, run_shell, web_fetch)
    _TOOL_IMPLEMENTATIONS.update(CAPTAIN_TOOL_MAP)
    _TOOL_SCHEMAS[AgentName.CAPTAIN] = CAPTAIN_TOOL_SCHEMAS

    # SCOUT — web search (Brave key bound at startup)
    scout_map = make_scout_tool_map(brave_api_key)
    _TOOL_IMPLEMENTATIONS.update(scout_map)
    _TOOL_SCHEMAS[AgentName.SCOUT] = SCOUT_TOOL_SCHEMAS

    # DEVOPS shares CAPTAIN's read-only tools (no write_file, no dispatch)
    _TOOL_SCHEMAS[AgentName.DEVOPS] = [
        s for s in CAPTAIN_TOOL_SCHEMAS
        if s["name"] in ("execute_code", "read_file", "run_shell", "web_fetch")
    ]

    # User-scoped tools (BOWEN memory, CAPTAIN dispatch, HELEN calendar, TAMARA Gmail)
    user_impls, user_schemas = _build_user_tool_maps(
        db_path=db_path,
        memory_store=memory_store,
        google_credentials_path=google_credentials_path,
        google_token_path=google_token_path,
        user_timezone=user_timezone,
    )
    _TOOL_IMPLEMENTATIONS.update(user_impls)
    _TOOL_SCHEMAS.update(user_schemas)

    logger.info(
        "Tool registry initialized",
        extra={
            "tools": len(_TOOL_IMPLEMENTATIONS),
            "agents": list(_TOOL_SCHEMAS.keys()),
        },
    )


# ── Tool execution ────────────────────────────────────────────────────────────

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

    # Input validation
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
        logger.error(
            "Tool execution error",
            extra={"agent": agent_name, "tool": tool_name, "err": f"{type(e).__name__}: {e}"},
        )
        return {"success": False, "error": f"Tool '{tool_name}' failed: {type(e).__name__}: {e}"}


def _validate_inputs(tool_name: str, schema: dict, kwargs: dict) -> str | None:
    """Validate kwargs against the tool's input_schema. Returns error string or None."""
    input_schema = schema.get("input_schema", {})
    required     = input_schema.get("required", [])
    properties   = input_schema.get("properties", {})

    for field in required:
        if field not in kwargs:
            return f"'{tool_name}' missing required field: '{field}'"
        val = kwargs[field]
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"'{tool_name}' field '{field}' must not be empty"

    for field, val in kwargs.items():
        if field not in properties:
            continue
        expected = properties[field].get("type")
        if expected == "string" and not isinstance(val, str):
            return f"'{tool_name}' field '{field}' must be a string, got {type(val).__name__}"
        if expected == "integer" and not isinstance(val, int):
            return f"'{tool_name}' field '{field}' must be an integer, got {type(val).__name__}"
        if expected == "array" and not isinstance(val, list):
            return f"'{tool_name}' field '{field}' must be a list, got {type(val).__name__}"

    for field, val in kwargs.items():
        if isinstance(val, str) and len(val) > 100_000:
            return f"'{tool_name}' field '{field}' exceeds 100K character limit"

    return None


def get_schemas(agent_name: str) -> list[dict]:
    """Return Anthropic tool schemas for this agent's allowed tools."""
    return _TOOL_SCHEMAS.get(agent_name, [])


# ── UserRegistry ──────────────────────────────────────────────────────────────

class UserRegistry:
    """
    Per-connection tool registry. User-specific tools (memory search, task
    management, calendar, Gmail) operate on the correct user's DB and credentials.
    Stateless tools (SCOUT web search, DEVOPS analysis) fall through to the
    global registry implementations.

    Built once per WebSocket connection in gateway.py:
        reg = UserRegistry(user_id, user_db_path, user_memory_store, config)
    """

    def __init__(self, user_id: str, db_path, memory_store, config) -> None:
        self._user_id = user_id
        self._impls: dict[str, Callable] = {}
        self._schemas: dict[str, list] = {}
        self._build(db_path, memory_store, config)

    def _build(self, db_path, memory_store, config) -> None:
        """Use the shared factory — no duplication of tool map construction logic."""
        impls, schemas = _build_user_tool_maps(
            db_path=db_path,
            memory_store=memory_store,
            google_credentials_path=config.GOOGLE_CREDENTIALS_PATH,
            google_token_path=config.GOOGLE_TOKEN_PATH,
            user_timezone=config.USER_TIMEZONE,
        )
        self._impls.update(impls)
        self._schemas.update(schemas)

    def call_tool(self, agent_name: str, tool_name: str, **kwargs) -> Any:
        """
        Execute a tool with user-specific context.
        User-specific implementations take precedence over global ones.
        Falls back to global registry for stateless tools (SCOUT, DEVOPS CAPTAIN base).
        """
        # Permission check (same whitelist for all users)
        allowed = TOOL_REGISTRY.get(agent_name, [])
        if tool_name not in allowed:
            return {
                "success": False,
                "error": (
                    f"{agent_name} is not permitted to call '{tool_name}'. "
                    f"Allowed: {allowed}"
                ),
            }

        # User-specific implementation first; fall back to global
        fn = self._impls.get(tool_name) or _TOOL_IMPLEMENTATIONS.get(tool_name)
        if fn is None:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not available (check Google OAuth setup).",
            }

        # Schema validation
        schemas = self.get_schemas(agent_name)
        schema  = next((s for s in schemas if s["name"] == tool_name), None)
        if schema:
            err = _validate_inputs(tool_name, schema, kwargs)
            if err:
                return {"success": False, "error": err}

        try:
            return fn(**kwargs)
        except TypeError as e:
            return {"success": False, "error": f"Invalid arguments for '{tool_name}': {e}"}
        except Exception as e:
            logger.error(
                "UserRegistry tool error",
                extra={
                    "user_id": self._user_id,
                    "agent": agent_name,
                    "tool": tool_name,
                    "err": f"{type(e).__name__}: {e}",
                },
            )
            return {"success": False, "error": f"Tool '{tool_name}' failed: {type(e).__name__}: {e}"}

    def get_schemas(self, agent_name: str) -> list[dict]:
        """User-specific schemas first, then global fallback."""
        if agent_name in self._schemas:
            return self._schemas[agent_name]
        return _TOOL_SCHEMAS.get(agent_name, [])
