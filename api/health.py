"""
api/health.py — Health check endpoint.
Tauri / start.sh polls GET /api/health to wait for the server to be ready.

Returns:
  status:    "ok" when fully booted
  agents:    list of loaded agent names
  memory:    ChromaDB memory count
  services:  API key presence from config.status()
  probes:    Live results from keep_alive service (Anthropic, ChromaDB, Groq)
"""

import logging
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/health")
async def health(request: Request) -> dict:
    """Liveness + readiness check. Includes keep-alive probe results."""
    config  = request.app.state.config
    memory  = request.app.state.memory
    agents  = request.app.state.agents
    ka      = getattr(request.app.state, "keep_alive", None)

    probes = ka.get_status() if ka else {}

    return {
        "status": "ok",
        "agents": list(agents.keys()),
        "memory_count": memory._collection.count(),
        "services": config.status(),
        "probes": probes,
    }
