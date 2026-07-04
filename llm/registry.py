"""
llm/registry.py — Provider construction + agents.yaml resolution.

get_provider(kind, config)      → cached adapter instance
resolve_agent_llm(name, config) → (provider, model_id, temperature) for an agent
resolve_service_llm(...)        → same, for services (sleep pipeline, QA, ...)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from llm.provider import LLMProvider
from llm.anthropic_provider import AnthropicProvider
from llm.groq_provider import GroqProvider
from llm.local_provider import LocalProvider

_YAML_PATH = Path(__file__).parent.parent / "agents.yaml"

_PROVIDERS: dict[tuple[str, str], LLMProvider] = {}


@lru_cache(maxsize=1)
def _load_yaml() -> dict:
    return yaml.safe_load(_YAML_PATH.read_text())


def _resolve_model(alias: str, config) -> str:
    return {
        "sonnet": config.SONNET_MODEL,
        "haiku": config.HAIKU_MODEL,
    }.get(alias, alias)


def get_provider(kind: str, config) -> LLMProvider:
    """Cached adapter per (kind, key). The only place adapters are built."""
    api_key = {
        "anthropic": config.ANTHROPIC_API_KEY,
        "groq": config.GROQ_API_KEY,
        "local": "",
    }.get(kind)
    if api_key is None:
        raise ValueError(f"Unknown LLM provider kind: {kind!r}")

    cache_key = (kind, api_key)
    if cache_key not in _PROVIDERS:
        cls = {"anthropic": AnthropicProvider, "groq": GroqProvider, "local": LocalProvider}[kind]
        _PROVIDERS[cache_key] = cls(api_key)
    return _PROVIDERS[cache_key]


def _resolve(section: str, name: str, config) -> tuple[LLMProvider, str, Optional[float]]:
    entry = _load_yaml().get(section, {}).get(name)
    if entry is None:
        raise KeyError(f"agents.yaml has no entry {section}.{name}")
    provider = get_provider(entry["provider"], config)
    model = _resolve_model(entry["model"], config)
    return provider, model, entry.get("temperature")


def resolve_agent_llm(agent_name: str, config) -> tuple[LLMProvider, str, Optional[float]]:
    return _resolve("agents", agent_name, config)


def resolve_routing_llm(role: str, config) -> tuple[LLMProvider, str, Optional[float]]:
    return _resolve("routing", role, config)


def resolve_service_llm(service: str, config) -> tuple[LLMProvider, str, Optional[float]]:
    return _resolve("services", service, config)
