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
    def from_config(cls, config_path=None, ledger: BudgetLedger | None = None, transport: HttpTransport | None = None) -> ModelGateway:
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

    def probe(self) -> list[ProviderHealth]:
        return [
            ProviderHealth(
                name=provider.name,
                available=provider.has_key,
                configured=True,
                detail="configured" if provider.has_key else f"missing env {provider.key_env}",
                models=provider.models,
            )
            for provider in self.providers.values()
        ]

    def route_targets(self, capability: str) -> list[str]:
        return list(self.routes.get(capability, []))

    def route_availability(self, capability: str) -> list[ProviderHealth]:
        healths: list[ProviderHealth] = []
        for target in self.route_targets(capability):
            provider_name, _ = _split_model(target)
            provider = self.providers.get(provider_name)
            if provider is None:
                healths.append(ProviderHealth(name=provider_name, available=False, configured=False, detail="provider not configured", models=[]))
                continue
            healths.append(
                ProviderHealth(
                    name=provider.name,
                    available=provider.has_key,
                    configured=True,
                    detail="configured" if provider.has_key else f"missing env {provider.key_env}",
                    models=provider.models,
                )
            )
        return healths

    async def complete(self, req: CompletionRequest, token: BudgetToken | None = None) -> CompletionResult:
        last_error: Exception | None = None
        for target in self._route_targets(req):
            try:
                resolved = self.resolve(req.capability, target)
                projected = self.projected_cost(req, resolved)
                if self.ledger and token:
                    self.ledger.reserve(token, projected)
                provider = self._provider_config(resolved.provider)
                result = await adapter_for(provider, self.transport).complete(req, resolved)
            except (ProviderUnavailable, TransientProviderError) as exc:
                last_error = exc
                if self.ledger:
                    self.ledger.degrade(f"fallback after provider error on {resolved.provider}/{resolved.model}: {exc}")
                continue
            if self.ledger and token:
                self.ledger.settle(token, resolved, result.tokens_in, result.tokens_out, result.cost_usd)
            return result
        raise SchemaError(f"all route candidates failed: {last_error}")

    async def complete_json(self, req: CompletionRequest, schema: type[BaseModel], max_repair_attempts: int = 3, token: BudgetToken | None = None) -> BaseModel:
        last_error: Exception | None = None
        working = req.model_copy(deep=True)
        working.messages = _with_schema_instruction(list(req.messages), schema)
        for _ in range(max_repair_attempts + 1):
            result = await self.complete(working, token)
            try:
                return schema.model_validate(_loads_json_object(result.text))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                working.messages = [*working.messages, {"role": "user", "content": f"Repair JSON for schema {schema.__name__}. Error: {exc}. Schema: {json.dumps(schema.model_json_schema(), sort_keys=True)}"}]
        raise SchemaError(f"failed to produce {schema.__name__}: {last_error}")

    def _route_targets(self, req: CompletionRequest) -> list[str]:
        if req.model:
            return [req.model]
        return list(self.routes.get(req.capability or "fast", ["stub/fast"]))

    def projected_cost(self, req: CompletionRequest, resolved: ResolvedModel) -> float:
        tokens_in = sum(len(message.get("content", "").split()) for message in req.messages)
        tokens_out = max(req.max_tokens, 0)
        return round(tokens_in / 1000 * resolved.price_input_per_1k + tokens_out / 1000 * resolved.price_output_per_1k, 6)

    def _projected_cost(self, req: CompletionRequest, resolved: ResolvedModel) -> float:
        return self.projected_cost(req, resolved)

    def _provider_config(self, provider_name: str) -> ProviderConfig:
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ProviderUnavailable(f"provider {provider_name!r} is not configured")
        return provider


def _split_model(value: str) -> tuple[str, str]:
    if "/" not in value:
        return "stub", value
    provider, model = value.split("/", 1)
    return provider, model


def _env_provider_defaults(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("providers"):
        return {"routes": {}, "providers": {}}
    routes: dict[str, list[str]] = {}
    providers: dict[str, ProviderConfig] = {}
    for raw in ENV_PROVIDER_DEFAULTS.values():
        env = raw["env"]
        if isinstance(env, str) and os.environ.get(env):
            provider = raw["provider"]
            if isinstance(provider, ProviderConfig):
                providers[provider.name] = provider.model_copy(deep=True)
            for capability, targets in raw["routes"].items():
                routes.setdefault(capability, []).extend(list(targets))
    return {"routes": routes, "providers": providers}


def _loads_json_object(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    return json.loads(stripped)


def _with_schema_instruction(messages: list[dict[str, str]], schema: type[BaseModel]) -> list[dict[str, str]]:
    instruction = (
        f"Return only valid JSON matching schema {schema.__name__}. "
        f"Schema: {json.dumps(schema.model_json_schema(), sort_keys=True)}"
    )
    if messages and messages[0].get("role") == "system":
        first = dict(messages[0])
        first["content"] = f"{first.get('content', '')}\n\n{instruction}".strip()
        return [first, *messages[1:]]
    return [{"role": "system", "content": instruction}, *messages]
