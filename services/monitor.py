"""
services/monitor.py — Conversation quality monitor.

Wraps the WebSocket send callback to inspect every outbound chunk.
Catches AI slop phrases, lost context, excessive length, broken voice formatting.

Usage (in gateway.py):
    from services.monitor import monitor
    monitored_send = monitor.wrap(send, session_id=active_conversation_id, agent=target_name)
    await agents[target_name].respond(content, send=monitored_send)
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# ── Banned phrases ─────────────────────────────────────────────────────────────
# Phrases that should never appear in BOWEN responses.
# Checked case-insensitively against accumulated chunk text.

BANNED_PHRASES: list[str] = [
    "as an ai",
    "i'm just an ai",
    "i am an ai",
    "how can i help you today",
    "how can i assist you",
    "i'd be happy to",
    "i would be happy to",
    "i'm happy to help",
    "certainly!",
    "of course!",
    "absolutely!",
    "great question",
    "excellent question",
    "i hope this helps",
    "let me know if you have any questions",
    "feel free to ask",
    "as your ai assistant",
    "i don't have personal",        # "I don't have personal opinions"
    "i cannot provide",
    "i'm not able to",
    "i am not able to",
]

# Markdown patterns that break TTS / voice output
VOICE_BANNED: list[str] = [
    "**",     # bold
    "##",     # headers
    "```",    # code blocks (in voice mode)
]

# Max chars in a single response before it's flagged as too long for voice
VOICE_MAX_CHARS = 600


class _Violation:
    __slots__ = ("session_id", "agent", "phrase", "context", "ts")

    def __init__(self, session_id: str, agent: str, phrase: str, context: str) -> None:
        self.session_id = session_id
        self.agent = agent
        self.phrase = phrase
        self.context = context
        self.ts = time.monotonic()


class MonitorService:
    def __init__(self) -> None:
        self._violations: list[_Violation] = []

    def wrap(
        self,
        send_fn: Callable,
        session_id: str = "",
        agent: str = "",
        voice_mode: bool = False,
    ) -> Callable:
        """
        Return a new send callback that monitors outbound chunks.
        Passes all messages through unchanged — monitoring is non-blocking.
        """
        accumulated: list[str] = []

        async def monitored_send(data: dict) -> None:
            # Collect text for phrase checking
            if data.get("type") == "chunk":
                content = data.get("content", "")
                accumulated.append(content)
                self._check_chunk(content, accumulated, session_id, agent, voice_mode)

            elif data.get("type") == "done":
                full = "".join(accumulated)
                self._check_full_response(full, session_id, agent, voice_mode)
                accumulated.clear()

            await send_fn(data)

        return monitored_send

    def _check_chunk(
        self,
        chunk: str,
        accumulated: list[str],
        session_id: str,
        agent: str,
        voice_mode: bool,
    ) -> None:
        """Check an individual chunk for banned phrases."""
        full_so_far = "".join(accumulated).lower()
        chunk_lower = chunk.lower()

        for phrase in BANNED_PHRASES:
            if phrase in full_so_far and phrase not in "".join(accumulated[:-1]).lower():
                self._flag(session_id, agent, f"banned_phrase: '{phrase}'", chunk[:80])

        if voice_mode:
            for marker in VOICE_BANNED:
                if marker in chunk:
                    self._flag(session_id, agent, f"voice_markdown: '{marker}'", chunk[:80])

    def _check_full_response(
        self,
        full: str,
        session_id: str,
        agent: str,
        voice_mode: bool,
    ) -> None:
        """Check the complete response after 'done'."""
        if voice_mode and len(full) > VOICE_MAX_CHARS:
            self._flag(
                session_id, agent,
                f"voice_too_long: {len(full)} chars (max {VOICE_MAX_CHARS})",
                full[:80],
            )

    def _flag(self, session_id: str, agent: str, phrase: str, context: str) -> None:
        v = _Violation(session_id, agent, phrase, context)
        self._violations.append(v)
        logger.warning(
            "Response quality violation",
            extra={
                "session_id": session_id,
                "agent": agent,
                "violation": phrase,
                "context": context,
            },
        )

    def get_recent_violations(self, n: int = 20) -> list[dict]:
        return [
            {"agent": v.agent, "violation": v.phrase, "context": v.context}
            for v in self._violations[-n:]
        ]

    def violation_count(self) -> int:
        return len(self._violations)


# Singleton
monitor = MonitorService()
