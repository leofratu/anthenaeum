from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ReasoningEffortName = Literal["auto", "off", "low", "medium", "high", "vhigh", "xhigh", "max"]


@dataclass(frozen=True)
class ReasoningProfile:
    name: ReasoningEffortName
    label: str
    openai_effort: str | None
    anthropic_budget_tokens: int
    google_thinking_budget: int
    description: str


REASONING_PROFILES: dict[str, ReasoningProfile] = {
    "auto": ReasoningProfile("auto", "Auto", None, 0, -1, "Let each provider choose its default reasoning mode."),
    "off": ReasoningProfile("off", "Off", None, 0, 0, "Disable explicit reasoning controls where the API supports it."),
    "low": ReasoningProfile("low", "Low", "low", 1024, 512, "Fast reasoning for simple prompts."),
    "medium": ReasoningProfile("medium", "Medium", "medium", 4096, 2048, "Balanced reasoning for normal research runs."),
    "high": ReasoningProfile("high", "High", "high", 8192, 4096, "Deeper reasoning for harder synthesis and review."),
    "vhigh": ReasoningProfile("vhigh", "Very High", "high", 12000, 8192, "High effort plus larger thinking budgets where supported."),
    "xhigh": ReasoningProfile("xhigh", "Extra High", "high", 14000, 10000, "Extra-high reasoning budget for demanding review and synthesis."),
    "max": ReasoningProfile("max", "Max", "high", 16000, 12000, "Maximum configured reasoning budget for hardest tasks."),
}


def get_reasoning_profile(name: str | None) -> ReasoningProfile:
    key = (name or "auto").lower()
    if key not in REASONING_PROFILES:
        valid = ", ".join(REASONING_PROFILES)
        raise ValueError(f"unknown reasoning effort {name!r}; expected one of: {valid}")
    return REASONING_PROFILES[key]


def apply_openai_reasoning(body: dict[str, Any], effort: str | None, overrides: dict[str, dict[str, Any]] | None = None) -> None:
    profile = get_reasoning_profile(effort)
    if profile.name in {"auto", "off"} or profile.openai_effort is None:
        return
    body["reasoning"] = {"effort": profile.openai_effort}
    _merge_override(body, overrides, profile.name)


def apply_anthropic_reasoning(body: dict[str, Any], effort: str | None, overrides: dict[str, dict[str, Any]] | None = None) -> None:
    profile = get_reasoning_profile(effort)
    if profile.name in {"auto", "off"} or profile.anthropic_budget_tokens <= 0:
        return
    body["thinking"] = {"type": "enabled", "budget_tokens": profile.anthropic_budget_tokens}
    body["max_tokens"] = max(int(body.get("max_tokens", 0)), profile.anthropic_budget_tokens + 1024)
    _merge_override(body, overrides, profile.name)


def apply_google_reasoning(body: dict[str, Any], effort: str | None, overrides: dict[str, dict[str, Any]] | None = None) -> None:
    profile = get_reasoning_profile(effort)
    if profile.name == "auto":
        return
    generation_config = body.setdefault("generationConfig", {})
    generation_config["thinkingConfig"] = {"thinkingBudget": profile.google_thinking_budget}
    _merge_override(body, overrides, profile.name)


def _merge_override(body: dict[str, Any], overrides: dict[str, dict[str, Any]] | None, effort: str) -> None:
    if not overrides:
        return
    for key, value in overrides.get(effort, {}).items():
        if isinstance(value, dict) and isinstance(body.get(key), dict):
            body[key].update(value)
        else:
            body[key] = value
