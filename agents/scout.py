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
from bus.schema import AgentMessage, HandoffPayload, ResearchResponsePayload


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
            "Chaining to CAPTAIN: if your research findings require code to be written, "
            "end your response with a line in EXACTLY this format on its own line:\n"
            "HANDOFF_TO_CAPTAIN: <one-sentence description of what CAPTAIN should build>\n"
            "BOWEN will route it automatically. Only use this when code/build work is clearly needed."
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

        # Check for typed handoff directive — strip from visible response
        if "HANDOFF_TO_CAPTAIN:" in response:
            response = await self._handoff_to_captain(user_text, response)

        return response

    async def _handoff_to_captain(self, original_task: str, research: str) -> str:
        """Extract typed handoff directive, dispatch HandoffPayload, strip line from response."""
        lines = research.splitlines()
        handoff_line = next((l for l in lines if "HANDOFF_TO_CAPTAIN:" in l), "")
        task = handoff_line.replace("HANDOFF_TO_CAPTAIN:", "").strip()

        # Strip directive from what's shown to user
        clean_response = "\n".join(l for l in lines if "HANDOFF_TO_CAPTAIN:" not in l).strip()

        if not task:
            return clean_response

        payload = HandoffPayload(
            from_agent="SCOUT",
            target="CAPTAIN",
            original_task=original_task,
            work_product=clean_response,
            task=task,
            reason="Research findings require implementation",
        )

        print(f"  \033[90m[scout] handoff → CAPTAIN: {task[:60]}\033[0m")
        await self.dispatch_to("CAPTAIN", payload, msg_type="chain", priority=4)
        return clean_response

    async def handle(self, msg: AgentMessage, send: SendFn = None) -> Optional[str]:
        if type(msg.payload).__name__ == "DispatchBriefPayload":
            return await self._handle_brief(msg.payload, send=send)
        if isinstance(msg.payload, HandoffPayload):
            query = msg.payload.task
        elif hasattr(msg.payload, "query"):
            query = msg.payload.query
        else:
            query = str(msg.payload)
        return await self.respond(query, send=send)
