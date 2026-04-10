"""
api/admin.py — Admin endpoints (Praise-only).

All routes require X-Admin-Key header matching config.ADMIN_API_KEY.
Mounted at /api/admin in main.py.

POST /api/admin/users               — create a new user (returns API key once)
GET  /api/admin/users               — list all users
POST /api/admin/users/{id}/regen    — regenerate a user's API key
GET  /api/admin/users/active        — currently connected users
POST /api/admin/knowledge           — add a line to shared_knowledge.md
GET  /api/admin/knowledge           — return current shared knowledge
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin")

SHARED_KNOWLEDGE_PATH = Path(__file__).parent.parent / "memory" / "shared_knowledge.md"


# ── Auth ──────────────────────────────────────────────────────────────────────

def _require_admin(request: Request, x_admin_key: Optional[str] = Header(default=None)) -> None:
    config = request.app.state.config
    expected = config.ADMIN_API_KEY
    if not expected:
        raise HTTPException(status_code=503, detail="Admin key not configured")
    if x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Invalid admin key")


# ── Request models ────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    display_name: str


class KnowledgeRequest(BaseModel):
    entry: str           # single paragraph or insight to add
    category: str = ""   # optional category label


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/users")
async def create_user(body: CreateUserRequest, request: Request,
                      x_admin_key: Optional[str] = Header(default=None)) -> dict:
    _require_admin(request, x_admin_key)
    user_manager = request.app.state.user_manager

    try:
        result = await user_manager.create_user(body.username, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    logger.info(f"Admin created user: {result['username']} ({result['user_id']})")
    return {
        "user_id":      result["user_id"],
        "username":     result["username"],
        "display_name": result["display_name"],
        "api_key":      result["api_key"],   # shown once — not stored in plaintext
        "note":         "Save this API key now. It cannot be recovered.",
    }


@router.get("/users")
async def list_users(request: Request,
                     x_admin_key: Optional[str] = Header(default=None)) -> dict:
    _require_admin(request, x_admin_key)
    user_manager = request.app.state.user_manager
    multi_store = request.app.state.multi_store

    users = await user_manager.list_users()
    active = multi_store.active_users()

    for u in users:
        u["connected"] = u["id"] in active

    return {"users": users, "total": len(users)}


@router.post("/users/{user_id}/regen")
async def regen_key(user_id: str, request: Request,
                    x_admin_key: Optional[str] = Header(default=None)) -> dict:
    _require_admin(request, x_admin_key)
    user_manager = request.app.state.user_manager

    new_key = await user_manager.regenerate_key(user_id)
    if new_key is None:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"Admin regenerated key for {user_id}")
    return {
        "user_id": user_id,
        "api_key": new_key,
        "note":    "Previous key is now invalid. Save this key.",
    }


@router.get("/users/active")
async def active_users(request: Request,
                       x_admin_key: Optional[str] = Header(default=None)) -> dict:
    _require_admin(request, x_admin_key)
    multi_store = request.app.state.multi_store
    return {"active_users": multi_store.active_users()}


# ── Shared knowledge ──────────────────────────────────────────────────────────

@router.post("/knowledge")
async def add_knowledge(body: KnowledgeRequest, request: Request,
                        x_admin_key: Optional[str] = Header(default=None)) -> dict:
    """
    Add an entry to shared_knowledge.md — visible to ALL users' agents.
    This is the mechanism for growing the shared BOWEN brain.
    Commit shared_knowledge.md to git to make it permanent.
    """
    _require_admin(request, x_admin_key)

    SHARED_KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)

    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    category_line = f"[{body.category}] " if body.category else ""
    entry_block = f"\n## {category_line}{ts}\n{body.entry.strip()}\n"

    with open(SHARED_KNOWLEDGE_PATH, "a") as f:
        f.write(entry_block)

    logger.info(f"Shared knowledge updated ({len(body.entry)} chars)")
    return {"status": "added", "entry_length": len(body.entry)}


@router.get("/knowledge")
async def get_knowledge(request: Request,
                        x_admin_key: Optional[str] = Header(default=None)) -> dict:
    _require_admin(request, x_admin_key)

    if not SHARED_KNOWLEDGE_PATH.exists():
        return {"content": "", "size": 0}

    content = SHARED_KNOWLEDGE_PATH.read_text(errors="replace")
    return {"content": content, "size": len(content)}
