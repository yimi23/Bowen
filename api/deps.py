"""
api/deps.py — FastAPI dependencies for per-user authentication.

REST endpoints that touch user data (memory, topics, conversations) must use
get_user_memory() to authenticate the caller and get their MemoryStore.

Usage:
    from api.deps import get_user_memory

    @router.get("/profile")
    async def get_profile(
        memory: MemoryStore = Depends(get_user_memory),
    ) -> dict:
        return {"profile": memory.get_core_memory()}
"""

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from memory.store import MemoryStore

logger = logging.getLogger(__name__)


async def get_user_memory(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
) -> MemoryStore:
    """
    Authenticate via X-Api-Key header and return the caller's MemoryStore.

    Raises 401 if the key is missing or invalid.
    Raises 503 if the user's memory store cannot be initialized.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="X-Api-Key header required. Use your BOWEN API key.",
        )

    user_manager = request.app.state.user_manager
    multi_store  = request.app.state.multi_store

    user = await user_manager.authenticate(x_api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    # Fast path: memory already cached (after at least one WS connection)
    memory = multi_store.get_cached(user["id"])
    if memory is not None:
        return memory

    # Slow path: first REST-only access — initialize memory on demand
    try:
        memory = await multi_store.get_or_create(
            user["id"],
            user.get("username", ""),
            user.get("display_name", ""),
        )
        return memory
    except Exception as e:
        logger.error(
            "Failed to initialize memory for user %s: %s: %s",
            user["id"], type(e).__name__, e,
        )
        raise HTTPException(
            status_code=503,
            detail="Memory store unavailable. Try again shortly.",
        )
