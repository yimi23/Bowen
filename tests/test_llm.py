"""
tests/test_llm.py — The LLMProvider seam.

Adapters normalize vendor replies into one block shape, agents.yaml is the
single source of model policy, and LocalProvider is a visible, honest stub.
"""

from __future__ import annotations

import pytest

from llm import (
    AnthropicProvider,
    GroqProvider,
    LocalProvider,
    resolve_agent_llm,
    resolve_routing_llm,
    resolve_service_llm,
)
from tests.conftest import (
    FakeAnthropicClient,
    FakeGroqClient,
    groq_tool_call_response,
    make_config,
    text_response,
    tool_use_response,
)


class TestAgentsYaml:
    """agents.yaml is the one place model choice lives."""

    def test_current_model_mapping_is_preserved(self):
        config = make_config()
        sonnet_agents = ["CAPTAIN", "SCOUT", "TAMARA", "DEVOPS"]
        haiku_agents = ["BOWEN", "HELEN"]

        for name in sonnet_agents:
            provider, model, _ = resolve_agent_llm(name, config)
            assert isinstance(provider, AnthropicProvider)
            assert model == config.SONNET_MODEL, f"{name} should think with Sonnet"

        for name in haiku_agents:
            provider, model, _ = resolve_agent_llm(name, config)
            assert isinstance(provider, AnthropicProvider)
            assert model == config.HAIKU_MODEL, f"{name} should think with Haiku"

    def test_routing_tiers_resolve(self):
        config = make_config(GROQ_API_KEY="gsk_test")
        provider, model, temperature = resolve_routing_llm("tier2_primary", config)
        assert isinstance(provider, GroqProvider)
        assert model == "llama-3.1-8b-instant"
        assert temperature == 0

        provider, model, _ = resolve_routing_llm("tier2_fallback", config)
        assert isinstance(provider, AnthropicProvider)
        assert model == config.HAIKU_MODEL

    def test_services_resolve_to_haiku(self):
        config = make_config()
        for service in ["sleep_pipeline", "consolidator", "planner", "qa"]:
            provider, model, _ = resolve_service_llm(service, config)
            assert isinstance(provider, AnthropicProvider)
            assert model == config.HAIKU_MODEL

    def test_unknown_agent_fails_loudly(self):
        with pytest.raises(KeyError):
            resolve_agent_llm("NOBODY", make_config())


class TestAnthropicAdapter:
    async def test_complete_passes_through_and_normalizes(self):
        provider = AnthropicProvider(api_key="test")
        provider._client = FakeAnthropicClient([text_response("hello from sonnet")])

        resp = await provider.complete(
            [{"role": "user", "content": "hi"}],
            model="sonnet-test", max_tokens=100, system="be brief",
        )

        assert resp.text == "hello from sonnet"
        assert resp.stop_reason == "end_turn"
        call = provider._client.calls[0]
        assert call["model"] == "sonnet-test"
        assert call["max_tokens"] == 100
        assert call["system"] == "be brief"

    async def test_structured_output_forces_tool_and_parses(self):
        provider = AnthropicProvider(api_key="test")
        provider._client = FakeAnthropicClient([
            tool_use_response("emit_structured_output", {"verdict": "SHIP", "issues": []})
        ])

        schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
        resp = await provider.complete(
            [{"role": "user", "content": "review"}],
            model="m", max_tokens=64, output_schema=schema,
        )

        assert resp.structured == {"verdict": "SHIP", "issues": []}
        call = provider._client.calls[0]
        assert call["tool_choice"] == {"type": "tool", "name": "emit_structured_output"}
        assert call["tools"][0]["input_schema"] == schema

    async def test_structured_output_without_tool_block_raises(self):
        provider = AnthropicProvider(api_key="test")
        provider._client = FakeAnthropicClient([text_response("not structured, sorry")])
        with pytest.raises(ValueError, match="Structured output"):
            await provider.complete(
                [{"role": "user", "content": "x"}],
                model="m", max_tokens=64, output_schema={"type": "object"},
            )


class TestGroqAdapter:
    async def test_tool_calls_normalize_to_anthropic_shaped_blocks(self):
        provider = GroqProvider(api_key="gsk_test")
        provider._client = FakeGroqClient(
            response=groq_tool_call_response("route_to_SCOUT", '{"reason": "research"}')
        )

        resp = await provider.complete(
            [{"role": "user", "content": "find x"}],
            model="llama-3.1-8b-instant", max_tokens=64,
            tool_choice="required", temperature=0,
        )

        tool_uses = resp.tool_uses()
        assert len(tool_uses) == 1
        assert tool_uses[0].name == "route_to_SCOUT"
        assert tool_uses[0].input == {"reason": "research"}

    async def test_unparseable_tool_arguments_become_empty_input(self):
        provider = GroqProvider(api_key="gsk_test")
        provider._client = FakeGroqClient(
            response=groq_tool_call_response("route_to_CAPTAIN", "{broken json")
        )
        resp = await provider.complete(
            [{"role": "user", "content": "x"}], model="m", max_tokens=64,
        )
        assert resp.tool_uses()[0].input == {}


class TestLocalProviderStub:
    async def test_complete_raises_with_deployment_guidance(self):
        with pytest.raises(NotImplementedError, match="on-prem"):
            await LocalProvider().complete([], model="m", max_tokens=1)

    def test_stream_raises_with_deployment_guidance(self):
        with pytest.raises(NotImplementedError, match="agents.yaml"):
            LocalProvider().stream([], model="m", max_tokens=1)
