"""
voice/pipeline.py — Full voice pipeline coordinator.
Connects wake word → STT → agent → TTS into one loop.

Flow:
  1. WakeWordDetector hears "hey jarvis/bowen"
  2. TTS plays a short acknowledgment tone/word
  3. STTEngine records until silence
  4. Text routed through BOWEN agent system (same routing as text)
  5. Response text → TTS speaks it back
  6. Return to listening

Half-duplex: mic is logically muted while TTS is speaking (sounddevice
handles this naturally since we stop recording before playing).

Usage (from tui.py):
    pipeline = VoicePipeline(config, agents)
    pipeline.initialize()
    await pipeline.start()
    await pipeline.stop()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from config import Config
from voice.tts import TTSEngine
from voice.stt import STTEngine
from voice.wake import WakeWordDetector

logger = logging.getLogger(__name__)

# Short acknowledgment phrases — randomized so BOWEN doesn't sound like a recording
ACK_PHRASES = [
    "Go ahead.",
    "I'm listening.",
    "Yes.",
    "Here.",
]

import random


class VoicePipeline:
    """
    Coordinates wake → STT → agent → TTS.
    Agents dict is the same dict used by the TUI.
    on_transcript: called with (text, agent_name) when user speaks
    on_response: called with (text, agent_name) when agent responds (for TUI display)
    """

    def __init__(
        self,
        config: Config,
        agents: dict,
        on_transcript: Optional[Callable[[str, str], None]] = None,
        on_response: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.config = config
        self.agents = agents
        self.on_transcript = on_transcript
        self.on_response = on_response

        self.tts = TTSEngine(voice="am_adam", speed=0.95)
        self.stt = STTEngine(api_key=config.GROQ_API_KEY)
        self.wake = WakeWordDetector(callback=self._on_wake)

        self._active = False
        self._processing = False
        self._wake_queue: asyncio.Queue = asyncio.Queue()

    def initialize(self) -> dict[str, bool]:
        """Initialize all voice components. Returns status dict."""
        tts_ok = self.tts.initialize()
        stt_ok = self.stt.initialize()
        wake_ok = self.wake.initialize()
        status = {"tts": tts_ok, "stt": stt_ok, "wake": wake_ok}
        logger.info(f"Voice pipeline: {status}")
        return status

    async def start(self) -> None:
        """Start wake word listening + process loop."""
        self._active = True
        await self.wake.start()
        asyncio.create_task(self._process_loop())
        logger.info("Voice pipeline active")

    async def stop(self) -> None:
        """Stop everything cleanly."""
        self._active = False
        await self.wake.stop()
        logger.info("Voice pipeline stopped")

    def _on_wake(self, word_name: str) -> None:
        """Called by WakeWordDetector (from async context) when wake word detected."""
        if not self._processing:
            # Put wake event on queue for process loop to handle
            try:
                self._wake_queue.put_nowait(word_name)
            except asyncio.QueueFull:
                pass

    async def _process_loop(self) -> None:
        """Wait for wake events, then run STT → agent → TTS."""
        while self._active:
            try:
                word_name = await asyncio.wait_for(
                    self._wake_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            self._processing = True
            try:
                await self._handle_wake(word_name)
            except Exception as e:
                logger.warning(f"Voice process error: {e}")
            finally:
                self._processing = False
                # Brief cooldown so TTS audio finishes before mic reopens
                await asyncio.sleep(1.5)
                # Resume wake word listening (wake._running is False after trigger)
                if self._active:
                    await self.wake.start()

    async def _handle_wake(self, word_name: str) -> None:
        """Full cycle: ack → record → transcribe → agent → speak."""
        # 1. Acknowledge
        ack = random.choice(ACK_PHRASES)
        await self.tts.speak(ack)

        # 2. Record speech
        logger.debug("Voice: recording user speech...")
        text = await self.stt.transcribe_once()
        if not text:
            logger.debug("Voice: no speech detected")
            return

        logger.info(f"Voice: heard: {text}")

        # 3. Notify TUI of transcript
        if self.on_transcript:
            self.on_transcript(text, "voice")

        # 4a. WebSocket mode (TUI is a WS client — agents live in backend process)
        #     _ws_send is set by tui.py: self._voice._ws_send = self._send_voice_transcript
        #     The transcript goes through the WebSocket → backend routes + streams chunks back →
        #     tui._ws_receive_loop collects _voice_chunks → speaks on "done" event.
        ws_send = getattr(self, "_ws_send", None)
        if ws_send is not None:
            await ws_send(text)
            # TTS speaking is handled by tui.py on the "done" WebSocket event.
            # Nothing more to do here — pipeline returns to listening.
            return

        # 4b. Direct mode (clawdbot.py or legacy — agents in same process)
        agent_name = "BOWEN"
        bowen = self.agents.get("BOWEN")
        if bowen and hasattr(bowen, "route"):
            try:
                agent_name = await bowen.route(text)
            except Exception:
                agent_name = "BOWEN"

        agent = self.agents.get(agent_name, self.agents.get("BOWEN"))
        if not agent:
            logger.warning("Voice: no agent available and no WebSocket — dropping transcript")
            return

        # 5. Get response
        response_parts: list[str] = []

        async def collect_chunk(data: dict) -> None:
            if data.get("type") == "chunk":
                response_parts.append(data["content"])

        await agent.respond(text, send=collect_chunk)

        full_response = "".join(response_parts)
        logger.debug(f"Voice: responding with {len(full_response)} chars")

        # 6. Notify TUI of response
        if self.on_response and full_response:
            self.on_response(full_response, agent_name)

        # 7. Speak response
        if full_response:
            await self.tts.speak_streaming(full_response)

    @property
    def ready(self) -> bool:
        return self.stt.ready

    @property
    def status(self) -> dict[str, bool]:
        return {
            "tts": self.tts.ready,
            "stt": self.stt.ready,
            "wake": self.wake.ready,
            "active": self._active,
        }
