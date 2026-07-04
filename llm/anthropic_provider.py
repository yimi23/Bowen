"""
llm/anthropic_provider.py — Anthropic adapter. The ONLY file (with
groq_provider.py) allowed to import a vendor SDK.

Wraps the exact calls BaseAgent, tier2, the sleep pipeline, the
consolidator, the planner, QA, and keep-alive were making directly.
Rate limiting moved inside so no call site can forget it.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import anthropic

from llm.provider import LLMProvider, LLMResponse
from utils.rate_limiter import anthropic_limiter

_STRUCTURED_TOOL = "emit_structured_output"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        *,
        model: str,
        max_tokens: int,
        system: Any = None,
        tools: Optional[list[dict]] = None,
        tool_choice: Any = None,
        temperature: Optional[float] = None,
        output_schema: Optional[dict] = None,
    ) -> LLMResponse:
        await anthropic_limiter.acquire()

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature

        if output_schema is not None:
            # Structured output via a forced tool call — works on every SDK
            # version and guarantees schema-valid JSON (the GENI pattern).
            kwargs["tools"] = [{
                "name": _STRUCTURED_TOOL,
                "description": "Emit the answer as structured JSON matching the schema.",
                "input_schema": output_schema,
            }]
            kwargs["tool_choice"] = {"type": "tool", "name": _STRUCTURED_TOOL}
        else:
            if tools is not None:
                kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        response = await self._client.messages.create(**kwargs)

        structured = None
        if output_schema is not None:
            for block in response.content:
                if getattr(block, "type", "") == "tool_use" and block.name == _STRUCTURED_TOOL:
                    structured = dict(block.input)
                    break
            if structured is None:
                raise ValueError("Structured output requested but no tool_use block returned")

        return LLMResponse(
            content=list(response.content),
            stop_reason=response.stop_reason,
            structured=structured,
        )

    def stream(
        self,
        messages: list[dict],
        *,
        model: str,
        max_tokens: int,
        system: Any = None,
        temperature: Optional[float] = None,
    ):
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        # The SDK object is itself an async context manager with .text_stream —
        # returned as-is so streaming behavior is byte-identical to before.
        return self._client.messages.stream(**kwargs)
