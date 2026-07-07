from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, ValidationError

from athenaeum.config import load_config

from .adapters import adapter_for
from .ledger import BudgetLedger, BudgetToken
from .models import (
    CompletionRequest,
    CompletionResult,
    ProviderConfig,
    ProviderHealth,
    ProviderUnavailable,
    ResolvedModel,
    SchemaError,
    TransientProviderError,
)
from .transport import HttpTransport


DEFAULT_ROUTES = {
    "reasoner": ["stub/reasoner"],
    "fast": ["stub/fast"],
    "long-context": ["stub/long-context"],
    "cheap-judge": ["stub/cheap-judge"],
    "embedder": ["stub/embedder"],
}

DEFAULT_PROVIDERS = {
    "stub": ProviderConfig(
        name="stub",
        kind="stub",
        models=["reasoner", "fast", "long-context", "cheap-judge", "embedder"],
        prices={"*": {"input": 0.0, "output": 0.0}},
    )
}

ENV_PROVIDER_DEFAULTS = {
    "openai": {
        "env": "OPENAI_API_KEY",
        "provider": ProviderConfig(
            name="openai",
            kind="openai-compatible",
            key_env="OPENAI_API_KEY",
            base_url="https://api.openai.com/v1",
            wire_api="responses",
            structured_output=True,
            models=["gpt-5.5", "gpt-5.5-mini"],
            prices={"*": {"input": 0.0, "output": 0.0}},
        ),
        "routes": {
            "reasoner": ["openai/gpt-5.5"],
            "fast": ["openai/gpt-5.5-mini"],
            "long-context": ["openai/gpt-5.5"],
            "cheap-judge": ["openai/gpt-5.5-mini"],
        },
    },
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "provider": ProviderConfig(
            name="anthropic",
            kind="anthropic",
            key_env="ANTHROPIC_API_KEY",
            models=["claude-fable-5", "claude-haiku-4-5"],
            prices={"*": {"input": 0.0, "output": 0.0}},
        ),
        "routes": {
            "reasoner": ["anthropic/claude-fable-5"],
            "fast": ["anthropic/claude-haiku-4-5"],
            "long-context": ["anthropic/claude-fable-5"],
            "cheap-judge": ["anthropic/claude-haiku-4-5"],
        },
    },
    "google": {
        "env": "GOOGLE_API_KEY",
        "provider": ProviderConfig(
            name="google",
            kind="google",
            key_env="GOOGLE_API_KEY",
            models=["gemini-3-pro", "gemini-3-flash"],
            prices={"*": {"input": 0.0, "output": 0.0}},
        ),
        "routes": {
            "reasoner": ["google/gemini-3-pro"],
            "fast": ["google/gemini-3-flash"],
            "long-context": ["google/gemini-3-pro"],
            "cheap-judge": ["google/gemini-3-flash"],
        },
    },
}


class ModelGateway:
    def __init__(self, routes: dict[str, list[str]] | None = None, providers: dict[str, ProviderConfig] | None = None, ledger: BudgetLedger | None = None, transport: HttpTransport | None = None):
        self.routes = routes or DEFAULT_ROUTES
        self.providers = providers or DEFAULT_PROVIDERS
        self.ledger = ledger
        self.transport = transport

    @classmethod
    def from_config(cls, config_path=None, ledger: BudgetLedger | None = None, transport: HttpTransport | None = None) -> "ModelGateway":
        data = load_config(config_path)
        routes = dict(DEFAULT_ROUTES)
        env_defaults = _env_provider_defaults(data)
        routes.update(env_defaults["routes"])
        routes.update({key: list(value) for key, value in data.get("routes", {}).items()})
        providers = dict(DEFAULT_PROVIDERS)
        providers.update(env_defaults["providers"])
        for name, raw in data.get("providers", {}).items():
            if isinstance(raw, dict):
                providers[name] = ProviderConfig(name=name, **raw)
        return cls(routes, providers, ledger, transport)

    def resolve(self, capability: str | None = None, model: str | None = None) -> ResolvedModel:
        target = model or self.routes.get(capability or "fast", ["stub/fast"])[0]
        provider_name, model_name = _split_model(target)
        provider = self._provider_config(provider_name)
        prices = provider.prices.get(model_name) or provider.prices.get("*") or {"input": 0.0, "output": 0.0}
        return ResolvedModel(
            capability=capability or "explicit",
            provider=provider_name,
            model=model_name,
            price_input_per_1k=float(prices.get("input", 0.0)),
            price_output_per_1k=float(prices.get("output", 0.0)),
        )
