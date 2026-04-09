"""
agents/base.py — BaseAgent class.
Phase 5+: Async memory calls + send callback for WebSocket streaming.

send callback: Optional[Callable[[dict], Awaitable[None]]]
  - When None  → prints to terminal (CLI / clawdbot.py debug mode)
  - When set   → streams JSON to WebSocket client (FastAPI server mode)

WebSocket message types sent:
  {"type": "chunk",       "agent": str, "content": str}  — streaming text token
  {"type": "tool_call",   "agent": str, "tool": str, "args": dict}
  {"type": "tool_result", "agent": str, "tool": str, "status": str, "preview": str}
  {"type": "routing",     "from": str, "to": str}          — agent hand-off (BOWEN only)
"""

from __future__ import annotations

import json
import uuid
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Callable, Awaitable, Any

import anthropic

from config import Config
from memory.store import MemoryStore
from bus.message_bus import MessageBus
from bus.schema import AgentMessage, TextPayload
from utils.rate_limiter import anthropic_limiter

# Type alias for the streaming callback
SendFn = Optional[Callable[[dict], Awaitable[None]]]

AGENT_TIMEOUT = 120


class BaseAgent(ABC):
    name: str
    voice_style: str
    model_override: Optional[str] = None

    def __init__(self, config: Config, memory: MemoryStore, bus: MessageBus) -> None:
        self.config = config
        self.memory = memory
        self.bus = bus
        self.client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        self._model = self.model_override or config.SONNET_MODEL
        self._session_id: Optional[str] = None
        self._topic_id: str = "default"
        self._turn: int = 0

    # ── Identity ──────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def base_identity(self) -> str: ...

    @property
    def allowed_tools(self) -> list[str]:
        return []

    # ── System Prompt ─────────────────────────────────────────────────────────

    async def build_system_prompt(self, query: str = "") -> str:
        """
        Assemble system prompt: identity + user profile + relevant memories.
        memory.search() runs in a thread to avoid blocking the event loop
        (SentenceTransformer embedding can take 10-50ms).
        get_core_memory() is a sync file read — fast, no await needed.
        """
        core = self.memory.get_core_memory()
        retrieved = await asyncio.to_thread(
            self.memory.search,
            query,
            self.config.MEMORY_TOP_K,
            self.config.MEMORY_MIN_RELEVANCE,
            True,
            self._topic_id,
        )

        # Append per-topic instructions if set
        topic = await self.memory.get_topic(self._topic_id)
        topic_instructions = (topic or {}).get("instructions", "")

        parts = [self.base_identity]
        if topic_instructions:
            parts.append(f"## Topic Context\n{topic_instructions}")
        if core:
            parts.append(f"## User Profile\n{core}")
        if retrieved:
            parts.append(f"## Relevant Memory\n{retrieved}")
        return "\n\n".join(parts)

    async def _get_system(self, query: str = "") -> list[dict]:
        """Build the Anthropic cached system prompt block."""
        prompt = await self.build_system_prompt(query)
        return [{
            "type": "text",
            "text": prompt,
            "cache_control": {"type": "ephemeral"},
        }]

    # ── Output helpers ────────────────────────────────────────────────────────

    @staticmethod
    async def _emit(send: SendFn, data: dict, fallback_print: str = "") -> None:
        """Route output to WebSocket send or terminal print."""
        if send:
            await send(data)
        elif fallback_print:
            print(fallback_print, end="", flush=True)

    # ── Streaming Response (no tools) ─────────────────────────────────────────

    async def stream_response(
        self,
        user_text: str,
        history: list[dict] | None = None,
        print_output: bool = True,
        send: SendFn = None,
    ) -> str:
        messages = []
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": user_text})

        system = await self._get_system(user_text)
        full_response = ""

        if print_output and not send:
            print(f"\n\033[1m[{self.name}]\033[0m ", end="", flush=True)

        try:
            async with asyncio.timeout(AGENT_TIMEOUT):
                await anthropic_limiter.acquire()
                async with self.client.messages.stream(
                    model=self._model,
                    max_tokens=2048,
                    system=system,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        full_response += text
                        if send:
                            await send({"type": "chunk", "agent": self.name, "content": text})
                        elif print_output:
                            print(text, end="", flush=True)
        except asyncio.TimeoutError:
            msg = f"[{self.name}] timed out after {AGENT_TIMEOUT}s"
            if send:
                await send({"type": "error", "agent": self.name, "content": msg})
            raise

        if print_output and not send:
            print()

        await self._log(user_text, full_response)
        return full_response

    # ── Tool-Use Loop ─────────────────────────────────────────────────────────

    async def tool_use_loop(
        self,
        user_text: str,
        tools: list[dict],
        tool_executor,
        history: list[dict] | None = None,
        print_output: bool = True,
        max_iterations: int = 10,
        send: SendFn = None,
    ) -> str:
        messages = []
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role in ("user", "assistant"):
                    messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": user_text})

        system = await self._get_system(user_text)
        final_text = ""

        if print_output and not send:
            print(f"\n\033[1m[{self.name}]\033[0m ", end="", flush=True)

        try:
            async with asyncio.timeout(AGENT_TIMEOUT):
                for iteration in range(max_iterations):
                    await anthropic_limiter.acquire()
                    response = await self.client.messages.create(
                        model=self._model,
                        max_tokens=4096,
                        system=system,
                        messages=messages,
                        tools=tools,
                    )

                    turn_text = ""
                    tool_calls = []

                    for block in response.content:
                        if block.type == "text":
                            turn_text += block.text
                            if send:
                                await send({"type": "chunk", "agent": self.name, "content": block.text})
                            elif print_output:
                                print(block.text, end="", flush=True)
                        elif block.type == "tool_use":
                            tool_calls.append(block)

                    final_text += turn_text

                    if response.stop_reason == "end_turn" or not tool_calls:
                        break

                    if print_output and not send and tool_calls:
                        print()

                    tool_results = []
                    for tc in tool_calls:
                        # Announce the tool call
                        if send:
                            await send({
                                "type": "tool_call",
                                "agent": self.name,
                                "tool": tc.name,
                                "args": _safe_args(tc.input),
                            })
                        elif print_output:
                            print(f"  \033[90m[tool] {tc.name}({_fmt_args(tc.input)})\033[0m")

                        try:
                            result = await asyncio.to_thread(tool_executor, tc.name, **tc.input)
                            result_text = json.dumps(result) if isinstance(result, dict) else str(result)
                            status = "OK" if not isinstance(result, dict) or result.get("success", True) else "ERR"
                        except Exception as tool_err:
                            result_text = json.dumps({"success": False, "error": str(tool_err)})
                            status = "ERR"

                        preview = result_text[:120].replace("\n", " ")

                        if send:
                            await send({
                                "type": "tool_result",
                                "agent": self.name,
                                "tool": tc.name,
                                "status": status,
                                "preview": preview,
                            })
                        elif print_output:
                            print(f"  \033[90m       → [{status}] {preview}\033[0m")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result_text,
                        })

                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})

                    if print_output and not send:
                        print(f"\n\033[1m[{self.name}]\033[0m ", end="", flush=True)

        except asyncio.TimeoutError:
            msg = f"[{self.name}] timed out after {AGENT_TIMEOUT}s"
            if send:
                await send({"type": "error", "agent": self.name, "content": msg})
            raise
        except Exception as e:
            msg = f"[{self.name}] error: {type(e).__name__}: {e}"
            if send:
                await send({"type": "error", "agent": self.name, "content": msg})
            elif print_output:
                print(f"\n{msg}")
            return final_text or f"Error: {msg}"

        if print_output and not send:
            print()

        await self._log(user_text, final_text)
        return final_text

    # ── Message Bus ───────────────────────────────────────────────────────────

    async def dispatch_to(
        self,
        recipient: str,
        payload,
        msg_type: str = "request",
        priority: int = 3,
        requires_approval: bool = False,
        correlation_id: Optional[str] = None,
    ) -> None:
        msg = AgentMessage(
            sender=self.name,
            recipient=recipient,
            msg_type=msg_type,
            payload=payload,
            priority=priority,
            requires_approval=requires_approval,
            correlation_id=correlation_id or str(uuid.uuid4()),
            session_id=self._session_id,
        )
        await self.bus.send(msg)

    # ── Entrypoints ───────────────────────────────────────────────────────────

    async def respond(self, user_text: str, send: SendFn = None) -> str:
        """User-facing response. Tool-using agents override this."""
        history = (
            await self.memory.get_recent_history(self._session_id, n=10)
            if self._session_id else []
        )
        return await self.stream_response(user_text, history=history, send=send)

    async def handle(self, msg: AgentMessage, send: SendFn = None) -> Optional[str]:
        """Handle bus message. Routes based on payload type."""
        if hasattr(msg.payload, "text"):
            return await self.respond(msg.payload.text, send=send)
        if hasattr(msg.payload, "task"):
            return await self.respond(msg.payload.task, send=send)
        if hasattr(msg.payload, "query"):
            return await self.respond(msg.payload.query, send=send)
        if hasattr(msg.payload, "work_product"):
            return await self.respond(
                f"{msg.payload.original_task}\n\nContext from {msg.sender}:\n{msg.payload.work_product}",
                send=send,
            )
        return None

    def set_session(self, session_id: str, topic_id: str = "default") -> None:
        self._session_id = session_id
        self._topic_id = topic_id
        self._turn = 0

    async def _log(self, user_text: str, response_text: str) -> None:
        """Log user+assistant messages to SQLite."""
        if self._session_id and response_text:
            self._turn += 1
            await self.memory.log_message(
                self._session_id, self._turn, "user", self.name, user_text,
                topic_id=self._topic_id,
            )
            await self.memory.log_message(
                self._session_id, self._turn, "assistant", self.name, response_text,
                topic_id=self._topic_id,
            )


def _fmt_args(inputs: dict) -> str:
    parts = []
    for k, v in inputs.items():
        val = str(v)
        if len(val) > 60:
            val = val[:57] + "..."
        parts.append(f"{k}={repr(val)}")
    return ", ".join(parts)


def _safe_args(inputs: dict) -> dict:
    """Truncate long values for JSON serialization to client."""
    return {k: str(v)[:200] if len(str(v)) > 200 else v for k, v in inputs.items()}
