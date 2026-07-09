"""Config loading and interactive config write helpers."""

from __future__ import annotations

from pathlib import Path

from rich.prompt import Prompt

from athenaeum.cli.io_util import write_text_file
from athenaeum.config import load_config, render_primary_config
from athenaeum.interactive import InteractiveState
from athenaeum.reasoning import get_reasoning_profile


def primary_config_text(
    provider: str,
    model: str,
    review_model: str,
    reasoning: str,
    base_url: str,
    network: str,
    disable_storage: bool,
    goals: bool,
) -> str:
    return render_primary_config(provider, model, review_model, reasoning, base_url, network, disable_storage, goals)


def write_interactive_config(path: Path, state: InteractiveState) -> None:
    provider = state.provider or "OpenAI"
    model = state.model or "gpt-5.5"
    review_model = state.review_model or model
    reasoning = reasoning_for_interactive_config(state)
    network = config_network_value(state.network_access)
    disable_storage = state.storage_preference.lower() in {
        "disabled",
        "disable",
        "no-response-storage",
        "no_storage",
        "off",
        "private",
        "true",
    }
    text = primary_config_text(
        provider,
        model,
        review_model,
        reasoning,
        state.base_url,
        network,
        disable_storage,
        True,
    )
    write_text_file(path, text + "\n", overwrite=True)


def reasoning_for_interactive_config(state: InteractiveState) -> str:
    if state.reasoning_effort != "auto":
        return get_reasoning_profile(state.reasoning_effort).name
    if state.effort in {"vhigh", "max", "ultra"}:
        return "xhigh"
    if state.effort == "medium":
        return "medium"
    if state.effort == "low":
        return "low"
    return "high"


def config_network_value(network_access: str) -> str:
    """Map interactive network state to config file values."""
    if network_access == "disabled":
        return "disabled"
    if network_access == "enabled":
        return "enabled"
    # auto and unknown map to enabled for generated configs
    return "enabled"


def prompt_bool(label: str, default: bool) -> bool:
    default_text = "true" if default else "false"
    return Prompt.ask(label, default=default_text).strip().lower() in {"1", "true", "yes", "y", "on"}


def config_defaults(path: Path | None) -> dict[str, str]:
    data = load_config(path)
    provider = data.get("model_provider")
    model = data.get("model")
    review_model = data.get("review_model")
    reasoning = data.get("model_reasoning_effort")
    network = data.get("network_access")
    base_url = active_provider_base_url(data, provider)
    storage = "no-response-storage" if data.get("disable_response_storage") is True else "default"
    defaults: dict[str, str] = {}
    if isinstance(provider, str):
        defaults["provider"] = provider
    if isinstance(model, str):
        defaults["model"] = model
        defaults["route_model"] = (
            model if "/" in model else f"{provider}/{model}" if isinstance(provider, str) else model
        )
    if isinstance(review_model, str):
        defaults["review_model"] = review_model
        defaults["route_review_model"] = (
            review_model
            if "/" in review_model
            else f"{provider}/{review_model}" if isinstance(provider, str) else review_model
        )
    if isinstance(reasoning, str):
        defaults["reasoning_effort"] = reasoning
    if isinstance(network, str):
        defaults["network_access"] = network
    elif isinstance(network, bool):
        defaults["network_access"] = "enabled" if network else "disabled"
    if isinstance(base_url, str):
        defaults["base_url"] = base_url
    defaults["storage_preference"] = storage
    return defaults


def active_provider_base_url(data: dict[str, object], provider: object) -> str | None:
    if not isinstance(provider, str):
        return None
    providers = data.get("model_providers")
    if not isinstance(providers, dict):
        return None
    raw = providers.get(provider)
    if not isinstance(raw, dict):
        provider_lower = provider.lower()
        for key, candidate in providers.items():
            if str(key).lower() == provider_lower:
                raw = candidate
                break
            if (
                isinstance(candidate, dict)
                and isinstance(candidate.get("name"), str)
                and candidate["name"].lower() == provider_lower
            ):
                raw = candidate
                break
    if isinstance(raw, dict) and isinstance(raw.get("base_url"), str):
        return raw["base_url"]
    return None
