from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_NAMES = ("thinktank.toml", ".thinktank/config.toml")
PRIMARY_CONFIG_KEYS = (
    "model_provider",
    "model",
    "review_model",
    "model_reasoning_effort",
    "disable_response_storage",
    "network_access",
    "windows_wsl_setup_acknowledged",
)


def find_config(start: Path | None = None) -> Path | None:
    root = (start or Path.cwd()).resolve()
    for name in DEFAULT_CONFIG_NAMES:
        path = root / name
        if path.exists():
            return path
    return None


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or find_config()
    if config_path is None:
        return {}
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"config {config_path} did not parse to a table")
    return normalize_gateway_config(data)


def normalize_gateway_config(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return config with new model_provider keys projected into legacy gateway keys."""
    normalized = deepcopy(dict(data))
    raw_model_providers = normalized.get("model_providers")
    model_providers = raw_model_providers if isinstance(raw_model_providers, Mapping) else {}

    gateway_providers = _model_providers_to_gateway_providers(normalized, model_providers)
    if gateway_providers:
        existing_providers = normalized.get("providers")
        if isinstance(existing_providers, Mapping):
            normalized["providers"] = {**gateway_providers, **dict(existing_providers)}
        else:
            normalized["providers"] = gateway_providers

    gateway_routes = _primary_model_routes(normalized, model_providers)
    if gateway_routes:
        existing_routes = normalized.get("routes")
        if isinstance(existing_routes, Mapping):
            normalized["routes"] = {**gateway_routes, **dict(existing_routes)}
        else:
            normalized["routes"] = gateway_routes

    return normalized


def feature_enabled(data: Mapping[str, Any], name: str, default: bool = False) -> bool:
    features = data.get("features")
    if not isinstance(features, Mapping):
        return default
    value = features.get(name, default)
    return value if isinstance(value, bool) else default


def generate_example_config() -> str:
    return render_primary_config(
        provider="OpenAI",
        model="gpt-5.5",
        review_model="gpt-5.5",
        reasoning="xhigh",
        base_url="https://openapi.junliai.org",
        network="enabled",
        disable_storage=True,
        goals=True,
    )


def render_primary_config(
    provider: str,
    model: str,
    review_model: str,
    reasoning: str,
    base_url: str,
    network: str,
    disable_storage: bool,
    goals: bool,
) -> str:
    return "\n".join(
        [
            f"model_provider = {_toml_string(provider)}",
            f"model = {_toml_string(model)}",
            f"review_model = {_toml_string(review_model)}",
            f"model_reasoning_effort = {_toml_string(reasoning)}",
            f"disable_response_storage = {_toml_bool(disable_storage)}",
            f"network_access = {_toml_string(network)}",
            "windows_wsl_setup_acknowledged = true",
            "",
            _provider_table_header(provider),
            f"name = {_toml_string(provider)}",
            f"base_url = {_toml_string(base_url)}",
            'wire_api = "responses"',
            "requires_openai_auth = true",
            "# requires_openai_auth uses OPENAI_API_KEY from the environment.",
            "",
            "[features]",
            f"goals = {_toml_bool(goals)}",
        ]
    )


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _provider_table_header(provider: str) -> str:
    if provider and all(char.isalnum() or char in {"_", "-"} for char in provider):
        return f"[model_providers.{provider}]"
    return f"[model_providers.{_toml_string(provider)}]"


def _model_providers_to_gateway_providers(
    data: Mapping[str, Any], model_providers: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    active_provider = _resolve_model_provider_key(data, model_providers)
    active_models = _active_models(data)
    providers: dict[str, dict[str, Any]] = {}
    for key, raw in model_providers.items():
        if not isinstance(raw, Mapping):
            continue
        provider: dict[str, Any] = {
            "kind": "openai-compatible",
            "structured_output": True,
        }
        if isinstance(raw.get("base_url"), str):
            provider["base_url"] = raw["base_url"]
        if isinstance(raw.get("wire_api"), str):
            provider["wire_api"] = raw["wire_api"]
        if data.get("disable_response_storage") is True:
            provider["disable_response_storage"] = True
        if raw.get("requires_openai_auth") is True:
            provider["key_env"] = "OPENAI_API_KEY"
        models = _string_list(raw.get("models"))
        if active_provider == key:
            models = _unique([*models, *active_models])
            if models:
                provider["probe_model"] = models[0]
        if models:
            provider["models"] = models
        providers[str(key)] = provider
    return providers


def _primary_model_routes(
    data: Mapping[str, Any], model_providers: Mapping[str, Any]
) -> dict[str, list[str]]:
    provider = _resolve_model_provider_key(data, model_providers)
    model = data.get("model")
    if not isinstance(provider, str) or not isinstance(model, str):
        return {}
    primary = model if "/" in model else f"{provider}/{model}"
    routes = {
        "reasoner": [primary],
        "fast": [primary],
        "long-context": [primary],
    }
    review_model = data.get("review_model")
    if isinstance(review_model, str):
        routes["cheap-judge"] = [review_model if "/" in review_model else f"{provider}/{review_model}"]
    return routes


def _resolve_model_provider_key(
    data: Mapping[str, Any], model_providers: Mapping[str, Any]
) -> str | None:
    configured = data.get("model_provider")
    if not isinstance(configured, str):
        return None
    if configured in model_providers:
        return configured
    configured_lower = configured.lower()
    for key, raw in model_providers.items():
        if str(key).lower() == configured_lower:
            return str(key)
        if (
            isinstance(raw, Mapping)
            and isinstance(raw.get("name"), str)
            and raw["name"].lower() == configured_lower
        ):
            return str(key)
    return configured


def _active_models(data: Mapping[str, Any]) -> list[str]:
    return _unique(
        value
        for key in ("model", "review_model")
        if isinstance((value := data.get(key)), str)
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
