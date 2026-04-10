"""
api/gateway.py — WebSocket chat gateway.
Endpoint: ws://localhost:8000/ws/chat?key=<api_key>

Auth: API key passed as `key` query parameter.
      Server hashes it, looks up in users.db, binds connection to that user.
      Each user gets isolated memory but shares agent code + tools.

Message protocol (client → server):
  {"type": "message", "content": str, "topic_id": str, "conversation_id": str}
  {"type": "ping"}

Message protocol (server → client):
  {"type": "auth_ok",     "user": str}                             — auth successful
  {"type": "routing",     "from": "user", "to": str}              — routing decision
  {"type": "chunk",       "agent": str, "content": str}           — streaming text token
  {"type": "tool_call",   "agent": str, "tool": str, "args": dict}
  {"type": "tool_result", "agent": str, "tool": str, "status": str, "preview": str}
  {"type": "done",        "agent": str}                            — turn complete
  {"type": "error",       "message": str}                         — agent error
  {"type": "pong"}

Each WebSocket connection creates fresh agent instances bound to that user's memory.
The MessageBus is per-connection (not shared across users).
"""

from __future__ import annotations

import asyncio
import uuid
import json
import logging
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
from agents.planner import Planner, build_enriched_prompt
from bus.message_bus import MessageBus
from memory.pipeline import run_sleep_pipeline
from services.monitor import monitor
from tools.registry import UserRegistry

logger = logging.getLogger(__name__)
router = APIRouter()

AGENT_TIMEOUT = 120


def _make_agents(config, user_memory, user_registry) -> dict:
    """Create fresh agent instances for one user connection."""
    bus = MessageBus()
    agents = {
        AgentName.BOWEN:   BOWENAgent(config, user_memory, bus, user_registry),
        AgentName.CAPTAIN: CaptainAgent(config, user_memory, bus, user_registry),
        AgentName.DEVOPS:  DevOpsAgent(config, user_memory, bus, user_registry),
        AgentName.SCOUT:   ScoutAgent(config, user_memory, bus, user_registry),
        AgentName.TAMARA:  TamaraAgent(config, user_memory, bus, user_registry),
        AgentName.HELEN:   HelenAgent(config, user_memory, bus, user_registry),
    }
    return agents, bus


async def _drain_bus(agents: dict, bus, send: SendFn, depth: int = 0) -> None:
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

        try:
            async with asyncio.timeout(AGENT_TIMEOUT):
                await target.handle(msg, send=send)
        except asyncio.TimeoutError:
            await send({"type": "error", "message": f"{msg.recipient} timed out"})
        except Exception as e:
            await send({"type": "error", "message": f"{msg.recipient} error: {type(e).__name__}: {e}"})

    await _drain_bus(agents, bus, send, depth=depth + 1)


@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()

    config       = websocket.app.state.config
    user_manager = websocket.app.state.user_manager
    multi_store  = websocket.app.state.multi_store

    # ── Auth ──────────────────────────────────────────────────────────────────
    api_key = websocket.query_params.get("key", "")
    user = await user_manager.authenticate(api_key)
    if not user:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid or missing API key. Connect with: ws://...?key=<your_key>",
        })
        await websocket.close(code=4001)
        return

    user_id = user["id"]
    display_name = user["display_name"]

    # ── Per-user memory ───────────────────────────────────────────────────────
    user_memory = await multi_store.get_or_create(
        user_id, user["username"], display_name
    )

    # ── Per-user registry (user-specific DB bindings) ─────────────────────────
    user_registry = UserRegistry(
        user_id=user_id,
        db_path=user_memory._db_path,
        memory_store=user_memory,
        config=config,
    )

    # ── Per-connection agents ─────────────────────────────────────────────────
    agents, bus = _make_agents(config, user_memory, user_registry)

    # Tell client auth succeeded
    await websocket.send_json({
        "type": "auth_ok",
        "user": display_name,
        "user_id": user_id,
    })

    active_conversation_id: Optional[str] = None
    active_topic_id: str = "default"

    async def send(data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    logger.info(f"User connected: {display_name} ({user_id})")

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

            for agent in agents.values():
                agent.set_session(active_conversation_id, topic_id=active_topic_id)

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

            try:
                async with asyncio.timeout(AGENT_TIMEOUT):
                    await agents[target_name].respond(enriched_content, send=monitored_send)
            except asyncio.TimeoutError:
                await send({"type": "error", "message": f"{target_name} timed out after {AGENT_TIMEOUT}s"})
            except Exception as e:
                await send({"type": "error", "message": f"{target_name}: {type(e).__name__}: {e}"})

            await _drain_bus(agents, bus, send)
            await send({"type": "done", "agent": target_name})

    except WebSocketDisconnect:
        logger.info(f"User disconnected: {display_name} ({user_id})")
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
