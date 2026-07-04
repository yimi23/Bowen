"""
llm/provider.py — The single seam every model call in BOWEN goes through.

Contract:
- complete() returns an LLMResponse whose .content is a list of
  Anthropic-shaped blocks (type "text" or "tool_use"). Adapters for other
  vendors normalize INTO this shape so consumers never branch on vendor.
- stream() returns an async context manager yielding an object with an
  async-iterable .text_stream attribute (matches the Anthropic SDK shape,
  which existing consumers already depend on).
- output_schema requests structured output. The adapter guarantees
  LLMResponse.structured is a dict matching the schema, or raises.

Do not import anthropic/groq anywhere outside llm/ — that is the point.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    content: list = field(default_factory=list)   # Anthropic-shaped blocks
    stop_reason: Optional[str] = None
    structured: Optional[dict] = None             # set when output_schema was requested

    @property
    def text(self) -> str:
        return "".join(
            getattr(block, "text", "") for block in self.content
            if getattr(block, "type", "") == "text"
        )

    def tool_uses(self) -> list:
        return [b for b in self.content if getattr(b, "type", "") == "tool_use"]


class LLMProvider(ABC):
    """Every agent's thinking, routing, and memory extraction goes through this."""

    name: str = "abstract"

    @abstractmethod
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
    ) -> LLMResponse: ...

    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        *,
        model: str,
        max_tokens: int,
        system: Any = None,
        temperature: Optional[float] = None,
    ):
        """Async context manager yielding an object with .text_stream."""
        ...
