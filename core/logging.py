"""
core/logging.py — Centralized logging for the BOWEN backend.

Call setup_logging() once in main.py lifespan before anything else.

Outputs:
  - Console (INFO+): human-readable text
  - File (DEBUG+): JSON, rotating 10MB/5 backups → logs/bowen.log

Usage anywhere in the codebase:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Agent responded", extra={"agent": "CAPTAIN", "duration_ms": 142})
"""

from __future__ import annotations

import logging
import logging.handlers
import json
import time
import os
from pathlib import Path


# ── JSON formatter ─────────────────────────────────────────────────────────────

class _JSONFormatter(logging.Formatter):
    """Emit one JSON object per line — machine-parseable for future log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge any extra= fields the caller provided
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "id", "levelname", "levelno", "lineno", "module",
                "msecs", "message", "msg", "name", "pathname", "process",
                "processName", "relativeCreated", "stack_info", "thread",
                "threadName", "taskName",
            ):
                base[key] = val
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        return json.dumps(base, default=str)


# ── Text formatter ─────────────────────────────────────────────────────────────

_TEXT_FMT = "%(asctime)s  %(levelname)-8s  %(name)-24s  %(message)s"
_DATE_FMT = "%H:%M:%S"


# ── Setup ──────────────────────────────────────────────────────────────────────

def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/bowen.log",
    console: bool = True,
) -> None:
    """
    Configure the root logger. Call once at process startup.

    Args:
        log_level:  Minimum level for console output ("DEBUG", "INFO", "WARNING").
        log_file:   Path to the rotating log file (relative to CWD or absolute).
        console:    Whether to attach a console (stderr) handler.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # Root captures everything; handlers filter

    # ── File handler (JSON, DEBUG+, rotating) ──────────────────────────────────
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_JSONFormatter())
    root.addHandler(file_handler)

    # ── Console handler (text, configurable level) ─────────────────────────────
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(_TEXT_FMT, _DATE_FMT))
        root.addHandler(console_handler)

    # ── Suppress noisy third-party loggers ────────────────────────────────────
    for noisy in (
        "httpx", "httpcore", "h2", "hpack", "grpc",
        "chromadb", "sentence_transformers", "transformers",
        "urllib3", "asyncio", "multipart",
        "apscheduler.scheduler", "apscheduler.executors",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # quiet access log

    logging.getLogger(__name__).info(
        "Logging initialized",
        extra={"log_file": str(log_path.resolve()), "console_level": log_level},
    )
