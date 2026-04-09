"""
api/memory.py — Memory read endpoints for the React frontend.
GET /api/memory/profile    — user_profile.md contents
GET /api/memory/search     — semantic search over ChromaDB
GET /api/memory/stats      — ChromaDB count + task counts
"""

from fastapi import APIRouter, Request, Query

router = APIRouter(prefix="/api/memory")


@router.get("/profile")
async def get_profile(request: Request) -> dict:
    """Return the current user_profile.md (always-on core memory)."""
    memory = request.app.state.memory
    return {"profile": memory.get_core_memory()}


@router.get("/search")
async def search_memory(
    request: Request,
    q: str = Query(..., description="Search query"),
    top_k: int = Query(8, ge=1, le=20),
    min_relevance: float = Query(0.5, ge=0.0, le=1.0),
) -> dict:
    """Semantic search across all memories. Returns formatted memory block."""
    memory = request.app.state.memory
    results = memory.search(q, top_k=top_k, min_relevance=min_relevance)
    return {"query": q, "results": results or "No memories found."}


@router.get("/stats")
async def get_stats(request: Request) -> dict:
    """Dashboard stats: memory count, open tasks, conversation count, files generated."""
    memory = request.app.state.memory
    return await memory.get_stats()
