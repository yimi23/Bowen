"""
utils/retry.py — Async retry with exponential backoff.

Distinguishes retryable errors (429, 5xx, network) from non-retryable (4xx client errors).
Anthropic 529 overloads and Groq rate limits both resolve within a few seconds.

Usage:
    from utils.retry import with_retry

    response = await with_retry(
        self.client.messages.create,
        model=..., messages=...,
        max_retries=3,
        context="CAPTAIN stream_response",
    )
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# HTTP status codes that indicate a transient failure worth retrying
_RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}

# Backoff delays in seconds for attempts 0, 1, 2, ...
_DEFAULT_BACKOFF = [1.0, 2.0, 4.0]


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception is a transient error that may resolve on retry."""
    # Anthropic / Groq SDK errors carry a status_code attribute
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status in _RETRYABLE_STATUS

    # Network-level errors
    name = type(exc).__name__
    if any(t in name for t in ("Timeout", "ConnectionError", "NetworkError", "ConnectError")):
        return True

    # asyncio timeout
    if isinstance(exc, asyncio.TimeoutError):
        return True

    return False


async def with_retry(
    coro_func: Callable[..., Awaitable[Any]],
    *args: Any,
    max_retries: int = 3,
    backoff: list[float] = _DEFAULT_BACKOFF,
    context: str = "",
    **kwargs: Any,
) -> Any:
    """
    Call an async function with retry on transient failures.

    Args:
        coro_func:   Async callable to invoke.
        *args:       Positional args forwarded to coro_func.
        max_retries: Total attempts (including the first). Default 3.
        backoff:     Sleep seconds before each retry. Index 0 = before attempt 1.
        context:     Label for log messages (e.g. "CAPTAIN tool_use_loop").
        **kwargs:    Keyword args forwarded to coro_func.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await coro_func(*args, **kwargs)

        except Exception as exc:
            last_exc = exc

            if not _is_retryable(exc):
                # 4xx client error — won't improve on retry
                raise

            remaining = max_retries - attempt - 1
            if remaining == 0:
                logger.error(
                    "All retries exhausted",
                    extra={
                        "context": context,
                        "attempts": attempt + 1,
                        "exc": str(exc),
                        "exc_type": type(exc).__name__,
                    },
                )
                raise

            delay = backoff[min(attempt, len(backoff) - 1)]
            logger.warning(
                "Transient error — retrying",
                extra={
                    "context": context,
                    "attempt": attempt + 1,
                    "remaining": remaining,
                    "delay_s": delay,
                    "exc_type": type(exc).__name__,
                    "exc": str(exc)[:120],
                },
            )
            await asyncio.sleep(delay)

    raise last_exc  # type: ignore[misc]
