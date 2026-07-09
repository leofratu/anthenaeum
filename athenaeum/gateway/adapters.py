from __future__ import annotations

import json
from typing import Any

import httpx

from athenaeum.reasoning import apply_anthropic_reasoning, apply_google_reasoning, apply_openai_reasoning

from .models import (
    CompletionRequest,
    CompletionResult,
    ProviderConfig,
    ProviderUnavailable,
    ResolvedModel,
    TransientProviderError,
)
from .transport import HttpTransport


class ProviderAdapter:
    def __init__(self, config: ProviderConfig, transport: HttpTransport | None = None):
        self.config = config
        self.transport = transport

    async def complete(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        raise NotImplementedError

    def _require_transport(self) -> HttpTransport:
        if self.transport is None:
            from .transport import HttpxTransport

            self.transport = HttpxTransport()
        return self.transport

    def _require_key(self) -> str:
        if not self.config.has_key:
            raise ProviderUnavailable(f"missing env {self.config.key_env}")
        return self.config.api_key or ""


class StubAdapter(ProviderAdapter):
    async def complete(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        prompt = "\n".join(message.get("content", "") for message in req.messages)
        text = json.dumps(
            {
                "title": "ATHENAEUM API Runtime Report",
                "question": prompt[:120] or "untitled",
                "summary": f"Stub provider {resolved.provider}/{resolved.model} completed the request.",
                "report_markdown": f"# ATHENAEUM API Runtime Report\n\nStub provider `{resolved.provider}/{resolved.model}` completed the request.\n",
            }
        )
        return CompletionResult(text=text, model=resolved, tokens_in=_tokens(req), tokens_out=len(text.split()), cost_usd=0.0)


class OpenAICompatibleAdapter(ProviderAdapter):
    async def complete(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        if self.config.wire_api == "responses":
            return await self._complete_responses(req, resolved)
        return await self._complete_chat_completions(req, resolved)

    async def _complete_chat_completions(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        key = self._require_key()
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", **self.config.headers}
        body: dict[str, Any] = {"model": resolved.model, "messages": req.messages, "max_tokens": req.max_tokens, "temperature": req.temperature}
        if self.config.structured_output:
            body["response_format"] = {"type": "json_object"}
        apply_openai_reasoning(body, req.reasoning_effort, self.config.reasoning_overrides)
        data = await _request(self._require_transport(), "POST", f"{base}/chat/completions", headers, body, self.config.timeout_seconds)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable("OpenAI-compatible response had no message content") from exc
        usage = data.get("usage", {})
        tokens_in = int(usage.get("prompt_tokens", _tokens(req)))
        tokens_out = int(usage.get("completion_tokens", len(str(text).split())))
        return CompletionResult(text=str(text), model=resolved, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=_cost(resolved, tokens_in, tokens_out), raw={"id": data.get("id")})

    async def _complete_responses(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        key = self._require_key()
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", **self.config.headers}
        body: dict[str, Any] = {"model": resolved.model, "input": _responses_input(req), "max_output_tokens": req.max_tokens, "temperature": req.temperature}
        if self.config.disable_response_storage:
            body["store"] = False
        if self.config.structured_output:
            body["text"] = {"format": {"type": "json_object"}}
        apply_openai_reasoning(body, req.reasoning_effort, self.config.reasoning_overrides)
        data = await _request(self._require_transport(), "POST", f"{base}/responses", headers, body, self.config.timeout_seconds)
        text = _responses_text(data)
        usage = data.get("usage", {})
        tokens_in = int(usage.get("input_tokens", usage.get("prompt_tokens", _tokens(req))))
        tokens_out = int(usage.get("output_tokens", usage.get("completion_tokens", len(text.split()))))
        return CompletionResult(text=text, model=resolved, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=_cost(resolved, tokens_in, tokens_out), raw={"id": data.get("id")})


class AnthropicAdapter(ProviderAdapter):
    async def complete(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        key = self._require_key()
        base = (self.config.base_url or "https://api.anthropic.com").rstrip("/")
        headers = {"x-api-key": key, "anthropic-version": self.config.api_version or "2023-06-01", "Content-Type": "application/json", **self.config.headers}
        system = "\n".join(message["content"] for message in req.messages if message.get("role") == "system")
        messages = [message for message in req.messages if message.get("role") != "system"] or [{"role": "user", "content": "Continue."}]
        body: dict[str, Any] = {"model": resolved.model, "messages": messages, "max_tokens": req.max_tokens, "temperature": req.temperature}
        if system:
            body["system"] = system
        apply_anthropic_reasoning(body, req.reasoning_effort, self.config.reasoning_overrides)
        data = await _request(self._require_transport(), "POST", f"{base}/v1/messages", headers, body, self.config.timeout_seconds)
        blocks = data.get("content", [])
        text = "\n".join(block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text")
        if not text:
            raise ProviderUnavailable("Anthropic response had no text content")
        usage = data.get("usage", {})
        tokens_in = int(usage.get("input_tokens", _tokens(req)))
        tokens_out = int(usage.get("output_tokens", len(text.split())))
        return CompletionResult(text=text, model=resolved, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=_cost(resolved, tokens_in, tokens_out), raw={"id": data.get("id")})


class GoogleAdapter(ProviderAdapter):
    async def complete(self, req: CompletionRequest, resolved: ResolvedModel) -> CompletionResult:
        key = self._require_key()
        base = (self.config.base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        url = f"{base}/models/{resolved.model}:generateContent?key={key}"
        headers = {"Content-Type": "application/json", **self.config.headers}
        text_prompt = "\n".join(f"{message.get('role', 'user')}: {message.get('content', '')}" for message in req.messages)
        body: dict[str, Any] = {"contents": [{"parts": [{"text": text_prompt}]}], "generationConfig": {"maxOutputTokens": req.max_tokens, "temperature": req.temperature}}
        if self.config.structured_output:
            body["generationConfig"]["responseMimeType"] = "application/json"
        apply_google_reasoning(body, req.reasoning_effort, self.config.reasoning_overrides)
        data = await _request(self._require_transport(), "POST", url, headers, body, self.config.timeout_seconds)
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable("Google response had no text candidate") from exc
        usage = data.get("usageMetadata", {})
        tokens_in = int(usage.get("promptTokenCount", _tokens(req)))
        tokens_out = int(usage.get("candidatesTokenCount", len(str(text).split())))
        return CompletionResult(text=str(text), model=resolved, tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=_cost(resolved, tokens_in, tokens_out), raw={"model": resolved.model})


def adapter_for(config: ProviderConfig, transport: HttpTransport | None = None) -> ProviderAdapter:
    if config.kind == "stub":
        return StubAdapter(config, transport)
    if config.kind in {"openai", "openai-compatible"}:
        return OpenAICompatibleAdapter(config, transport)
    if config.kind == "anthropic":
        return AnthropicAdapter(config, transport)
    if config.kind == "google":
        return GoogleAdapter(config, transport)
    raise ProviderUnavailable(f"unknown provider kind {config.kind}")


async def _request(transport: HttpTransport, method: str, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        return await transport.request_json(method, url, headers=headers, json_body=body, timeout=timeout)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {408, 409, 429, 500, 502, 503, 504, 529}:
            raise TransientProviderError(f"transient HTTP {exc.response.status_code}") from exc
        raise ProviderUnavailable(f"provider HTTP {exc.response.status_code}") from exc
    except httpx.TimeoutException as exc:
        raise TransientProviderError("provider timeout") from exc


def _tokens(req: CompletionRequest) -> int:
    return sum(len(message.get("content", "").split()) for message in req.messages)


def _cost(resolved: ResolvedModel, tokens_in: int, tokens_out: int) -> float:
    return round(tokens_in / 1000 * resolved.price_input_per_1k + tokens_out / 1000 * resolved.price_output_per_1k, 6)


def _responses_input(req: CompletionRequest) -> list[dict[str, str]]:
    return [{"role": message.get("role", "user"), "content": message.get("content", "")} for message in req.messages]


def _responses_text(data: dict[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text

    chunks: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        _append_response_text(chunks, item)
        content = item.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    _append_response_text(chunks, block)

    text = "\n".join(chunk for chunk in chunks if chunk)
    if not text:
        raise ProviderUnavailable("OpenAI-compatible Responses response had no output text")
    return text


def _append_response_text(chunks: list[str], block: dict[str, Any]) -> None:
    text = block.get("text")
    if isinstance(text, str) and text:
        chunks.append(text)
    elif isinstance(text, dict) and isinstance(text.get("value"), str) and text["value"]:
        chunks.append(text["value"])
