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

