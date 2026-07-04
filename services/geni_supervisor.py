"""
services/geni_supervisor.py — Supervises GENI's self-contained processes.

GENI's monitoring internals (Express backend, YOLO fall detection, 15-minute
cron cycles) are proven and stay in Node/Python land — we supervise them,
we do not inline them. This mirrors GENI's own fall-detection supervisor:
restart with backoff, circuit-break after repeated crashes, report honest
health instead of pretending.

Enabled via config.GENI_ENABLED. When disabled (the default), BOWEN boots
exactly as before and the GENI agent runs in degraded chat-only mode.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

MAX_RESTARTS = 3          # consecutive crashes before the breaker opens
RESTART_DELAY_S = 15      # wait between restarts
BREAKER_RESET_S = 300     # a run this long counts as stable → reset the count
STOP_GRACE_S = 10         # SIGTERM → SIGKILL grace window


class GENISupervisor:
    """Spawns and babysits the GENI Node backend as a child process."""

    def __init__(self, config) -> None:
        self._config = config
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._task: Optional[asyncio.Task] = None
        self._restarts = 0
        self._stopping = False
        self.state: str = "stopped"   # stopped | running | degraded

    async def start(self) -> None:
        if not self._config.GENI_ENABLED:
            logger.info("GENI supervisor: disabled (GENI_ENABLED != true)")
            return
        if not (self._config.GENI_DIR / "package.json").exists():
            logger.error("GENI supervisor: geni/backend not found — cannot start")
            self.state = "degraded"
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run_loop(), name="geni-supervisor")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=STOP_GRACE_S)
            except asyncio.TimeoutError:
                self._proc.kill()
        self.state = "stopped"
        logger.info("GENI supervisor: stopped")

    async def _run_loop(self) -> None:
        """Spawn → wait → restart with backoff → circuit-break."""
        while not self._stopping:
            started = asyncio.get_event_loop().time()
            try:
                self._proc = await asyncio.create_subprocess_exec(
                    "npm", "start",
                    cwd=str(self._config.GENI_DIR),
                    env={
                        **os.environ,
                        "PORT": self._config.GENI_BACKEND_URL.rsplit(":", 1)[-1],
                        "BOWEN_INTERNAL_URL": "http://localhost:8000",
                        "GENI_API_KEY": self._config.GENI_API_KEY,
                    },
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self.state = "running"
                logger.info("GENI backend started", extra={"pid": self._proc.pid})
                code = await self._proc.wait()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("GENI backend failed to spawn: %s: %s", type(exc).__name__, exc)
                code = -1

            if self._stopping:
                return

            ran_for = asyncio.get_event_loop().time() - started
            if ran_for >= BREAKER_RESET_S:
                self._restarts = 0   # stable run — forgive past crashes
            self._restarts += 1
            logger.warning(
                "GENI backend exited",
                extra={"code": code, "ran_for_s": round(ran_for), "restarts": self._restarts},
            )

            if self._restarts > MAX_RESTARTS:
                self.state = "degraded"
                logger.error(
                    "GENI supervisor: circuit open after %d crashes — staying degraded. "
                    "GENI agent falls back to chat-only mode.", self._restarts,
                )
                return

            self.state = "degraded"
            await asyncio.sleep(RESTART_DELAY_S)

    def health(self) -> dict:
        return {
            "state": self.state,
            "pid": self._proc.pid if self._proc and self._proc.returncode is None else None,
            "restarts": self._restarts,
        }
