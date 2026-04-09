"""
services/keep_alive.py — Background health-check service.

Pings critical dependencies every INTERVAL seconds so failures are detected
proactively (not when Praise sends a message and gets an error).

Checked services:
  - Anthropic API  (lightweight models.list() call)
  - ChromaDB       (collection.count())
  - Groq API       (lightweight models.list() call)

Results are stored in _status and exposed via get_status() for /api/health.

Usage (in main.py lifespan):
    from services.keep_alive import keep_alive
    keep_alive.start(config, memory)
    yield
    keep_alive.stop()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

INTERVAL = 60  # seconds between checks


@dataclass
class _ServiceStatus:
    healthy: bool = True
    last_check: Optional[float] = None  # monotonic time
    last_error: str = ""

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "last_check_ago_s": (
                round(time.monotonic() - self.last_check, 1)
                if self.last_check else None
            ),
            "last_error": self.last_error or None,
        }


class KeepAliveService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._status: dict[str, _ServiceStatus] = {
            "anthropic": _ServiceStatus(),
            "chromadb":  _ServiceStatus(),
            "groq":      _ServiceStatus(),
        }
        self._config = None
        self._memory = None

    def start(self, config, memory) -> None:
        """Launch background check loop. Call once in lifespan startup."""
        self._config = config
        self._memory = memory
        self._task = asyncio.create_task(self._loop(), name="keep_alive")
        logger.info("KeepAlive service started", extra={"interval_s": INTERVAL})

    def stop(self) -> None:
        """Cancel background loop. Call in lifespan shutdown."""
        if self._task:
            self._task.cancel()
            logger.info("KeepAlive service stopped")

    def get_status(self) -> dict:
        """Return current health status of all probed services."""
        return {name: s.as_dict() for name, s in self._status.items()}

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        # First check immediately, then every INTERVAL seconds
        await asyncio.sleep(5)  # small delay so server finishes booting
        while True:
            await asyncio.gather(
                self._check_anthropic(),
                self._check_chromadb(),
                self._check_groq(),
                return_exceptions=True,
            )
            await asyncio.sleep(INTERVAL)

    async def _check_anthropic(self) -> None:
        status = self._status["anthropic"]
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=self._config.ANTHROPIC_API_KEY)
            await client.models.list()
            status.healthy = True
            status.last_error = ""
        except Exception as exc:
            status.healthy = False
            status.last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("Anthropic health check failed", extra={"err": status.last_error})
        finally:
            status.last_check = time.monotonic()

    async def _check_chromadb(self) -> None:
        status = self._status["chromadb"]
        try:
            count = await asyncio.to_thread(self._memory._collection.count)
            status.healthy = True
            status.last_error = ""
            logger.debug("ChromaDB OK", extra={"memory_count": count})
        except Exception as exc:
            status.healthy = False
            status.last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("ChromaDB health check failed", extra={"err": status.last_error})
        finally:
            status.last_check = time.monotonic()

    async def _check_groq(self) -> None:
        status = self._status["groq"]
        if not self._config.GROQ_API_KEY:
            status.healthy = False
            status.last_error = "GROQ_API_KEY not set"
            status.last_check = time.monotonic()
            return
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self._config.GROQ_API_KEY)
            await client.models.list()
            status.healthy = True
            status.last_error = ""
        except Exception as exc:
            status.healthy = False
            status.last_error = f"{type(exc).__name__}: {str(exc)[:120]}"
            logger.warning("Groq health check failed", extra={"err": status.last_error})
        finally:
            status.last_check = time.monotonic()


# Singleton — imported by main.py and health.py
keep_alive = KeepAliveService()
