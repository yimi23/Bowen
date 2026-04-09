"""
voice/wake.py — Always-on wake word detection using openWakeWord.
No API key. Fully local. ONNX Runtime on Apple Silicon.

Using pretrained models bundled in the openwakeword package:
  - hey_jarvis_v0.1.onnx  →  "Hey BOWEN" proxy (phonetically close)
  - alexa_v0.1.onnx       →  backup model

Custom model training (Phase 2):
  Use openWakeWord's synthetic training pipeline to train
  "hey bowen", "daddy's home", "come alive" using TTS-generated audio.
  See: https://github.com/dscripka/openWakeWord#training-new-models

Usage:
    wake = WakeWordDetector(callback=on_detected)
    wake.initialize()
    await wake.start()
    await wake.stop()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DETECTION_THRESHOLD = 0.5
SAMPLE_RATE = 16000
CHUNK_MS = 80
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)


class WakeWordDetector:
    """
    Listens to microphone continuously using openWakeWord (ONNX Runtime).
    Calls callback(word_name) when wake word detected.
    <5% CPU at idle.
    """

    def __init__(
        self,
        callback: Callable[[str], None],
        threshold: float = DETECTION_THRESHOLD,
        models: Optional[list[str]] = None,
    ) -> None:
        self._callback = callback
        self._threshold = threshold
        self._models = models  # None = use all pretrained
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._ready = False
        self._oww_model = None

    def initialize(self) -> bool:
        """Load ONNX models. Returns True if ready."""
        try:
            import openwakeword
            from openwakeword.model import Model

            # Use pretrained ONNX models bundled in the package
            if self._models:
                wakeword_models = self._models
            else:
                # Default: hey_jarvis as "hey bowen" proxy
                pretrained = openwakeword.get_pretrained_model_paths("onnx")
                wakeword_models = [p for p in pretrained if "hey_jarvis" in p]
                if not wakeword_models:
                    wakeword_models = pretrained[:1]  # fallback to first available

            self._oww_model = Model(
                wakeword_models=wakeword_models,
                inference_framework="onnx",
            )
            model_names = [m.split("/")[-1] for m in wakeword_models]
            self._ready = True
            logger.info(f"Wake word ready — models: {model_names}")
            return True

        except Exception as e:
            logger.warning(f"Wake word init failed: {e}")
            return False

    async def start(self) -> None:
        """Start background listening. Non-blocking. Safe to call multiple times."""
        if not self._ready or self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Wake word detector started")

    async def stop(self) -> None:
        """Stop listening."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Wake word detector stopped")

    async def _listen_loop(self) -> None:
        try:
            import sounddevice as sd
            import numpy as np

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SIZE,
            ) as stream:
                logger.debug("Wake word: listening...")
                while self._running:
                    chunk, _ = await asyncio.to_thread(stream.read, CHUNK_SIZE)
                    audio = chunk.flatten().astype("int16")

                    scores = await asyncio.to_thread(self._oww_model.predict, audio)

                    for name, score in scores.items():
                        if score >= self._threshold:
                            logger.info(f"Wake word: {name} (score={score:.2f})")
                            self._running = False  # stop loop — pipeline will restart
                            try:
                                self._callback(name)
                            except Exception as e:
                                logger.warning(f"Wake callback error: {e}")
                            break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Wake word listen error: {e}")
            self._running = False

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def running(self) -> bool:
        return self._running
