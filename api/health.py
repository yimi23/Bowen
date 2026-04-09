"""
api/health.py — Health check endpoint.
Tauri calls GET /api/health on startup to wait for the Python server to be ready.
Returns 200 + service status once the server is alive.
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> dict:
    """Liveness + readiness check. Tauri polls this before opening the UI."""
    config = request.app.state.config
    memory = request.app.state.memory
    agents = request.app.state.agents

    return {
        "status": "ok",
        "agents": list(agents.keys()),
        "memory_count": memory._collection.count(),
        "services": config.status(),
    }
