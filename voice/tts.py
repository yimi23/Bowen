"""
voice/tts.py — Kokoro ONNX text-to-speech.
Local, no API key, Apache 2.0. Voice: am_adam (deep, male).
Falls back to silence if model files not yet downloaded.

Usage:
    tts = TTSEngine()
    await tts.speak("All systems online.")
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default model paths on S1
MODEL_DIR = Path(__file__).parent / "kokoro"
MODEL_PATH = MODEL_DIR / "kokoro-v0_19.onnx"
VOICES_PATH = MODEL_DIR / "voices.bin"

# Voice selection — am_adam is deep and authoritative
# Options: am_adam, am_michael, am_puck, af_sarah, bf_emma
DEFAULT_VOICE = "am_adam"
DEFAULT_SPEED = 1.0


class TTSEngine:
    """Kokoro ONNX TTS. Thread-safe, async-friendly."""

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        voices_path: Path = VOICES_PATH,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
        config=None,
    ) -> None:
        if config is not None:
            voice = config.KOKORO_VOICE
            speed = config.KOKORO_SPEED
            model_path = config.KOKORO_MODEL_DIR / "kokoro-v0_19.onnx"
            voices_path = config.KOKORO_MODEL_DIR / "voices.bin"
        self.voice = voice
        self.speed = speed
        self._kokoro = None
        self._sd = None
        self._ready = False
        self._model_path = model_path
        self._voices_path = voices_path

    def initialize(self) -> bool:
        """Load models. Call once at startup. Returns True if successful."""
        if not self._model_path.exists():
            logger.warning(f"TTS model not found: {self._model_path}")
            return False
        if not self._voices_path.exists():
            logger.warning(f"TTS voices not found: {self._voices_path}")
            return False

        try:
            from kokoro_onnx import Kokoro
            import sounddevice as sd
            self._kokoro = Kokoro(str(self._model_path), str(self._voices_path))
            self._sd = sd
            self._ready = True
            logger.info(f"TTS ready — voice: {self.voice}, speed: {self.speed}")
            return True
        except Exception as e:
            logger.warning(f"TTS init failed: {e}")
            return False

    async def speak(self, text: str) -> None:
        """Synthesize and play text. Non-blocking — runs in thread."""
        if not self._ready or not text.strip():
            return
        await asyncio.to_thread(self._speak_sync, text)

    def _speak_sync(self, text: str) -> None:
        """Synchronous TTS + playback. Called from thread pool."""
        try:
            import numpy as np
            samples, sample_rate = self._kokoro.create(
                text,
                voice=self.voice,
                speed=self.speed,
                lang="en-us",
            )
            # Play audio — blocks until done (half-duplex: mic muted while speaking)
            self._sd.play(samples, samplerate=sample_rate)
            self._sd.wait()
        except Exception as e:
            logger.warning(f"TTS speak failed: {e}")

    async def speak_streaming(self, text: str) -> None:
        """Speak as text arrives — splits on sentence boundaries."""
        if not self._ready:
            return
        # Split into natural speaking chunks
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        for sentence in sentences:
            if sentence.strip():
                await self.speak(sentence.strip())

    @property
    def ready(self) -> bool:
        return self._ready

    def set_voice(self, voice: str) -> None:
        self.voice = voice

    def set_speed(self, speed: float) -> None:
        self.speed = max(0.5, min(2.0, speed))
