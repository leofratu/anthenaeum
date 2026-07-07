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
    budget: Annotated[float | None, typer.Option("--budget", help="Hard USD budget ceiling.")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Compile and print the workflow only.")] = False,
    out: Annotated[Path, typer.Option("--out", help="Report output path.")] = Path("report.md"),
    config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None,
    mode: Annotated[str, typer.Option("--mode", help="auto|deliberate|decide|brief")] = "auto",
    audience: Annotated[str | None, typer.Option("--audience", help="Audience profile.")] = None,
    panel: Annotated[str | None, typer.Option("--panel", help="Public thinker lenses or preset, e.g. risk or einstein,kahneman.")] = None,
    seed: Annotated[int | None, typer.Option("--seed", help="Deterministic seed.")] = None,
    workflow: Annotated[str, typer.Option("--workflow", help="Workflow template name or path.")] = "auto",
    reasoning_effort: Annotated[str, typer.Option("--reasoning-effort", help="auto|off|low|medium|high|vhigh|xhigh|max")] = "auto",
    no_anim: Annotated[bool, typer.Option("--no-anim", help="Disable live animation.")] = False,
    interactive_effort: Annotated[bool, typer.Option("-i", "--interactive-effort", help="Open the effort slider before run.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON for ask/dry-run.")] = False,
    minimal: Annotated[bool, typer.Option("--minimal", help="Force deterministic in-process runtime.")] = False,
) -> None:
    ctx.obj = {
        "effort": iq or effort,
        "iq": iq,
        "runtime": "minimal" if minimal else runtime,
        "budget": budget,
        "dry_run": dry_run,
        "out": out,
        "config": config,
        "mode": mode,
        "audience": audience,
        "panel": panel,
        "seed": seed,
        "workflow": workflow,
        "reasoning_effort": reasoning_effort,
        "interactive_effort": interactive_effort,
        "no_anim": no_anim or json_output,
        "json_output": json_output,
    }


@app.command()
def ask(
    ctx: typer.Context,
    question: Annotated[str, typer.Argument(help="Question to research.")],
    effort: Annotated[str | None, typer.Option("--effort")] = None,
    iq: Annotated[str | None, typer.Option("--iq", help="IQ-style effort alias, e.g. 140, iq160, iq-high")] = None,
    runtime: Annotated[str | None, typer.Option("--runtime")] = None,
    budget: Annotated[float | None, typer.Option("--budget")] = None,
    dry_run: Annotated[bool | None, typer.Option("--dry-run")] = None,
    out: Annotated[Path | None, typer.Option("--out")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    mode: Annotated[str | None, typer.Option("--mode")] = None,
    audience: Annotated[str | None, typer.Option("--audience")] = None,
    panel: Annotated[str | None, typer.Option("--panel", help="Public thinker lenses or preset, e.g. risk or einstein,kahneman.")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    workflow: Annotated[str | None, typer.Option("--workflow")] = None,
    reasoning_effort: Annotated[str | None, typer.Option("--reasoning-effort", help="auto|off|low|medium|high|vhigh|xhigh|max")] = None,
    no_anim: Annotated[bool | None, typer.Option("--no-anim")] = None,
    interactive_effort: Annotated[bool | None, typer.Option("-i", "--interactive-effort")] = None,
    json_output: Annotated[bool | None, typer.Option("--json")] = None,
    minimal: Annotated[bool, typer.Option("--minimal")] = False,
) -> None:
    parent = ctx.parent.obj if ctx.parent and isinstance(ctx.parent.obj, dict) else {}
    _handle_question(
        question,
        iq or effort or parent.get("effort", "high"),
        "minimal" if minimal else runtime or parent.get("runtime", "minimal"),
        budget if budget is not None else parent.get("budget"),
        dry_run if dry_run is not None else parent.get("dry_run", False),
        out or parent.get("out", Path("report.md")),
        config or parent.get("config"),
        mode or parent.get("mode", "auto"),
        audience if audience is not None else parent.get("audience"),
        panel if panel is not None else parent.get("panel"),
        seed if seed is not None else parent.get("seed"),
        workflow or parent.get("workflow", "auto"),
        reasoning_effort or parent.get("reasoning_effort", "auto"),
        interactive_effort if interactive_effort is not None else parent.get("interactive_effort", False),
        no_anim if no_anim is not None else parent.get("no_anim", False),
        json_output if json_output is not None else parent.get("json_output", False),
    )


@app.command()
def doctor(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    registry = RuntimeRegistry.from_config(config)
    render_doctor([runtime.health() for runtime in registry.all()])
    console.print("\nAPI Providers", style="bold")
    for health in ModelGateway.from_config(config).probe():
        status = "ok" if health.available else "missing"
        console.print(f" {status:<7} {health.name:<12} {health.detail or ''}")


@runtimes_app.command("list")
def runtimes_list(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    registry = RuntimeRegistry.from_config(config)
    rows = [(runtime.name, runtime.definition.binary, runtime.definition.args) for runtime in registry.all()]
    render_runtime_list(rows)


@runtimes_app.command("run")
def runtimes_run(
    runtime: Annotated[str, typer.Argument(help="Runtime name.")],
    prompt: Annotated[str, typer.Argument(help="Task prompt to send to the runtime.")],
    out: Annotated[Path, typer.Option("--out")] = Path("runtime-result.md"),
    config: Annotated[Path | None, typer.Option("--config")] = None,
    deadline: Annotated[int, typer.Option("--deadline")] = 600,
    reasoning_effort: Annotated[str, typer.Option("--reasoning-effort")] = "auto",
) -> None:
    registry = RuntimeRegistry.from_config(config)
    selected = registry.get(runtime)
    task = AgentTask(prompt=prompt, output_schema=_report_schema(), deadline_seconds=deadline, reasoning_effort=get_reasoning_profile(reasoning_effort).name)
    try:
        result = asyncio.run(_run_selected_runtime(selected, task))
    except (RuntimeUnavailable, RuntimeExecutionError, SchemaValidationError) as exc:
        typer.echo(f"runtime failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    out.write_text(_report_text(result.content), encoding="utf-8")
    render_completion(str(out), result, _report_text(result.content))


@app.command()
def effort(
    level: Annotated[str | None, typer.Argument(help="Optional effort level.")] = None,
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
    table = [(name, profile.tagline, profile.scale_strategy, f"${profile.default_budget:.2f}") for name, profile in EFFORTS.items()]
    for name, tagline, scale, budget_text in table:
        console.print(f"{name:<7} {tagline:<18} {scale:<14} {budget_text}")


@app.command("reasoning")
def reasoning(level: Annotated[str | None, typer.Argument(help="Optional reasoning effort level.")] = None) -> None:
    if level:
        profile = get_reasoning_profile(level)
        console.print(f"[bold]{profile.name}[/] - {profile.description}")
        console.print(f"openai={profile.openai_effort or 'default'} · anthropic_budget={profile.anthropic_budget_tokens} · google_budget={profile.google_thinking_budget}")
        return
    for name, profile in REASONING_PROFILES.items():
        console.print(f"{name:<7} {profile.description}")


@app.command("interactive")
def interactive(
    runtime: Annotated[str, typer.Option("--runtime")] = "auto",
    effort: Annotated[str, typer.Option("--effort")] = "high",
    iq: Annotated[str | None, typer.Option("--iq", help="IQ-style effort alias, e.g. 140, iq160, iq-high")] = None,
    reasoning_effort: Annotated[str, typer.Option("--reasoning-effort")] = "auto",
    budget: Annotated[float | None, typer.Option("--budget")] = None,
    audience: Annotated[str | None, typer.Option("--audience")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    defaults = _config_defaults(config)
    state = InteractiveState(
        provider=defaults.get("provider"),
        model=defaults.get("model"),
        review_model=defaults.get("review_model"),
        base_url=defaults.get("base_url", DEFAULT_BASE_URL),
        runtime=runtime,
        effort=get_effort(iq or effort).name,
        reasoning_effort=get_reasoning_profile(reasoning_effort if reasoning_effort != "auto" else defaults.get("reasoning_effort", "auto")).name,
        network_access=defaults.get("network_access", "auto"),
        storage_preference=defaults.get("storage_preference", "default"),
        budget=budget,
        audience=audience,
    )
    console.print("ATHENAEUM interactive. Use /help for commands, /exit to quit.", style="bold")
    while True:
        try:
            line = Prompt.ask("[bold medium_purple2]thinktank[/]")
        except (EOFError, KeyboardInterrupt):
            console.print("leaving interactive mode")
            return
        result = handle_interactive_line(line, state)
        if result.message:
            console.print(result.message)
        if result.action == "exit":
            return
        if result.action == "help":
            continue
        if result.action == "doctor":
            doctor(config)
            continue
        if result.action == "select_effort":
            state.effort = select_effort_slider(state.effort)
            console.print(f"iq=effort:{state.effort}")
            continue
        if result.action == "save_config":
            _write_interactive_config(Path(result.target or "thinktank.toml"), state)
            continue
        if result.action == "resume":
            if not result.target:
                console.print("usage: /resume <run-id>")
                continue
            _print_resume_state(result.target)
            continue
        if result.action == "plan" and result.question:
            _handle_question(
                result.question,
                state.effort,
                state.runtime,
                state.budget,
                True,
                Path("report.md"),
                config,
                state.mode,
                state.audience,
                None,
                None,
                "auto",
                state.reasoning_effort,
                False,
                True,
                False,
            )
            continue
        if result.action in {"run", "dry_run"} and result.question:
            answer = _handle_question(
                result.question,
                state.effort,
                state.runtime,
                state.budget,
                result.action == "dry_run",
                Path("report.md"),
                config,
                state.mode,
                state.audience,
                None,
                None,
                "auto",
                state.reasoning_effort,
                False,
                True,
                False,
            )
            if result.action == "run" and answer:
                console.rule("Answer", style="grey42")
                console.print(answer)


@app.command()
def evolve(
    prompt: Annotated[str, typer.Argument(help="Idea or thesis prompt.")],
    generations: Annotated[int, typer.Option("--generations")] = 6,
    axes: Annotated[str, typer.Option("--axes")] = "novelty,risk,horizon",
    out: Annotated[Path, typer.Option("--out")] = Path("evolve.md"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    seed: Annotated[int, typer.Option("--seed")] = 0,
) -> None:
    axis_list = [axis.strip() for axis in axes.split(",") if axis.strip()]
    if not axis_list:
        axis_list = ["novelty", "risk", "horizon"]
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="athenaeum-dryrun-") as temp:
            output = DeterministicLoopEngine(RunContext(prompt, "dryrun", "high", "evolve", None, seed, Path(temp))).run_evolve(prompt, generations, axis_list)
        console.print(output.report_markdown)
        return
    artifacts = _mode_artifacts(prompt, "evolve", seed)
    engine = DeterministicLoopEngine(RunContext(prompt, artifacts.run_id, "high", "evolve", None, seed, artifacts.artifacts))
    artifacts.append_journal("run_start", {"mode": "evolve", "prompt": prompt})
    output = engine.run_evolve(prompt, generations, axis_list)
    artifacts.append_journal("run_complete", {"out": str(out), "archive": len(output.archive)})
    artifacts.write_manifest()
    _write_output(out, output.report_markdown, output.model_dump(mode="json"))


@app.command()
def review(
    file: Annotated[Path, typer.Argument(help="Markdown draft to review.")],
    court: Annotated[str, typer.Option("--court")] = "full",
    audience: Annotated[str | None, typer.Option("--audience")] = None,
    out: Annotated[Path, typer.Option("--out")] = Path("review.md"),
) -> None:
    draft = file.read_text(encoding="utf-8")
    artifacts = _mode_artifacts(str(file), "review", 0)
    engine = DeterministicLoopEngine(RunContext(str(file), artifacts.run_id, "high", "review", audience, 0, artifacts.artifacts))
    artifacts.append_journal("run_start", {"mode": "review", "file": str(file)})
    output = engine.run_review(str(file), draft, court, audience)
    artifacts.append_journal("run_complete", {"out": str(out), "verdicts": len(output.court.verdicts)})
    artifacts.write_manifest()
    _write_output(out, output.report_markdown, output.model_dump(mode="json"))


@app.command()
def science(
    hypothesis: Annotated[str, typer.Argument(help="Hypothesis to test.")],
    sandbox: Annotated[Path, typer.Option("--sandbox")] = Path("lab"),
    max_experiments: Annotated[int, typer.Option("--max-experiments")] = 5,
    out: Annotated[Path, typer.Option("--out")] = Path("science.md"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="athenaeum-dryrun-") as temp:
            output = DeterministicLoopEngine(RunContext(hypothesis, "dryrun", "high", "science", None, 0, Path(temp))).run_science(hypothesis, str(sandbox), max_experiments).writeup
        console.print(output.report_markdown)
        return
    sandbox.mkdir(parents=True, exist_ok=True)
    artifacts = _mode_artifacts(hypothesis, "science", 0)
    engine = DeterministicLoopEngine(RunContext(hypothesis, artifacts.run_id, "high", "science", None, 0, artifacts.artifacts))
    artifacts.append_journal("run_start", {"mode": "science", "hypothesis": hypothesis, "sandbox": str(sandbox)})
    run_output = engine.run_science(hypothesis, str(sandbox), max_experiments)
    artifacts.append_journal("run_complete", {"out": str(out), "experiments": len(run_output.results)})
    artifacts.write_manifest()
    _write_output(out, run_output.writeup.report_markdown, run_output.writeup.model_dump(mode="json"))


@app.command()
def watch(
    question: Annotated[str, typer.Argument(help="Question for a long-running session.")],
    daily_budget: Annotated[float, typer.Option("--daily-budget")] = 3.0,
    for_duration: Annotated[str, typer.Option("--for")] = "14d",
) -> None:
    session = SessionRecord(id=new_run_id(), question=question, daily_budget=daily_budget, duration=for_duration)
    SessionStore().create(session)
    console.print(f"started session {session.id}: {question}")


@app.command()
def poke(session_id: Annotated[str, typer.Argument(help="Session id to wake.")]) -> None:
    store = SessionStore()
    if store.get(session_id) is None:
        raise typer.BadParameter(f"unknown session {session_id!r}")
    store.enqueue_wake(session_id, "manual")
    console.print(f"poked session {session_id}")


@app.command()
def resume(
    run_id: Annotated[str, typer.Argument(help="Run id to inspect/resume.")],
    continue_run: Annotated[bool, typer.Option("--continue", help="Continue an incomplete deterministic run.")] = False,
) -> None:
    try:
        state = replay_run(run_id)
    except ResumeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if continue_run and not state.complete:
        _continue_run(run_id, set(state.completed_nodes))
        return
    console.print(f"run {state.run_id}: {'complete' if state.complete else 'incomplete'}")
    console.print(f"events: {state.events} · spent ${state.spent_usd:.2f}")
    console.print(f"artifacts: {len(state.artifacts)}")
    console.print(f"next: {state.next_action}")


@sessions_app.command("list")
def sessions_list() -> None:
    sessions = SessionStore().list()
    if not sessions:
        console.print("no sessions")
        return
    for row in sessions:
        console.print(f"{row.get('id')}  {row.get('status')}  ${row.get('daily_budget')}/day  {row.get('question')}")


@sessions_app.command("show")
def sessions_show(session_id: Annotated[str, typer.Argument()]) -> None:
    row = SessionStore().get(session_id)
    if row is None:
        raise typer.BadParameter(f"unknown session {session_id!r}")
    console.print(json.dumps(row, indent=2, sort_keys=True))


@sessions_app.command("pause")
def sessions_pause(session_id: Annotated[str, typer.Argument()]) -> None:
    _set_session_status(session_id, "paused")


@sessions_app.command("resume")
def sessions_resume(session_id: Annotated[str, typer.Argument()]) -> None:
    _set_session_status(session_id, "running")


@sessions_app.command("stop")
def sessions_stop(session_id: Annotated[str, typer.Argument()]) -> None:
    _set_session_status(session_id, "stopped")


@personas_app.command("list")
def personas_list() -> None:
    for name, summary in BUILTIN_PERSONAS.items():
        console.print(f"{name:<10} {summary}")


@personas_app.command("show")
def personas_show(name: Annotated[str, typer.Argument()]) -> None:
    key = name.lower()
    if key not in BUILTIN_PERSONAS:
        raise typer.BadParameter(f"unknown persona {name!r}")
    console.print(f"[bold]{key}[/]\n{BUILTIN_PERSONAS[key]}")


@thinkers_app.command("list")
def thinkers_list() -> None:
    for lens in list_lenses():
        console.print(f"{lens.key:<10} {lens.short_style}")


@thinkers_app.command("show")
def thinkers_show(name: Annotated[str, typer.Argument()]) -> None:
    try:
        lens = get_lens(name)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(lens.prompt_block())


@thinkers_app.command("presets")
def thinkers_presets() -> None:
    for preset in list_panel_presets():
        console.print(f"{preset.key:<12} {','.join(preset.lenses):<72} {preset.use}")


@thinkers_app.command("panel")
def thinkers_panel(names: Annotated[str, typer.Argument(help="Comma-separated thinker lens names or a preset.")]) -> None:
    try:
        panel = build_panel(names)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(panel.prompt())


@workflows_app.command("list")
