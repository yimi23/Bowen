"""
llm/groq_provider.py — Groq adapter (chat + Whisper transcription).

complete() normalizes Groq's OpenAI-shaped reply into Anthropic-shaped
blocks so consumers (tier-2 routing) read one format regardless of vendor.
Tools are passed in OpenAI function format — that is Groq's native dialect
and this adapter is where vendor dialect belongs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Optional

from groq import AsyncGroq, Groq

from llm.provider import LLMProvider, LLMResponse
from utils.rate_limiter import groq_limiter


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = AsyncGroq(api_key=api_key)
        self._sync_client: Optional[Groq] = None

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
        if output_schema is not None:
            raise NotImplementedError("Structured output is only wired for Anthropic today")

        await groq_limiter.acquire()

        if system is not None:
            messages = [{"role": "system", "content": system}, *messages]

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if temperature is not None:
            kwargs["temperature"] = temperature

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        blocks: list = []
        if choice.message.content:
            blocks.append(SimpleNamespace(type="text", text=choice.message.content))
        for call in choice.message.tool_calls or []:
            try:
                args = json.loads(call.function.arguments)
            except Exception:
                args = {}
            blocks.append(
                SimpleNamespace(type="tool_use", name=call.function.name, input=args, id=call.id if hasattr(call, "id") else "")
            )

        return LLMResponse(content=blocks, stop_reason=choice.finish_reason)

    def stream(self, messages, *, model, max_tokens, system=None, temperature=None):
        raise NotImplementedError("Groq streaming is not used anywhere in BOWEN yet")

    # ── Whisper transcription (voice STT) ─────────────────────────────────────

    def transcribe_sync(self, audio_file, model: str = "whisper-large-v3-turbo") -> str:
        """Blocking Whisper call — STT engine runs this inside a thread."""
        if self._sync_client is None:
            self._sync_client = Groq(api_key=self._api_key)
        result = self._sync_client.audio.transcriptions.create(
            file=audio_file, model=model,
        )
        return result.text
