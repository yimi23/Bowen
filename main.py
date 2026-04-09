"""
main.py — FastAPI backend entry point.
Phase 5+: Replaces clawdbot.py's input() loop with WebSocket streaming server.

Run: source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Tauri health check: GET /api/health
WebSocket chat: ws://localhost:8000/ws/chat

Startup sequence:
  1. Config validated (ANTHROPIC_API_KEY required)
  2. MemoryStore initialized (aiosqlite + ChromaDB)
  3. Tool registry initialized (Brave, Google, etc.)
  4. All 5 agents instantiated (shared memory + bus)
  5. APScheduler started (nightly consolidation + HELEN jobs)
  6. FastAPI routers mounted

All agents share a single in-process state — no cross-process coordination needed.
The server is single-user (Praise only), so no auth is implemented at this layer.
"""

from __future__ import annotations

import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging import setup_logging
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from agents.bowen import BOWENAgent
from agents.captain import CaptainAgent
from agents.scout import ScoutAgent
from agents.tamara import TamaraAgent
from agents.helen import HelenAgent
from scheduler.jobs import build_scheduler, wire_helen_jobs
from services.keep_alive import keep_alive
import tools.registry as registry

# Routers
from api.gateway import router as ws_router
from api.health import router as health_router
from api.memory import router as memory_router
from api.topics import router as topics_router

# Initialize logging immediately — before anything else logs
setup_logging(log_level="INFO", log_file="logs/bowen.log")


# ── App-wide state (populated in lifespan) ────────────────────────────────────
# Stored on app.state so routers can access via request.app.state

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: initialize memory, registry, agents, scheduler.
    Shutdown: drain scheduler, close DB.
    """
    config = Config()

    # Validate required keys — fail fast if ANTHROPIC_API_KEY missing
    missing = config.validate()
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    # Memory layer — must open before agents (agents read profile on first respond)
    memory = MemoryStore(config.DB_PATH, config.CHROMA_PATH)
    memory.set_profile_path(config.PROFILE_PATH)
    await memory.initialize()

    # Tool registry — binds API keys into closures, must precede agent instantiation
    registry.initialize(
        brave_api_key=config.BRAVE_API_KEY,
        google_credentials_path=config.GOOGLE_CREDENTIALS_PATH,
        google_token_path=config.GOOGLE_TOKEN_PATH,
        db_path=config.DB_PATH,
        user_timezone=config.USER_TIMEZONE,
        memory_store=memory,
    )

    bus = MessageBus()

    agents = {
        "BOWEN":   BOWENAgent(config, memory, bus),
        "CAPTAIN": CaptainAgent(config, memory, bus),
        "SCOUT":   ScoutAgent(config, memory, bus),
        "TAMARA":  TamaraAgent(config, memory, bus),
        "HELEN":   HelenAgent(config, memory, bus),
    }

    # Scheduler: nightly consolidation (no agents) + HELEN jobs (agent-dependent)
    scheduler = build_scheduler(config, memory)
    wire_helen_jobs(scheduler, agents["HELEN"], config)
    scheduler.start()

    # Keep-alive: background pings Anthropic, ChromaDB, Groq every 60s
    keep_alive.start(config, memory)

    # Store on app.state for router access
    app.state.config = config
    app.state.memory = memory
    app.state.bus = bus
    app.state.agents = agents
    app.state.scheduler = scheduler
    app.state.keep_alive = keep_alive

    import logging
    logging.getLogger(__name__).info("BOWEN server online", extra={
        "ws": "ws://localhost:8000/ws/chat",
        "health": "http://localhost:8000/api/health",
    })
    print("\n\033[1mBOWEN FastAPI server online.\033[0m")
    print(f"  WebSocket: ws://localhost:8000/ws/chat")
    print(f"  Health:    http://localhost:8000/api/health\n")

    yield  # Server runs here

    # Shutdown
    keep_alive.stop()
    scheduler.shutdown(wait=False)
    await memory.close()
    logging.getLogger(__name__).info("BOWEN server shut down cleanly")
    print("\n[BOWEN] Server shut down cleanly.")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BOWEN",
    description="Personal AI chief-of-staff — 5 agents, async, WebSocket streaming",
    version="5.0.0",
    lifespan=lifespan,
)

# CORS — allow Tauri (localhost) and dev React (localhost:3000, localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health_router)
app.include_router(ws_router)
app.include_router(memory_router)
app.include_router(topics_router)
