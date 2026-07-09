from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, Field

Capability = Literal["reasoner", "fast", "long-context", "cheap-judge", "embedder"]
WireApi = Literal["chat/completions", "responses"]


class GatewayError(RuntimeError):
    pass


class BudgetExceeded(GatewayError):
    pass


class ProviderUnavailable(GatewayError):
    pass


class SchemaError(GatewayError):
    pass


class TransientProviderError(GatewayError):
    pass


class ResolvedModel(BaseModel):
    capability: str
    provider: str
    model: str
    route_index: int = 0
    price_input_per_1k: float = 0.0
    price_output_per_1k: float = 0.0


class ProviderHealth(BaseModel):
    name: str
    available: bool
    configured: bool
    detail: str | None = None
    models: list[str] = Field(default_factory=list)


class CompletionRequest(BaseModel):
    messages: list[dict[str, str]]
    capability: str | None = None
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.2
    reasoning_effort: str | None = "auto"
    seed: int | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    budget_token_id: str | None = None


class CompletionResult(BaseModel):
    text: str
    model: ResolvedModel
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    name: str
    kind: Literal["stub", "openai", "anthropic", "google", "openai-compatible"] = "stub"
    wire_api: WireApi = "chat/completions"
    base_url: str | None = None
    key_env: str | None = None
    models: list[str] = Field(default_factory=list)
    prices: dict[str, dict[str, float]] = Field(default_factory=dict)
    timeout_seconds: float = 60.0
    api_version: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    structured_output: bool = False
    disable_response_storage: bool = False
    probe_model: str | None = None
    reasoning_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @property
    def has_key(self) -> bool:
        return self.kind == "stub" or not self.key_env or bool(os.environ.get(self.key_env))

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.key_env) if self.key_env else None
