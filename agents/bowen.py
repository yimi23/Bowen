"""
agents/bowen.py — BOWEN: Lead Orchestrator.
Routes all tasks. Validates critical outputs. Never handles code, research,
messaging, or calendar directly.
"""

from __future__ import annotations

from typing import Optional

from agents.base import BaseAgent, SendFn
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from bus.schema import AgentMessage, TextPayload, ApprovalRequestPayload
from routing import tier1_route, tier2_route
import tools.registry as registry


class BOWENAgent(BaseAgent):
    name = "BOWEN"
    voice_style = "Deep, calm, authoritative. Measured pace. Never wastes words."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus) -> None:
        super().__init__(config, memory, bus)
        self._model = config.HAIKU_MODEL  # voice uses Haiku; text deep work uses Sonnet

    @property
    def base_identity(self) -> str:
        return (
            "You are BOWEN — a lead AI orchestrator and personal chief of staff. "
            "You serve Praise Oyimi, CEO of Twine Campus Inc. "
            "Your voice: deep, calm, authoritative. Measured pace. Never wastes words.\n\n"
            "Your role is to route tasks, synthesize results from sub-agents, and surface "
            "decisions that require Praise's approval. You never write code, do research, "
            "send emails, or manage calendars directly — you delegate those to the right agent.\n\n"
            "Agents under you:\n"
            "  CAPTAIN — code, builds, file ops, shell\n"
            "  SCOUT   — research, web search, competitive analysis\n"
            "  TAMARA  — email, messaging, outbound communications\n"
            "  HELEN   — calendar, reminders, Bible tracking, morning briefing\n\n"
            "When you respond directly, be direct. No filler. Short sentences. Active voice. "
            "No em dashes. No semicolons. No markdown asterisks."
        )

    async def route(self, user_text: str) -> str:
        """
        Two-tier routing:
        Tier 1 — Regex (< 1ms, $0). Returns agent name or None.
        Tier 2 — Haiku tool_choice (300-500ms, ~$0.001). Always returns agent name.
        """
        agent = tier1_route(user_text)
        if agent:
            print(f"  \033[90m[router] tier1 → {agent}\033[0m")
            return agent

        agent, reason = await tier2_route(
            user_text, self.client, self.config.HAIKU_MODEL,
            groq_api_key=self.config.GROQ_API_KEY,
        )
        backend = "groq" if self.config.GROQ_API_KEY else "haiku"
        print(f"  \033[90m[router] tier2/{backend} → {agent} ({reason})\033[0m")
        return agent

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        """Override: use tool_use_loop so BOWEN can search memory and create tasks."""
        history = (
            await self.memory.get_recent_history(self._session_id, n=10)
            if self._session_id else []
        )
        bowen_tools = registry.get_schemas("BOWEN")
        if not bowen_tools:
            # Tools not initialized (no db_path / memory_store at startup) — fall back to plain streaming
            return await self.stream_response(user_text, history=history, send=send)

        def executor(tool_name: str, **kwargs):
            return registry.call_tool("BOWEN", tool_name, **kwargs)

        return await self.tool_use_loop(
            user_text,
            tools=bowen_tools,
            tool_executor=executor,
            history=history,
            send=send,
        )

    async def surface_for_approval(self, payload: ApprovalRequestPayload) -> None:
        """Surface a high-risk action to the user before it executes."""
        print(f"\n\033[33m[BOWEN] Approval required:\033[0m")
        print(f"  Action: {payload.action_type}")
        print(f"  {payload.description}")
        print(f"  Risk: {payload.risk_level.upper()}")
        answer = input("  Approve? (y/n): ").strip().lower()
        # Sub-agents check this flag before executing
        payload.data["approved"] = answer == "y"
