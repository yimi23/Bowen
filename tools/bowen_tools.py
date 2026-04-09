"""
tools/bowen_tools.py — BOWEN's own tools: memory search and task management.

BOWEN uses these to surface relevant context and track delegated work without
relying on sub-agents. All implementations are synchronous (called from
asyncio.to_thread in base.py's tool_use_loop).

memory_search  — semantic search over ChromaDB (SentenceTransformer)
task_create    — create a task row in SQLite
task_list      — list open tasks from SQLite
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


BOWEN_TOOL_SCHEMAS = [
    {
        "name": "memory_search",
        "description": (
            "Search BOWEN's semantic memory for relevant context, past decisions, "
            "or Praise's preferences. Use when you need background before responding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in memory",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "task_create",
        "description": (
            "Create a task to track delegated work or action items. "
            "Use after routing work to a sub-agent so nothing gets dropped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title of the task",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context or details",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "task_list",
        "description": (
            "List all open tasks. Use before responding to give Praise a status overview "
            "or to check what's already in flight before creating a duplicate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def make_bowen_tool_map(db_path: Path, memory_store: Any) -> dict:
    """
    Returns BOWEN tool implementations.
    - memory_search uses memory_store.search() directly (sync ChromaDB call).
    - task_create / task_list open their own sync SQLite connection
      (safe since these run in asyncio.to_thread, off the event loop).
    """

    def memory_search(query: str) -> dict:
        results = memory_store.search(query=query, top_k=5, min_relevance=0.65)
        return {
            "success": True,
            "results": results if results else "No relevant memories found.",
        }

    def task_create(title: str, context: str = "") -> dict:
        import sqlite3
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute(
                "INSERT INTO tasks (title, agent, context, topic_id, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (title, "BOWEN", context, "default", now, now),
            )
            conn.commit()
            return {"success": True, "task_id": cursor.lastrowid, "title": title}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def task_list() -> dict:
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, title, agent, status, context, created_at FROM tasks "
                "WHERE status NOT IN ('done', 'cancelled') ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
            tasks = [dict(r) for r in rows]
            return {"success": True, "tasks": tasks, "count": len(tasks)}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    return {
        "memory_search": memory_search,
        "task_create": task_create,
        "task_list": task_list,
    }
