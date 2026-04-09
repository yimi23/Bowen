"""
agents/tamara.py — TAMARA: Messaging & Communications.
Phase 4+: Gmail read/send/draft. Phase 5+: send callback for WebSocket streaming.

RULE: Never sends without explicit user approval.
      gmail_send enforces this at the tool level (prompts before API call).
"""

import tools.registry as registry
from agents.base import BaseAgent, SendFn
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus


class TamaraAgent(BaseAgent):
    name = "TAMARA"
    voice_style = "Warm but efficient. Gets to the point fast."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus) -> None:
        super().__init__(config, memory, bus)
        self._model = config.SONNET_MODEL

    @property
    def base_identity(self) -> str:
        return (
            "You are TAMARA — communications manager for Praise Oyimi. "
            "You handle all email, messaging, and outbound communications.\n\n"
            "Voice: warm but efficient. You get to the point fast. "
            "No pleasantries unless they serve a purpose.\n\n"
            "When drafting emails: match Praise's style — direct, short sentences, "
            "active voice. No filler phrases. Never open with 'Hope this email finds you well.'\n\n"
            "CRITICAL RULE: You NEVER send anything without explicit approval. "
            "Always draft first, surface for approval, then send only if approved. "
            "gmail_send will prompt Praise before transmitting — trust that gate.\n\n"
            "Reading emails: lead with most urgent, identify action items, "
            "flag anything requiring a response within 24 hours.\n\n"
            "You have access to Gmail tools. Use gmail_read to check the inbox, "
            "gmail_draft to prepare messages, and gmail_send to transmit (with approval)."
        )

    @property
    def allowed_tools(self) -> list[str]:
        return ["gmail_read", "gmail_send", "gmail_draft"]

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        history = (
            await self.memory.get_recent_history(self._session_id, n=6)
            if self._session_id else []
        )
        schemas = registry.get_schemas("TAMARA")

        if schemas:
            return await self.tool_use_loop(
                user_text=user_text,
                tools=schemas,
                tool_executor=lambda name, **kw: registry.call_tool("TAMARA", name, **kw),
                history=history,
                send=send,
            )

        # Fallback: no tools registered (Google not configured yet)
        return await self.stream_response(user_text, history=history, send=send)
