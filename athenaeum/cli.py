from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Annotated

import click
import typer
from rich.prompt import Prompt
from typer.core import TyperGroup

from .artifacts import RunArtifacts, new_run_id
from .config import generate_example_config, load_config, render_primary_config
from .conductor import LocalConductor, result_from_report
from .effort import EFFORTS
from .effort import get_effort
from .gateway import BudgetLedger, ModelGateway
from .interactive import DEFAULT_BASE_URL, InteractiveState, handle_interactive_line
from .loops.context import RunContext
from .planner import plan_run
from .reasoning import REASONING_PROFILES, get_reasoning_profile
from .runtime.api import ApiRuntime
from .runtime import AgentTask, RuntimeRegistry, Workspace
from .loops import DeterministicLoopEngine
from .runtime.models import CostDelta, RuntimeExecutionError, RuntimeUnavailable, SchemaValidationError
from .resume import ResumeError, replay_run
from .sanity import SanityChecker
from .schemas import OUTPUT_MODELS, SessionRecord, output_schema
from .store import CitationDB, ClaimLedger, SessionStore
from .thinkers import build_panel, get_lens, list_lenses, list_panel_presets
from .ui import (
    LiveRunRenderer,
    console,
    render_completion,
    render_doctor,
    render_dry_run,
    render_launch_header,
    render_runtime_list,
    render_effort_slider,
    select_effort_slider,
)
from .workflow import apply_gateway_estimates, compile_plan


class ThinkTankGroup(TyperGroup):
    def resolve_command(self, ctx: click.Context, args: list[str]):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if args and not args[0].startswith("-"):
                return super().resolve_command(ctx, ["ask", *args])
            raise


app = typer.Typer(
    cls=ThinkTankGroup,
    add_completion=False,
    no_args_is_help=True,
    context_settings={
        "help_option_names": ["-h", "--help"],
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
runtimes_app = typer.Typer(help="Inspect and run external CLI runtimes.")
sessions_app = typer.Typer(help="Manage long-running sessions.")
personas_app = typer.Typer(help="Inspect thinker persona cards.")
thinkers_app = typer.Typer(help="Inspect public thinker lenses.")
workflows_app = typer.Typer(help="Inspect workflow templates.")
schemas_app = typer.Typer(help="Inspect ATHENAEUM output schemas.")
daemon_app = typer.Typer(help="Run or inspect the long-running session daemon.")
providers_app = typer.Typer(help="Inspect API providers and routing.")
config_app = typer.Typer(help="Create and inspect thinktank.toml configuration.")
app.add_typer(runtimes_app, name="runtimes")
app.add_typer(sessions_app, name="sessions")
app.add_typer(personas_app, name="personas")
app.add_typer(thinkers_app, name="thinkers")
app.add_typer(workflows_app, name="workflows")
app.add_typer(schemas_app, name="schemas")
app.add_typer(daemon_app, name="daemon")
app.add_typer(providers_app, name="providers")
app.add_typer(config_app, name="config")


BUILTIN_PERSONAS = {
    "einstein": "Limit cases, invariance, and hidden assumptions.",
    "feynman": "First-principles reconstruction and plain-language checks.",
    "kahneman": "Bias audit, base rates, and confidence calibration.",
    "ostrom": "Institutional incentives and governance fit.",
    "taleb": "Tail risk, fragility, and convexity.",
    "popper": "Falsifiability and risky predictions.",
}

BUILTIN_WORKFLOWS = {
    "auto": "research -> debate -> draft -> verify -> court -> revise -> emit",
    "review": "draft -> verify -> court -> opinion",
    "evolve": "seed archive -> mutate -> evaluate -> admit elites",
    "science": "hypothesize -> methods gate -> execute -> analyze -> court",
}


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    effort: Annotated[str, typer.Option("--effort", help="low|medium|high|vhigh|max|ultra plus iq-* aliases")] = "high",
    iq: Annotated[str | None, typer.Option("--iq", help="IQ-style effort alias, e.g. 140, iq160, iq-high")] = None,
    runtime: Annotated[str, typer.Option("--runtime", help="auto|minimal|api|opencode|codex|agy|claude|gemini")] = "auto",
