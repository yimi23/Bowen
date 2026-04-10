"""
api/memory.py — Memory read endpoints.
GET /api/memory/profile    — user_profile.md contents
GET /api/memory/search     — semantic search over ChromaDB
GET /api/memory/stats      — ChromaDB count + task counts

All endpoints require X-Api-Key header authentication and operate on the
authenticated user's memory store — not the global admin store.
"""

import asyncio

from fastapi import APIRouter, Depends, Query

from api.deps import get_user_memory
from memory.store import MemoryStore

router = APIRouter(prefix="/api/memory")


@router.get("/profile")
async def get_profile(
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    """Return the authenticated user's user_profile.md (always-on core memory)."""
    return {"profile": memory.get_core_memory()}


@router.get("/search")
async def search_memory(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(8, ge=1, le=20),
    min_relevance: float = Query(0.5, ge=0.0, le=1.0),
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    """Semantic search across the authenticated user's memories."""
    results = await asyncio.to_thread(
        memory.search, q, top_k, min_relevance
    )
    return {"query": q, "results": results or "No memories found."}


@router.get("/stats")
async def get_stats(
    memory: MemoryStore = Depends(get_user_memory),
) -> dict:
    """Dashboard stats: memory count, open tasks, conversation count."""
    return await memory.get_stats()
