from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from athenaeum.effort import get_effort
from athenaeum.reasoning import get_reasoning_profile
from athenaeum.workflow import validate_mode


Action = Literal[
    "noop",
    "exit",
    "run",
    "dry_run",
    "plan",
    "doctor",
    "resume",
    "status",
    "settings",
    "help",
    "select_effort",
    "save_config",
]
NetworkAccess = Literal["auto", "enabled", "disabled"]
GoalStatus = Literal["none", "active", "complete"]

DEFAULT_BASE_URL = "https://openapi.junliai.org"


NETWORK_ALIASES: dict[str, NetworkAccess] = {
    "auto": "auto",
    "default": "auto",
    "on": "enabled",
    "yes": "enabled",
    "true": "enabled",
    "enabled": "enabled",
    "enable": "enabled",
    "off": "disabled",
    "no": "disabled",
    "false": "disabled",
    "disabled": "disabled",
    "disable": "disabled",
}


@dataclass
class InteractiveState:
    provider: str | None = None
    model: str | None = None
    review_model: str | None = None
    base_url: str = DEFAULT_BASE_URL
    effort: str = "high"
    reasoning_effort: str = "auto"
    runtime: str = "minimal"
    network_access: NetworkAccess = "auto"
    storage_preference: str = "default"
    budget: float | None = None
    audience: str | None = None
    mode: str = "auto"
    goal: str | None = None
    current_goal: str | None = None
    goal_status: GoalStatus = "none"
    planner_summary: str | None = None
    planner_settings: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class InteractiveResult:
    action: Action
    message: str = ""
    question: str | None = None
    target: str | None = None


HELP_TEXT = """ATHENAEUM interactive

Setup:
/setup                 show the current setup path
/provider [name]      show or set provider
/model [name]         show or set primary model
/review-model [name]  show or set review model
/base-url [url]       show or set OpenAI-compatible base URL
/runtime [name]       auto|minimal|api|opencode|codex|agy|claude|gemini
/network [on|off|auto]
/storage [preference]
/save-config [path]   write thinktank.toml from this session

Control:
/iq [value|select]    one main slider; no value opens it
/plan <question>      preview the workflow
/run <question>       run with current settings
/doctor               run environment diagnostics
/settings             show compact settings
/help advanced        show lower-level controls
/exit                 leave interactive mode

Typing a question without a slash is the same as /run <question>.
""".strip()


ADVANCED_HELP_TEXT = """Advanced commands:
/dry-run <question>       preview the compiled workflow
/effort [level|select]    low|medium|high|vhigh|max|ultra or iq-* aliases
/reasoning [level]        auto|off|low|medium|high|vhigh|xhigh|max
/budget [usd]             show or set budget
/audience [text]          show or set audience
/mode [name]              auto|decide|evolve|review|science
/goal [text|complete]     show, set, or complete the active goal
/resume [run-id]          resume a previous run
/settings network ...     advanced network alias
/settings storage ...     advanced storage alias
""".strip()


def handle_interactive_line(line: str, state: InteractiveState) -> InteractiveResult:
    value = line.strip()
    if not value:
        return InteractiveResult("noop")
    if not value.startswith("/"):
        return InteractiveResult("run", question=value)
    command, _, rest = value[1:].partition(" ")
    command = command.lower()
    rest = rest.strip()
    if command in {"exit", "quit", "q"}:
        return InteractiveResult("exit", "leaving interactive mode")
    if command in {"help", "?"}:
        return InteractiveResult("help", ADVANCED_HELP_TEXT if rest.lower() == "advanced" else HELP_TEXT)
    if command == "status":
        return InteractiveResult("status", format_status(state))
    if command in {"setup", "configure", "config"}:
        if command == "config" and rest:
            subcommand, _, target = rest.partition(" ")
            if subcommand.lower() in {"save", "write"}:
                return InteractiveResult("save_config", target=target.strip() or "thinktank.toml")
        return InteractiveResult("settings", format_setup(state))
    if command in {"save-config", "saveconfig", "write-config"}:
        return InteractiveResult("save_config", target=rest or "thinktank.toml")
    if command == "settings":
        return _handle_settings(rest, state)
    if command == "network":
        return _handle_settings(f"network {rest}", state)
    if command == "storage":
        return _handle_settings(f"storage {rest}", state)
    if command == "doctor":
        return InteractiveResult("doctor")
    if command == "resume":
        return InteractiveResult("resume", target=rest or None)
    if command == "run":
        return InteractiveResult("run", question=rest) if rest else InteractiveResult("noop", "usage: /run <question>")
    if command == "plan":
        return InteractiveResult("plan", question=rest) if rest else InteractiveResult("noop", "usage: /plan <question>")
    if command in {"dry-run", "dryrun"}:
        return InteractiveResult("dry_run", question=rest) if rest else InteractiveResult("noop", "usage: /dry-run <question>")
    if command == "provider":
        return _handle_provider(rest, state)
    if command == "model":
        return _handle_model(rest, state)
    if command in {"review-model", "review_model"}:
        return _handle_model(f"review {rest}", state)
    if command in {"base-url", "base_url"}:
        return _handle_base_url(rest, state)
    if command in {"effort", "iq"}:
        if not rest:
            return InteractiveResult("select_effort")
        if rest.lower() in {"select", "slider", "interactive"}:
            return InteractiveResult("select_effort")
        try:
            state.effort = get_effort(rest).name
        except ValueError as exc:
            return InteractiveResult("noop", str(exc))
        if command == "iq":
            return InteractiveResult("status", f"iq={rest} maps to effort={state.effort}")
        return InteractiveResult("status", f"effort={state.effort}")
    if command in {"reasoning", "reasoning-effort"}:
        if not rest:
            return InteractiveResult("status", f"reasoning_effort={state.reasoning_effort}")
        try:
            state.reasoning_effort = get_reasoning_profile(rest).name
        except ValueError as exc:
            return InteractiveResult("noop", str(exc))
        return InteractiveResult("status", f"reasoning_effort={state.reasoning_effort}")
    if command == "runtime":
        if not rest:
            return InteractiveResult("status", f"runtime={state.runtime}")
        state.runtime = rest
        return InteractiveResult("status", f"runtime={state.runtime}")
    if command == "budget":
        if not rest:
            return InteractiveResult("status", f"budget={state.budget if state.budget is not None else 'default'}")
        try:
            state.budget = float(rest)
        except ValueError:
            return InteractiveResult("noop", "usage: /budget <usd>")
        return InteractiveResult("status", f"budget={state.budget}")
    if command == "audience":
        state.audience = rest or None
        return InteractiveResult("status", f"audience={state.audience or 'default'}")
    if command == "mode":
        if not rest:
            return InteractiveResult("status", f"mode={state.mode}")
        try:
            state.mode = validate_mode(rest)
        except ValueError as exc:
            return InteractiveResult("noop", str(exc))
        return InteractiveResult("status", f"mode={state.mode}")
    if command == "goal":
        return _handle_goal(rest, state)
    return InteractiveResult("noop", f"unknown command /{command}; use /help")


def format_status(state: InteractiveState) -> str:
    return format_settings(state)


def format_settings(state: InteractiveState) -> str:
    provider = state.provider or "default"
    model = state.model or "default"
    review_model = state.review_model or "default"
    budget = state.budget if state.budget is not None else "default"
    audience = state.audience or "default"
    return (
        f"provider={provider} · model={model} · review_model={review_model} · "
        f"base_url={state.base_url} · iq=effort:{state.effort} · runtime={state.runtime} · "
        f"network={state.network_access} · storage={state.storage_preference} · "
        f"budget={budget} · audience={audience} · mode={state.mode} · goal={_format_goal_value(state)}"
    )


def format_setup(state: InteractiveState) -> str:
    provider = state.provider or "OpenAI"
    model = state.model or "gpt-5.5"
    review_model = state.review_model or model
    return "\n".join(
        [
            "Setup path:",
            f"provider={provider}",
            f"model={model}",
            f"review_model={review_model}",
            f"base_url={state.base_url}",
            f"runtime={state.runtime}",
            f"iq=effort:{state.effort}",
            f"network={state.network_access}",
            f"storage={state.storage_preference}",
            "Next: /iq select, /runtime auto, /save-config thinktank.toml, then /plan <question>.",
        ]
    )


def _handle_provider(rest: str, state: InteractiveState) -> InteractiveResult:
    if not rest:
        return InteractiveResult("status", f"provider={state.provider or 'default'}")
    state.provider = _optional_value(rest)
    return InteractiveResult("status", f"provider={state.provider or 'default'}")


def _handle_model(rest: str, state: InteractiveState) -> InteractiveResult:
    if not rest:
        return InteractiveResult("status", f"model={state.model or 'default'} · review_model={state.review_model or 'default'}")
    slot, _, value = rest.partition(" ")
    if slot.lower() in {"review", "reviewer", "review-model", "review_model"}:
        if not value.strip():
            return InteractiveResult("status", f"review_model={state.review_model or 'default'}")
        state.review_model = _optional_value(value.strip())
        return InteractiveResult("status", f"review_model={state.review_model or 'default'}")
    model = _optional_value(rest)
    if model and "/" in model:
        provider, _, provider_model = model.partition("/")
        if provider and provider_model:
            state.provider = provider
            model = provider_model
    state.model = model
    return InteractiveResult("status", f"provider={state.provider or 'default'} · model={state.model or 'default'}")


def _handle_base_url(rest: str, state: InteractiveState) -> InteractiveResult:
    if not rest:
        return InteractiveResult("status", f"base_url={state.base_url}")
    state.base_url = rest
    return InteractiveResult("status", f"base_url={state.base_url}")


def _handle_goal(rest: str, state: InteractiveState) -> InteractiveResult:
    if not rest or rest.lower() in {"show", "status"}:
        return InteractiveResult("status", f"goal={_format_goal_value(state)}")
    command = rest.lower()
    if command in {"complete", "completed", "done", "finish", "finished"}:
        if not state.goal:
            return InteractiveResult("noop", "no active goal")
        state.current_goal = None
        state.goal_status = "complete"
        return InteractiveResult("status", f"goal={_format_goal_value(state)}")
    if command in {"clear", "reset", "none"}:
        state.goal = None
        state.current_goal = None
        state.goal_status = "none"
        return InteractiveResult("status", "goal=none")
    state.goal = rest
    state.current_goal = rest
    state.goal_status = "active"
    return InteractiveResult("status", f"goal={_format_goal_value(state)}")


def _handle_settings(rest: str, state: InteractiveState) -> InteractiveResult:
    if not rest:
        return InteractiveResult("settings", format_settings(state))
    key, value = _split_key_value(rest)
    if key in {"network", "network-access", "network_access"}:
        if not value:
            return InteractiveResult("settings", f"network={state.network_access}")
        normalized = NETWORK_ALIASES.get(value.lower())
        if normalized is None:
            return InteractiveResult("noop", "usage: /settings network on|off|auto")
        state.network_access = normalized
        return InteractiveResult("settings", f"network={state.network_access}")
    if key in {"storage", "storage-preference", "storage_preference"}:
        if not value:
            return InteractiveResult("settings", f"storage={state.storage_preference}")
        state.storage_preference = value
        return InteractiveResult("settings", f"storage={state.storage_preference}")
    return InteractiveResult("noop", "usage: /settings [network on|off|auto|storage <preference>]")


def _split_key_value(rest: str) -> tuple[str, str]:
    key, separator, value = rest.partition("=")
    if separator:
        return key.strip().lower(), value.strip()
    key, _, value = rest.partition(" ")
    return key.strip().lower(), value.strip()


def _optional_value(value: str) -> str | None:
    normalized = value.strip()
    return None if normalized.lower() in {"", "default", "auto", "none", "clear", "reset"} else normalized


def _format_goal_value(state: InteractiveState) -> str:
    if state.goal_status == "active" and state.current_goal:
        return f"active:{state.current_goal}"
    if state.goal_status == "complete" and state.goal:
        return f"complete:{state.goal}"
    return "none"
