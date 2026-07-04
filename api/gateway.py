"""
api/gateway.py — WebSocket chat gateway.
Endpoint: ws://localhost:8000/ws/chat

Auth: none — hardcoded to usr_admin (Praise Oyimi). Single-user local setup.

Message protocol (client → server):
  {"type": "message", "content": str, "topic_id": str, "conversation_id": str}
  {"type": "planning_answer", "question": str, "answer": str}
  {"type": "approval_response", "correlation_id": str, "approved": bool}
  {"type": "ping"}

Message protocol (server → client):
  {"type": "auth_ok",     "user": str}
  {"type": "routing",     "from": "user", "to": str}
  {"type": "chunk",       "agent": str, "content": str}
  {"type": "tool_call",   "agent": str, "tool": str, "args": dict}
  {"type": "tool_result", "agent": str, "tool": str, "status": str, "preview": str}
  {"type": "done",        "agent": str}
  {"type": "error",       "message": str}
  {"type": "pong"}

Phase A:
  - session_context dict accumulates cross-turn state
  - JSONL handoff log at /Volumes/S1/bowen/logs/handoffs.jsonl
  - HandoffPayload routing in _drain_bus
Phase B:
  - Live bus loop runs as a background asyncio task for the duration of the session
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.base import SendFn
from agents.bowen import BOWENAgent
from agents.captain import CaptainAgent
from agents.constants import AgentName
from agents.devops import DevOpsAgent
from agents.scout import ScoutAgent
from agents.tamara import TamaraAgent
from agents.helen import HelenAgent
from agents.geni import GENIAgent
from agents.planner import Planner, build_enriched_prompt
from bus.message_bus import MessageBus
from bus.schema import HandoffPayload, ReviewPayload
from memory.pipeline import run_sleep_pipeline
from services.monitor import monitor
from tools.registry import UserRegistry

logger = logging.getLogger(__name__)
router = APIRouter()

AGENT_TIMEOUT = 120
_LOGS_DIR = Path("/Volumes/S1/bowen/logs")
_HANDOFF_LOG = _LOGS_DIR / "handoffs.jsonl"


# ── Handoff JSONL logger ──────────────────────────────────────────────────────

def _log_handoff(
    from_agent: str,
    to_agent: str,
    payload_type: str,
    session_id: str,
    latency_ms: int,
    outcome: str,
) -> None:
    """Append one handoff event to the JSONL log. Fire-and-forget; errors are suppressed."""
    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": session_id[:8] if session_id else "",
            "from": from_agent,
            "to": to_agent,
            "payload": payload_type,
            "latency_ms": latency_ms,
            "outcome": outcome,
        }
        with _HANDOFF_LOG.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ── Agent factory ─────────────────────────────────────────────────────────────

def _make_agents(config, user_memory, user_registry) -> tuple[dict, MessageBus]:
    """Create fresh agent instances for one user connection."""
    bus = MessageBus()
    agents = {
        AgentName.BOWEN:   BOWENAgent(config, user_memory, bus),
        AgentName.CAPTAIN: CaptainAgent(config, user_memory, bus, user_registry),
        AgentName.DEVOPS:  DevOpsAgent(config, user_memory, bus, user_registry),
        AgentName.SCOUT:   ScoutAgent(config, user_memory, bus, user_registry),
        AgentName.TAMARA:  TamaraAgent(config, user_memory, bus, user_registry),
        AgentName.HELEN:   HelenAgent(config, user_memory, bus, user_registry),
        AgentName.GENI:    GENIAgent(config, user_memory, bus, user_registry),
    }
    return agents, bus


# ── Bus drain (handles one pass of all pending messages) ─────────────────────

async def _drain_bus(agents: dict, bus, send: SendFn, session_id: str = "", depth: int = 0) -> None:
    if depth > 10:
        return

    pending = await bus.drain_all()
    if not pending:
        return

    for msg in pending:
        if msg.requires_approval:
            await send({
                "type": "approval_required",
                "from": msg.sender,
                "to": msg.recipient,
                "action": getattr(msg.payload, "action_type", "unknown"),
                "description": getattr(msg.payload, "description", str(msg.payload)[:120]),
                "correlation_id": msg.correlation_id,
            })
            continue

        target = agents.get(msg.recipient)
        if not target:
            continue

        await send({"type": "routing", "from": msg.sender, "to": msg.recipient})

        t0 = time.monotonic()
        outcome = "ok"
        try:
            async with asyncio.timeout(AGENT_TIMEOUT):
                await target.handle(msg, send=send)
        except asyncio.TimeoutError:
            outcome = "timeout"
            await send({"type": "error", "message": f"{msg.recipient} timed out"})
        except Exception as e:
            outcome = f"error:{type(e).__name__}"
            await send({"type": "error", "message": f"{msg.recipient} error: {type(e).__name__}: {e}"})
        finally:
            latency = round((time.monotonic() - t0) * 1000)
            _log_handoff(
                from_agent=msg.sender,
                to_agent=msg.recipient,
                payload_type=type(msg.payload).__name__,
                session_id=session_id,
                latency_ms=latency,
                outcome=outcome,
            )

    await _drain_bus(agents, bus, send, session_id, depth=depth + 1)


# ── Live bus loop (Phase B: background task) ──────────────────────────────────

async def _bus_loop(agents: dict, bus, send: SendFn, session_id: str, stop: asyncio.Event) -> None:
    """
    Continuously drain the bus while the WebSocket session is active.
    Runs as a background asyncio task — replaced the post-turn drain pattern.
    """
    while not stop.is_set():
        try:
            if bus.any_pending():
                await _drain_bus(agents, bus, send, session_id)
            else:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Bus loop error: %s", e)
            await asyncio.sleep(0.5)


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()

    config      = websocket.app.state.config
    multi_store = websocket.app.state.multi_store

    # ── Tenant authentication ─────────────────────────────────────────────────
    # Every session binds to exactly one tenant's isolated stores. The key in
    # ?key= decides which. No-key connections are allowed ONLY when no admin
    # key is configured (fully local, single-tenant dev mode).
    from memory.users import RateLimited

    api_key = websocket.query_params.get("key", "")
    if api_key:
        try:
            user = await websocket.app.state.user_manager.authenticate(api_key)
        except RateLimited:
            await websocket.close(code=4429, reason="rate limit exceeded")
            return
        if not user:
            await websocket.close(code=4401, reason="invalid API key")
            return
        user_id      = user["id"]
        username     = user.get("username", user_id)
        display_name = user.get("display_name", username)
    elif not config.ADMIN_API_KEY:
        user_id, username, display_name = "usr_admin", "praise", "Praise Oyimi"
    else:
        await websocket.close(code=4401, reason="API key required")
        return

    # ── Per-tenant memory ─────────────────────────────────────────────────────
    user_memory = await multi_store.get_or_create(
        user_id, username, display_name
    )

    # ── Per-user registry ─────────────────────────────────────────────────────
    user_registry = UserRegistry(
        user_id=user_id,
        db_path=user_memory._db_path,
        memory_store=user_memory,
        config=config,
    )

    # ── Per-connection agents ─────────────────────────────────────────────────
    agents, bus = _make_agents(config, user_memory, user_registry)

    await websocket.send_json({
        "type": "auth_ok",
        "user": display_name,
        "user_id": user_id,
    })

    active_conversation_id: Optional[str] = None
    active_topic_id: str = "default"

    # session_context accumulates cross-turn state (Phase A)
    session_context: dict = {
        "turn_count": 0,
        "agents_used": [],
        "last_agent": None,
    }

    async def send(data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    # ── Live bus loop (Phase B) ───────────────────────────────────────────────
    bus_stop = asyncio.Event()
    bus_task = asyncio.create_task(
        _bus_loop(agents, bus, send, active_conversation_id or "", bus_stop),
        name="bus_loop",
    )

    logger.info("User connected: %s (%s)", display_name, user_id)

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "message")

            if msg_type == "ping":
                await send({"type": "pong"})
                continue

            if msg_type != "message":
                continue

            content = msg.get("content", "").strip()
            if not content:
                continue

            topic_id = msg.get("topic_id", "default")
            conversation_id = msg.get("conversation_id", "")

            if conversation_id:
                active_conversation_id = conversation_id
                active_topic_id = topic_id
            else:
                active_conversation_id = await user_memory.create_conversation(
                    topic_id=topic_id,
                    title=content[:60],
                )
                active_topic_id = topic_id
                await send({
                    "type": "conversation_created",
                    "conversation_id": active_conversation_id,
                    "topic_id": active_topic_id,
                })

            # Update bus loop with current session ID
            bus_task.cancel()
            bus_stop.set()
            bus_stop = asyncio.Event()
            bus_task = asyncio.create_task(
                _bus_loop(agents, bus, send, active_conversation_id or "", bus_stop),
                name="bus_loop",
            )

            for agent in agents.values():
                agent.set_session(active_conversation_id, topic_id=active_topic_id)

            # Update session context
            session_context["turn_count"] += 1

            # Routing
            forced = msg.get("target_agent", "").upper()
            if forced and forced in agents:
                target_name = forced
            else:
                try:
                    async with asyncio.timeout(10):
                        target_name = await agents[AgentName.BOWEN].route(content)
                except (asyncio.TimeoutError, Exception):
                    target_name = AgentName.BOWEN

            session_context["last_agent"] = target_name
            if target_name not in session_context["agents_used"]:
                session_context["agents_used"].append(target_name)

            await send({"type": "routing", "from": "user", "to": target_name})

            # Planning layer
            enriched_content = content
            if target_name in {AgentName.CAPTAIN, AgentName.SCOUT}:
                planner = Planner(config.ANTHROPIC_API_KEY, config.HAIKU_MODEL)
                clarity = await planner.classify(content)
                if clarity == "vague":
                    questions = await planner.get_questions(content)
                    if questions:
                        await send({"type": "planning_start", "agent": "BOWEN"})
                        for q in questions:
                            await send({"type": "chunk", "agent": "BOWEN", "content": f"\n**{q}**\n"})
                            await send({"type": "planning_question", "question": q})
                        await send({"type": "planning_end"})

                        answer_map: dict[str, str] = {}
                        try:
                            async with asyncio.timeout(180):
                                while len(answer_map) < len(questions):
                                    raw_ans = await websocket.receive_text()
                                    try:
                                        ans_msg = json.loads(raw_ans)
                                    except json.JSONDecodeError:
                                        continue
                                    if ans_msg.get("type") == "ping":
                                        await send({"type": "pong"})
                                    elif ans_msg.get("type") == "planning_answer":
                                        q = ans_msg.get("question", "")
                                        answer_map[q] = ans_msg.get("answer", "")
                        except asyncio.TimeoutError:
                            pass

                        qa_pairs = [(q, answer_map.get(q, "")) for q in questions]
                        ctx = Planner.gather_context()
                        enriched_content = build_enriched_prompt(content, qa_pairs, ctx)

            monitored_send = monitor.wrap(
                send,
                session_id=active_conversation_id or "",
                agent=target_name,
            )

            t0 = time.monotonic()
            response_text = ""
            try:
                async with asyncio.timeout(AGENT_TIMEOUT):
                    response_text = await agents[target_name].respond(
                        enriched_content, send=monitored_send
                    ) or ""
            except asyncio.TimeoutError:
                await send({"type": "error", "message": f"{target_name} timed out after {AGENT_TIMEOUT}s"})
            except Exception as e:
                await send({"type": "error", "message": f"{target_name}: {type(e).__name__}: {e}"})
            finally:
                latency = round((time.monotonic() - t0) * 1000)
                _log_handoff("user", target_name, "message", active_conversation_id or "", latency, "ok")

            # done carries the full text so the UI can backfill any reply path
            # that returned without streaming chunks (Remi's empty-stream rule).
            await send({"type": "done", "agent": target_name, "response": response_text})

    except WebSocketDisconnect:
        logger.info("User disconnected: %s (%s)", display_name, user_id)
    finally:
        # Stop live bus loop
        bus_stop.set()
        bus_task.cancel()
        try:
            await bus_task
        except (asyncio.CancelledError, Exception):
            pass

        if active_conversation_id:
            await user_memory.end_conversation(active_conversation_id)
            asyncio.create_task(
                run_sleep_pipeline(
                    user_memory,
                    active_conversation_id,
                    config.ANTHROPIC_API_KEY,
                    config.HAIKU_MODEL,
                ),
                name=f"sleep_pipeline_{(active_conversation_id or 'unknown')[:8]}",
            )
