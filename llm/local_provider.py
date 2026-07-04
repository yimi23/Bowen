"""
llm/local_provider.py — Deliberate stub.

This seam exists so that running BOWEN fully inside a customer's walls
(Ollama, llama.cpp, vLLM, or any on-prem endpoint) is a future ADAPTER,
not a rewrite. Implement complete()/stream() against the local runtime
and register it in llm/registry.py — no agent code changes required.
"""

from __future__ import annotations

from llm.provider import LLMProvider

_MESSAGE = (
    "LocalProvider is not implemented yet. It is the seam for on-prem/local "
    "model deployment. Implement complete() and stream() against your local "
    "runtime (e.g. Ollama) and register it in llm/registry.py. Agents will "
    "pick it up via agents.yaml with zero code changes."
)


class LocalProvider(LLMProvider):
    name = "local"

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def complete(self, messages, *, model, max_tokens, system=None,
                       tools=None, tool_choice=None, temperature=None,
                       output_schema=None):
        raise NotImplementedError(_MESSAGE)

    def stream(self, messages, *, model, max_tokens, system=None, temperature=None):
        raise NotImplementedError(_MESSAGE)
