"""
agents/geni.py — GENI: Elder-Care Companion (seventh agent).

GENI's proven internals (monitoring core, vision, fall detection, cron
cycles) live in the supervised Node backend at geni/backend — this agent
WRAPS them, it does not reimplement them.

Two modes:
  wrapped  — forwards conversation to the GENI backend's context-aware brain
             (buildGENIContext + geni-brain voice rules) over HTTP.
  degraded — backend unreachable: answers directly through the LLM seam with
             GENI's identity, honest about reduced capability.

Bus events (fall_confirmed, medication_missed, wellness_check, daily_report)
arrive as typed payloads and are forwarded to TAMARA, who owns outbound
human interruptions and routes them through the core/alerts gate.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from agents.base import BaseAgent, SendFn
from agents.constants import AgentName
from bus.schema import (
    AgentMessage,
    DailyReportPayload,
    FallConfirmedPayload,
    MedicationMissedPayload,
    WellnessCheckPayload,
)
from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus

logger = logging.getLogger(__name__)

CHAT_TIMEOUT_S = 20

GENI_EVENT_PAYLOADS = (
    FallConfirmedPayload,
    MedicationMissedPayload,
    WellnessCheckPayload,
    DailyReportPayload,
)


class GENIAgent(BaseAgent):
    name = "GENI"
    voice_style = "Warm, human, unhurried. Short sentences. Never corporate."

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus, user_registry=None) -> None:
        super().__init__(config, memory, bus, user_registry)
        self._backend_url = config.GENI_BACKEND_URL
        self._api_key = config.GENI_API_KEY

    @property
    def base_identity(self) -> str:
        return (
            "You are GENI — a warm elder-care companion. You watch over an "
            "elderly person living alone: conversation, medication reminders, "
            "wellness, and caregiver updates.\n\n"
            "Voice rules (never break): sound human, not robotic. Say 'Looks "
            "like...' not 'I have detected...'. Short sentences. No jargon, "
            "no corporate speak, no markdown. Gentle, never alarmist.\n\n"
            "Right now your monitoring backend is offline, so you cannot see "
            "the camera, pill organizer, or schedules. Say so honestly if "
            "asked about them, and help with what you can."
        )

    # ── Conversation ──────────────────────────────────────────────────────────

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        """Wrapped mode first; degraded chat via the LLM seam if backend is down."""
        reply = await self._backend_chat(user_text)
        if reply is not None:
            if send:
                await send({"type": "chunk", "agent": self.name, "content": reply})
            await self._log(user_text, reply)
            return reply

        logger.warning("GENI backend unreachable — degraded chat mode")
        history = (
            await self.memory.get_recent_history(self._session_id, n=10)
            if self._session_id else []
        )
        return await self.stream_response(user_text, history=history, send=send)

    async def _backend_chat(self, text: str) -> Optional[str]:
        """POST to the GENI backend's context-aware brain. None = unreachable."""
        try:
            async with httpx.AsyncClient(timeout=CHAT_TIMEOUT_S) as client:
                resp = await client.post(
                    f"{self._backend_url}/api/chat",
                    json={"message": text},
                    headers={"x-api-key": self._api_key} if self._api_key else {},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response") or data.get("message") or None
        except Exception as exc:
            logger.debug("GENI backend chat failed: %s: %s", type(exc).__name__, exc)
            return None

    # ── Bus events ────────────────────────────────────────────────────────────

    async def handle(self, msg: AgentMessage, send: SendFn = None) -> Optional[str]:
        """GENI events get forwarded to TAMARA (owner of human interruptions)."""
        if isinstance(msg.payload, GENI_EVENT_PAYLOADS):
            await self.forward_event(msg.payload)
            return None
        return await super().handle(msg, send=send)

    async def forward_event(self, payload) -> None:
        """
        Dispatch a GENI event to TAMARA. Fall events ride at priority 5
        (urgent) so they jump every queue; the alerts gate downstream still
        owns the deliver/defer/suppress decision.
        """
        priority = 5 if isinstance(payload, FallConfirmedPayload) else 3
        await self.dispatch_to(
            AgentName.TAMARA,
            payload,
            msg_type="inform",
            priority=priority,
        )
        logger.info(
            "GENI event forwarded to TAMARA",
            extra={"event": type(payload).__name__, "priority": priority},
        )
