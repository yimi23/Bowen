"""
agents/captain.py — CAPTAIN: Full-stack builder.
Code execution, file ops, shell, architecture.
Phase 5+: send callback for WebSocket streaming.
"""

from typing import Optional

from agents.base import BaseAgent, SendFn
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from bus.schema import AgentMessage, ChainPayload


class CaptainAgent(BaseAgent):
    name = "CAPTAIN"
    voice_style = "Focused. Clipped. Slightly faster pace. Minimal words."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus, user_registry=None) -> None:
        super().__init__(config, memory, bus, user_registry)
        self._model = config.SONNET_MODEL  # always Sonnet for code quality

    @property
    def base_identity(self) -> str:
        return (
            "You are CAPTAIN — full-stack builder for Praise Oyimi. "
            "You handle all code, builds, file operations, shell commands, and architecture.\n\n"
            "Voice: focused, clipped, slightly faster pace. Minimal words. "
            "Deliver working code, not explanations of what you will do.\n\n"
            "When writing code: no placeholder comments, no TODO stubs, no incomplete functions. "
            "Deliver finished, working implementations.\n\n"
            "Tool usage rules:\n"
            "- Always read a file before writing to it\n"
            "- Always show what code does before executing it\n"
            "- For destructive shell ops (rm, overwrite), state what will be deleted\n"
            "- Run tests after writing code when possible\n\n"
            "Languages: Python, TypeScript, JavaScript, Shell, SQL."
        )

    @property
    def allowed_tools(self) -> list[str]:
        from tools.registry import TOOL_REGISTRY
        return TOOL_REGISTRY["CAPTAIN"]

    def _execute_tool(self, tool_name: str, **kwargs) -> dict:
        return self._call_tool("CAPTAIN", tool_name, **kwargs)

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        """Tool-use loop for CAPTAIN with QA verification + auto-retry (up to 3 attempts)."""
        from tools.qa import verify_output

        history = await self.memory.get_recent_history(self._session_id, n=10) if self._session_id else []
        schemas = self._get_schemas("CAPTAIN")

        current_prompt = user_text
        response = ""

        for attempt in range(1, 4):
            response = await self.tool_use_loop(
                user_text=current_prompt,
                tools=schemas,
                tool_executor=self._execute_tool,
                history=history,
                send=send,
            )

            try:
                qa = await verify_output(
                    user_text, response,
                    self.config.ANTHROPIC_API_KEY, self.config.HAIKU_MODEL,
                    attempt=attempt,
                )
            except Exception:
                # QA verification failed — accept response rather than crash
                break

            if qa.passed or attempt == 3:
                break

            # Inject QA feedback and retry
            if send:
                await send({
                    "type": "chunk", "agent": self.name,
                    "content": f"\n*[QA: {len(qa.issues)} issue(s) — retrying...]*\n",
                })
            current_prompt = f"{user_text}\n\n{qa.as_prompt_feedback()}"

        return response

    async def handle(self, msg: AgentMessage, send: SendFn = None) -> Optional[str]:
        """Handle bus messages — including SCOUT chains."""
        if isinstance(msg.payload, ChainPayload):
            task = (
                f"Task: {msg.payload.next_action}\n\n"
                f"Context from {msg.payload.from_agent}:\n{msg.payload.work_product}\n\n"
                f"Original request: {msg.payload.original_task}"
            )
            return await self.respond(task, send=send)
        return await super().handle(msg, send=send)
