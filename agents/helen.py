"""
agents/helen.py — HELEN: Personal Life Agent.
Phase 4+: Google Calendar + Bible tracking. Phase 5+: send callback for WebSocket streaming.
"""

from agents.base import BaseAgent, SendFn
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus


class HelenAgent(BaseAgent):
    name = "HELEN"
    voice_style = "Gentle, grounding. Firm when she needs to be."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus, user_registry=None) -> None:
        super().__init__(config, memory, bus, user_registry)
        self._model = config.HAIKU_MODEL  # briefings are short — Haiku is fast enough

    @property
    def base_identity(self) -> str:
        return (
            "You are HELEN — personal life agent for Praise Oyimi. "
            "You manage calendar, reminders, daily briefings, Bible accountability, "
            "tasks, and deadlines.\n\n"
            "Voice: gentle, grounding. Warm. Firm when needed — especially on the non-negotiables.\n\n"
            "Non-negotiables you track for Praise every day:\n"
            "  - Daily Bible reading. Ask if not logged by 9am. Log completions.\n"
            "  - Morning prayer before any work begins.\n\n"
            "Morning briefing format (7am daily):\n"
            "  1. Greeting + today's date\n"
            "  2. Bible reading status (done or not yet)\n"
            "  3. Today's calendar events in time order\n"
            "  4. Active deadlines and open tasks (next 48 hours)\n"
            "  5. Most important single focus for today\n"
            "  6. One line of encouragement\n\n"
            "You have access to calendar, task, and Bible tracking tools. "
            "Call daily_briefing to gather all data, then compose the briefing naturally.\n\n"
            "Speak plainly — no jargon, no markdown syntax in voice output. "
            "Refer to numbers as words ('three meetings', not '3 meetings') when speaking."
        )

    @property
    def allowed_tools(self) -> list[str]:
        return ["calendar_list", "calendar_create", "task_create", "bible_check", "notify", "daily_briefing"]

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        history = (
            await self.memory.get_recent_history(self._session_id, n=6)
            if self._session_id else []
        )
        schemas = self._get_schemas("HELEN")

        if schemas:
            return await self.tool_use_loop(
                user_text=user_text,
                tools=schemas,
                tool_executor=lambda name, **kw: self._call_tool("HELEN", name, **kw),
                history=history,
                send=send,
            )

        # Fallback: no tools registered
        return await self.stream_response(user_text, history=history, send=send)

    async def morning_briefing(self) -> str:
        """Called by the 7am scheduler job. Generates and prints the daily briefing."""
        return await self.respond("Generate my morning briefing for today.")
