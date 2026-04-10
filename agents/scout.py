"""
agents/scout.py — SCOUT: Deep researcher.
Competitive analysis, market research, technical deep dives.
Phase 5+: Brave Search. send callback for WebSocket streaming.
"""

from typing import Optional

from agents.base import BaseAgent, SendFn
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from bus.schema import AgentMessage, ChainPayload, ResearchResponsePayload


CHAIN_TRIGGER_PHRASES = [
    "then write", "then build", "then implement", "then create",
    "and write", "and build", "and implement", "and code",
    "pass to captain", "chain to captain",
]


class ScoutAgent(BaseAgent):
    name = "SCOUT"
    voice_style = "Clear, neutral. Analytical cadence. Speaks in findings."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus, user_registry=None) -> None:
        super().__init__(config, memory, bus, user_registry)
        self._model = config.SONNET_MODEL

    @property
    def base_identity(self) -> str:
        return (
            "You are SCOUT — deep researcher for Praise Oyimi. "
            "You handle web research, competitive analysis, market research, "
            "technical deep dives, and document parsing.\n\n"
            "Voice: clear, neutral, analytical. Lead with the most important finding. "
            "Be specific — names, numbers, dates, quotes. No vague summaries.\n\n"
            "Research format:\n"
            "1. Key finding (one sentence)\n"
            "2. Supporting evidence (numbered, with sources)\n"
            "3. What Praise should do with this\n"
            "4. Whether CAPTAIN needs to build something based on this\n\n"
            "Tool usage:\n"
            "- Use web_search first for overview\n"
            "- Use web_fetch to go deep on specific pages\n"
            "- Use structured_extract to pull specific fields from raw content\n"
            "- Always include source URLs in your response\n\n"
            "Chaining rule: if your research implies code needs writing, "
            "end your response with 'CHAIN_TO_CAPTAIN: <what CAPTAIN should build>' "
            "on its own line. BOWEN will route it automatically."
        )

    @property
    def allowed_tools(self) -> list[str]:
        from tools.registry import TOOL_REGISTRY
        return TOOL_REGISTRY["SCOUT"]

    def _execute_tool(self, tool_name: str, **kwargs) -> dict:
        return self._call_tool("SCOUT", tool_name, **kwargs)

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        """Tool-use loop for SCOUT — searches, fetches, chains to CAPTAIN if needed."""
        history = await self.memory.get_recent_history(self._session_id, n=10) if self._session_id else []
        schemas = self._get_schemas("SCOUT")

        response = await self.tool_use_loop(
            user_text=user_text,
            tools=schemas,
            tool_executor=self._execute_tool,
            history=history,
            send=send,
        )

        # Store research findings in memory for future context
        if response and len(response) > 100:
            await self.memory.write_memory(
                agent_id="SCOUT",
                memory_type="research",
                content=response[:500],
                importance=0.6,
                tags=["research", "scout"],
            )

        # Check if SCOUT wants to chain to CAPTAIN
        if "CHAIN_TO_CAPTAIN:" in response:
            await self._chain_to_captain(user_text, response)

        return response

    async def _chain_to_captain(self, original_task: str, research: str) -> None:
        """Extract chain instruction and dispatch to CAPTAIN via bus."""
        lines = research.splitlines()
        chain_line = next((l for l in lines if "CHAIN_TO_CAPTAIN:" in l), "")
        next_action = chain_line.replace("CHAIN_TO_CAPTAIN:", "").strip()

        if not next_action:
            return

        # Strip the chain directive from the work product
        work_product = research.replace(chain_line, "").strip()

        payload = ChainPayload(
            from_agent="SCOUT",
            original_task=original_task,
            work_product=work_product,
            next_action=next_action,
        )

        print(f"  \033[90m[scout] chaining to CAPTAIN: {next_action[:60]}\033[0m")
        await self.dispatch_to("CAPTAIN", payload, msg_type="chain", priority=4)

    async def handle(self, msg: AgentMessage, send: SendFn = None) -> Optional[str]:
        return await self.respond(
            msg.payload.query if hasattr(msg.payload, "query") else str(msg.payload),
            send=send,
        )
