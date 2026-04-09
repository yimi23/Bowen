"""
api/gateway.py — WebSocket chat gateway.
Endpoint: ws://localhost:8000/ws/chat

Message protocol (client → server):
  {"type": "message", "content": str, "topic_id": str, "conversation_id": str}
  {"type": "ping"}

Message protocol (server → client):
  {"type": "routing",     "from": "user", "to": str}              — routing decision
  {"type": "chunk",       "agent": str, "content": str}           — streaming text token
  {"type": "tool_call",   "agent": str, "tool": str, "args": dict} — tool invoked
  {"type": "tool_result", "agent": str, "tool": str, "status": str, "preview": str}
  {"type": "done",        "agent": str}                            — turn complete
  {"type": "error",       "message": str}                         — agent error
  {"type": "pong"}

Each WebSocket connection gets its own conversation_id (mapped to a topic).
Multiple connections can be open simultaneously (different browser tabs / Tauri panels).
"""

from __future__ import annotations

import asyncio
import uuid
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.base import SendFn

router = APIRouter()

# Maximum seconds to wait for an agent response (tool chains can be long)
AGENT_TIMEOUT = 120


async def _drain_bus(agents: dict, bus, send: SendFn, depth: int = 0) -> None:
    """
    Process inter-agent bus messages generated during a turn.
    Mirrors clawdbot.py drain_bus() but uses WebSocket send instead of print.
    """
    if depth > 10:
        return

    pending = await bus.drain_all()
    if not pending:
        return

    for msg in pending:
        if msg.requires_approval:
            # In WebSocket mode, approval is surfaced to the UI as a special event
            await send({
                "type": "approval_required",
                "from": msg.sender,
                "to": msg.recipient,
                "action": getattr(msg.payload, "action_type", "unknown"),
                "description": getattr(msg.payload, "description", str(msg.payload)[:120]),
                "correlation_id": msg.correlation_id,
            })
            # Skip — UI must send an approval response (future Phase 6 feature)
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
    """
    One WebSocket connection = one active session.
    Conversation_id is sent by the client (or generated if missing).
    All turns within the connection share the same conversation_id.
    """
    await websocket.accept()

    # Pull app state — populated by lifespan in main.py
    agents = websocket.app.state.agents
    memory = websocket.app.state.memory
    bus = websocket.app.state.bus
    config = websocket.app.state.config

    # Active conversation — client sends conversation_id to resume, or we create one
    active_conversation_id: Optional[str] = None
    active_topic_id: str = "default"

    async def send(data: dict) -> None:
        """Send JSON event to the WebSocket client."""
        try:
            await websocket.send_json(data)
        except Exception:
            pass  # Client disconnected mid-stream — ignore

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "message")

            # ── Ping / keepalive ──────────────────────────────────────────────
            if msg_type == "ping":
                await send({"type": "pong"})
                continue

            # ── Chat message ──────────────────────────────────────────────────
            if msg_type != "message":
                continue

            content = msg.get("content", "").strip()
            if not content:
                continue

            topic_id = msg.get("topic_id", "default")
            conversation_id = msg.get("conversation_id", "")

            # Create or reuse conversation
            if conversation_id:
                active_conversation_id = conversation_id
                active_topic_id = topic_id
            else:
                active_conversation_id = await memory.create_conversation(
                    topic_id=topic_id,
                    title=content[:60],
                )
                active_topic_id = topic_id
                # Tell client the new conversation ID so it can persist it
                await send({
                    "type": "conversation_created",
                    "conversation_id": active_conversation_id,
                    "topic_id": active_topic_id,
                })

            # Bind all agents to this conversation
            for agent in agents.values():
                agent.set_session(active_conversation_id, topic_id=active_topic_id)

            # ── Route → agent → stream ────────────────────────────────────────

            # Routing (capped at 10s)
            try:
                async with asyncio.timeout(10):
                    target_name = await agents["BOWEN"].route(content)
            except (asyncio.TimeoutError, Exception):
                target_name = "BOWEN"

            await send({"type": "routing", "from": "user", "to": target_name})

            # Agent responds with streaming via send callback
            try:
                async with asyncio.timeout(AGENT_TIMEOUT):
                    await agents[target_name].respond(content, send=send)
            except asyncio.TimeoutError:
                await send({"type": "error", "message": f"{target_name} timed out after {AGENT_TIMEOUT}s"})
            except Exception as e:
                await send({"type": "error", "message": f"{target_name}: {type(e).__name__}: {e}"})

            # Process any inter-agent messages this turn generated
            await _drain_bus(agents, bus, send)

            # Signal turn complete
            await send({"type": "done", "agent": target_name})

    except WebSocketDisconnect:
        # Clean up conversation on disconnect
        if active_conversation_id:
            await memory.end_conversation(active_conversation_id)
