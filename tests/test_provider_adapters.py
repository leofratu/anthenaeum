from __future__ import annotations

import asyncio
import os

from athenaeum.gateway.adapters import AnthropicAdapter, GoogleAdapter, OpenAICompatibleAdapter
from athenaeum.gateway.models import CompletionRequest, ProviderConfig, ResolvedModel
from athenaeum.gateway.transport import FakeTransport


def test_openai_compatible_adapter_normalizes_response(monkeypatch) -> None:
    monkeypatch.setenv("TEST_KEY", "secret")
    transport = FakeTransport({"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 1}})
    adapter = OpenAICompatibleAdapter(ProviderConfig(name="openai", kind="openai", key_env="TEST_KEY", base_url="https://example.test/v1"), transport)

    result = asyncio.run(adapter.complete(_request("high"), _resolved("openai", "gpt-test")))

    assert result.text == "hello"
    assert result.tokens_in == 3
    assert transport.requests[0]["url"] == "https://example.test/v1/chat/completions"
    assert transport.requests[0]["json"]["reasoning"] == {"effort": "high"}
    assert "secret" not in result.model_dump_json()


def test_openai_compatible_adapter_uses_responses_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("TEST_KEY", "secret")
    transport = FakeTransport(
        {
            "id": "resp_test",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "hello from responses"}]}],
            "usage": {"input_tokens": 4, "output_tokens": 3},
        }
    )
    adapter = OpenAICompatibleAdapter(
        ProviderConfig(name="junl", kind="openai-compatible", key_env="TEST_KEY", base_url="https://openapi.junliai.org", wire_api="responses", disable_response_storage=True),
        transport,
    )

    result = asyncio.run(adapter.complete(_request("medium"), _resolved("junl", "gpt-test")))

    assert result.text == "hello from responses"
    assert result.tokens_in == 4
    assert result.tokens_out == 3
    assert transport.requests[0]["url"] == "https://openapi.junliai.org/responses"
    assert transport.requests[0]["json"]["input"] == [{"role": "user", "content": "say hello"}]
    assert transport.requests[0]["json"]["max_output_tokens"] == 8
    assert transport.requests[0]["json"]["reasoning"] == {"effort": "medium"}
    assert transport.requests[0]["json"]["store"] is False


def test_openai_compatible_responses_supports_output_text_and_structured_format(monkeypatch) -> None:
    monkeypatch.setenv("TEST_KEY", "secret")
    transport = FakeTransport(
        {
            "id": "resp_direct",
            "output_text": '{"answer":"ok"}',
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }
    )
    adapter = OpenAICompatibleAdapter(
        ProviderConfig(
            name="openai",
            kind="openai-compatible",
            key_env="TEST_KEY",
            base_url="https://example.test/v1",
            wire_api="responses",
            structured_output=True,
        ),
        transport,
    )

    result = asyncio.run(adapter.complete(_request("auto"), _resolved("openai", "gpt-test")))

    assert result.text == '{"answer":"ok"}'
    assert result.tokens_in == 5
    assert result.tokens_out == 2
    assert transport.requests[0]["url"] == "https://example.test/v1/responses"
    assert transport.requests[0]["json"]["text"] == {"format": {"type": "json_object"}}
    assert "store" not in transport.requests[0]["json"]


def test_anthropic_adapter_normalizes_response(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_TEST_KEY", "secret")
    transport = FakeTransport({"content": [{"type": "text", "text": "hello"}], "usage": {"input_tokens": 2, "output_tokens": 1}})
    adapter = AnthropicAdapter(ProviderConfig(name="anthropic", kind="anthropic", key_env="ANTHROPIC_TEST_KEY"), transport)

    result = asyncio.run(adapter.complete(_request("medium"), _resolved("anthropic", "claude-test")))

    assert result.text == "hello"
    assert result.tokens_out == 1
    assert transport.requests[0]["json"]["thinking"]["budget_tokens"] == 4096


def test_google_adapter_normalizes_response(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_TEST_KEY", "secret")
    transport = FakeTransport({"candidates": [{"content": {"parts": [{"text": "hello"}]}}], "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 1}})
    adapter = GoogleAdapter(ProviderConfig(name="google", kind="google", key_env="GOOGLE_TEST_KEY"), transport)

    result = asyncio.run(adapter.complete(_request("low"), _resolved("google", "gemini-test")))

    assert result.text == "hello"
    assert ":generateContent" in transport.requests[0]["url"]
    assert transport.requests[0]["json"]["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 512


def _request(reasoning_effort: str = "auto") -> CompletionRequest:
    return CompletionRequest(messages=[{"role": "user", "content": "say hello"}], max_tokens=8, reasoning_effort=reasoning_effort)


def _resolved(provider: str, model: str) -> ResolvedModel:
    return ResolvedModel(capability="reasoner", provider=provider, model=model)
