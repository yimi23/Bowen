"""
voice/stt.py — Speech-to-text using Groq Whisper.
groq/whisper-large-v3-turbo: ~98% cheaper than OpenAI, ~200ms latency.
Records from mic, transcribes, returns clean text.

Usage:
    stt = STTEngine(api_key)
    text = await stt.transcribe_once()   # record until silence, return text
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
import wave
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── STT Corrections ───────────────────────────────────────────────────────────
# Whisper common mishears for BOWEN-specific vocabulary.
# Applied after every transcription before returning to caller.

import re

_CORRECTIONS: list[tuple[str, str]] = [
    # Agent names
    (r"\bbowman\b",          "BOWEN"),
    (r"\bbowing\b",          "BOWEN"),
    (r"\bbo\s+win\b",        "BOWEN"),
    (r"\bbo\s+when\b",       "BOWEN"),
    # Claude / Anthropic
    (r"\bcloud\s+code\b",    "Claude Code"),
    (r"\bclawed\s+code\b",   "Claude Code"),
    (r"\bclaude\s+code\b",   "Claude Code"),   # already correct — normalise casing
    (r"\banthropick\b",      "Anthropic"),
    (r"\banthrophic\b",      "Anthropic"),
    # Groq
    (r"\bgrok\b",            "Groq"),
    (r"\bgroak\b",           "Groq"),
    (r"\bcroak\b",           "Groq"),
    # BOWEN projects / vocabulary
    (r"\btwine\s+campus\b",  "Twine Campus"),
    (r"\btwine\s+camps\b",   "Twine Campus"),
    (r"\bremi\s+guardian\b", "Remi Guardian"),
    (r"\bsfb\s+holdings\b",  "SFB Holdings"),
    (r"\btamara\b",          "TAMARA"),
    # Slash commands often misheard
    (r"\bslash\s+code\b",    "/code"),
    (r"\bslash\s+email\b",   "/email"),
    (r"\bslash\s+search\b",  "/search"),
]


def _apply_corrections(text: str) -> str:
    """Fix common Whisper mishears for BOWEN vocabulary."""
    for pattern, replacement in _CORRECTIONS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


# Recording config
SAMPLE_RATE = 16000     # Whisper optimal sample rate
CHANNELS = 1            # mono
CHUNK_SIZE = 1024       # frames per buffer
SILENCE_THRESHOLD = 500 # amplitude below this = silence
SILENCE_DURATION = 1.5  # seconds of silence to stop recording
MAX_RECORD_SECONDS = 30 # safety cap


class STTEngine:
    """Groq Whisper STT. Records mic audio, returns transcribed text."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._ready = False
        self._client = None
        self._sd = None

    def initialize(self) -> bool:
        """Initialize Groq client + sounddevice. Returns True if successful."""
        if not self._api_key:
            logger.warning("STT: no Groq API key")
            return False
        try:
            from groq import Groq
            import sounddevice as sd
            self._client = Groq(api_key=self._api_key)
            self._sd = sd
            self._ready = True
            logger.info("STT ready — Groq whisper-large-v3-turbo")
            return True
        except Exception as e:
            logger.warning(f"STT init failed: {e}")
            return False

    async def transcribe_once(self, max_seconds: int = MAX_RECORD_SECONDS) -> Optional[str]:
        """
        Record from mic until silence, transcribe, return text.
        Returns None if nothing was recorded or transcription failed.
        """
        if not self._ready:
            return None

        audio_bytes = await asyncio.to_thread(self._record_sync, max_seconds)
        if not audio_bytes:
            return None

        return await asyncio.to_thread(self._transcribe_sync, audio_bytes)

    def _record_sync(self, max_seconds: int) -> Optional[bytes]:
        """Record from mic until silence. Returns WAV bytes."""
        import numpy as np

        frames = []
        silence_frames = 0
        silence_limit = int(SAMPLE_RATE / CHUNK_SIZE * SILENCE_DURATION)
        max_frames = int(SAMPLE_RATE / CHUNK_SIZE * max_seconds)
        started = False

        try:
            with self._sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
            ) as stream:
                logger.debug("STT: recording started")
                while len(frames) < max_frames:
                    data, _ = stream.read(CHUNK_SIZE)
                    frames.append(data.copy())
                    amplitude = np.abs(data).mean()

                    if amplitude > SILENCE_THRESHOLD:
                        started = True
                        silence_frames = 0
                    elif started:
                        silence_frames += 1
                        if silence_frames >= silence_limit:
                            break

        except Exception as e:
            logger.warning(f"STT record failed: {e}")
            return None

        if not frames or not started:
            return None

        # Convert to WAV bytes
        import numpy as np
        audio = np.concatenate(frames, axis=0).astype("int16")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        buf.seek(0)
        logger.debug(f"STT: recorded {len(frames) * CHUNK_SIZE / SAMPLE_RATE:.1f}s")
        return buf.read()

    def _transcribe_sync(self, audio_bytes: bytes) -> Optional[str]:
        """Send WAV bytes to Groq Whisper, return transcribed text."""
        try:
            result = self._client.audio.transcriptions.create(
                file=("audio.wav", audio_bytes, "audio/wav"),
                model="whisper-large-v3-turbo",
                language="en",
                response_format="text",
            )
            text = result.strip() if isinstance(result, str) else result.text.strip()
            text = _apply_corrections(text)
            logger.debug(f"STT: transcribed: {text[:80]}")
            return text if text else None
        except Exception as e:
            logger.warning(f"STT transcribe failed: {e}")
            return None

    @property
    def ready(self) -> bool:
        return self._ready
