from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.prompt import Prompt
from rich.table import Table

from athenaeum.cli.app import app
from athenaeum.cli.config_util import config_defaults, write_interactive_config
from athenaeum.cli.run import handle_question_from_state, print_interactive_message
from athenaeum.cli.sessions_util import print_resume_state
from athenaeum.effort import EFFORTS, get_effort
from athenaeum.gateway import ModelGateway
from athenaeum.interactive import DEFAULT_BASE_URL, InteractiveState, format_settings, handle_interactive_line
from athenaeum.reasoning import REASONING_PROFILES, get_reasoning_profile
from athenaeum.runtime import RuntimeRegistry
from athenaeum.ui import (
    console,
    render_doctor,
    render_effort_slider,
    render_effort_table,
    render_interactive_welcome,
    select_effort_slider,
)


@app.command(help="Check runtime binaries and API provider readiness.")
def doctor(
    config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None,
) -> None:
    registry = RuntimeRegistry.from_config(config)
    render_doctor(
        [runtime.health() for runtime in registry.all()],
        providers=list(ModelGateway.from_config(config).probe()),
    )


@app.command(help="Show or select IQ/effort tier (slider, table, or preview).")
def effort(
    level: Annotated[str | None, typer.Argument(help="Optional effort level: low|medium|high|vhigh|max|ultra.")] = None,
    select: Annotated[bool, typer.Option("--select", "-s", help="Open the keyboard-driven effort slider.")] = False,
    list_levels: Annotated[bool, typer.Option("--list", help="Print effort levels as a table.")] = False,
) -> None:
    selected = get_effort(level or "high").name
    if list_levels:
        _print_effort_table()
        return
    if select:
        selected = select_effort_slider(selected)
        console.print(f"selected effort={selected}")
        return
    if level:
        render_effort_slider(selected)
        return
    if console.is_terminal:
        selected = select_effort_slider(selected)
        console.print(f"selected effort={selected}")
        return
    _print_effort_table()


def _print_effort_table() -> None:
    render_effort_table(EFFORTS)
    for name, profile in EFFORTS.items():
        console.print(f"{name:<7} {profile.tagline:<18} {profile.scale_strategy:<14} ${profile.default_budget:.2f}")


@app.command("reasoning", help="Show provider reasoning effort profiles.")
def reasoning(level: Annotated[str | None, typer.Argument(help="Optional reasoning effort level.")] = None) -> None:
    if level:
        profile = get_reasoning_profile(level)
        console.print(f"[bold]{profile.name}[/] - {profile.description}")
        console.print(
            f"openai={profile.openai_effort or 'default'} · "
            f"anthropic_budget={profile.anthropic_budget_tokens} · "
            f"google_budget={profile.google_thinking_budget}"
        )
        return
    table = Table(title="Reasoning Profiles", show_header=True, header_style="bold", border_style="grey42")
    table.add_column("level", style="bold")
    table.add_column("description")
    for name, profile in REASONING_PROFILES.items():
        table.add_row(name, profile.description)
        console.print(f"{name:<7} {profile.description}")
    console.print(table)


@app.command("interactive", help="Polished REPL: /setup, /iq, /plan, /run.")
def interactive(
    runtime: Annotated[str, typer.Option("--runtime", help="auto|minimal|api|opencode|codex|agy|claude|gemini")] = "auto",
    effort: Annotated[str, typer.Option("--effort", help="low|medium|high|vhigh|max|ultra")] = "high",
    iq: Annotated[str | None, typer.Option("--iq", help="IQ-style effort alias, e.g. 140, iq160, iq-high")] = None,
    reasoning_effort: Annotated[str, typer.Option("--reasoning-effort", help="auto|off|low|medium|high|vhigh|xhigh|max")] = "auto",
    budget: Annotated[float | None, typer.Option("--budget", help="Hard USD budget ceiling.")] = None,
    audience: Annotated[str | None, typer.Option("--audience", help="Audience profile.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None,
) -> None:
    state = _build_interactive_state(runtime, effort, iq, reasoning_effort, budget, audience, config)
    render_interactive_welcome(format_settings(state))
    while True:
        try:
            line = Prompt.ask("[bold medium_purple2]athenaeum[/]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            console.print("leaving interactive mode", style="grey58")
            return
        if not _dispatch_interactive(line, state, config):
            return


def _build_interactive_state(
    runtime: str,
    effort: str,
    iq: str | None,
    reasoning_effort: str,
    budget: float | None,
    audience: str | None,
    config: Path | None,
) -> InteractiveState:
    defaults = config_defaults(config)
    selected_reasoning = reasoning_effort if reasoning_effort != "auto" else defaults.get("reasoning_effort", "auto")
    return InteractiveState(
        provider=defaults.get("provider"),
        model=defaults.get("model"),
        review_model=defaults.get("review_model"),
        base_url=defaults.get("base_url", DEFAULT_BASE_URL),
        runtime=runtime,
        effort=get_effort(iq or effort).name,
        reasoning_effort=get_reasoning_profile(selected_reasoning).name,
        network_access=defaults.get("network_access", "auto"),
        storage_preference=defaults.get("storage_preference", "default"),
        budget=budget,
        audience=audience,
    )


def _dispatch_interactive(line: str, state: InteractiveState, config: Path | None) -> bool:
    """Handle one interactive line. Return False to leave the REPL."""
    result = handle_interactive_line(line, state)
    if result.action == "exit":
        console.print(result.message or "leaving interactive mode", style="grey58")
        return False
    if result.action == "noop" and (
        not result.message or result.message.startswith("empty input")
    ):
        console.print(
            result.message or "empty input · type a question, /help, or /exit",
            style="grey58",
        )
        return True
    if result.message:
        print_interactive_message(result.action, result.message)
    if result.action == "help":
        return True
    if result.action == "doctor":
        doctor(config)
        return True
    if result.action == "select_effort":
        state.effort = select_effort_slider(state.effort)
        console.print(f"iq=effort:{state.effort}", style="medium_purple2")
        return True
    if result.action == "save_config":
        write_interactive_config(Path(result.target or "thinktank.toml"), state)
        return True
    if result.action == "resume":
        if not result.target:
            console.print("usage: /resume <run-id>", style="yellow")
            return True
        print_resume_state(result.target)
        return True
    if result.action == "plan" and result.question:
        handle_question_from_state(result.question, state, config, dry_run=True)
        return True
    if result.action in {"run", "dry_run"} and result.question:
        answer = handle_question_from_state(
            result.question,
            state,
            config,
            dry_run=result.action == "dry_run",
        )
        if result.action == "run" and answer:
            console.rule("Answer", style="grey42")
            console.print(answer)
        return True
    return True
