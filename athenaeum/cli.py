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
def workflows_list() -> None:
    for name, summary in BUILTIN_WORKFLOWS.items():
        console.print(f"{name:<8} {summary}")


@workflows_app.command("show")
def workflows_show(name: Annotated[str, typer.Argument()]) -> None:
    key = name.lower()
    if key not in BUILTIN_WORKFLOWS:
        raise typer.BadParameter(f"unknown workflow {name!r}")
    console.print(f"[bold]{key}[/]\n{BUILTIN_WORKFLOWS[key]}")


@schemas_app.command("list")
def schemas_list() -> None:
    for name in sorted(OUTPUT_MODELS):
        console.print(name)


@schemas_app.command("show")
def schemas_show(name: Annotated[str, typer.Argument()]) -> None:
    console.print(json.dumps(output_schema(name), indent=2, sort_keys=True))


@providers_app.command("list")
def providers_list(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    gateway = ModelGateway.from_config(config)
    console.print("Routes", style="bold")
    for capability, route in gateway.routes.items():
        console.print(f" {capability:<13} {' -> '.join(route)}")
    console.print("\nProviders", style="bold")
    for health in gateway.probe():
        console.print(f" {health.name:<12} {'available' if health.available else 'missing'}  models={','.join(health.models) or '-'}")


@providers_app.command("example-config")
def providers_example_config() -> None:
    typer.echo(generate_example_config())


@providers_app.command("init")
def providers_init(out: Annotated[Path, typer.Option("--out", help="Config file to write.")] = Path("thinktank.toml")) -> None:
    if out.exists():
        raise typer.BadParameter(f"{out} already exists")
    out.write_text(generate_example_config() + "\n", encoding="utf-8")
    console.print(f"wrote {out}")


@config_app.command("example")
def config_example() -> None:
    typer.echo(generate_example_config())


@config_app.command("init")
def config_init(out: Annotated[Path, typer.Option("--out", help="Config file to write.")] = Path("thinktank.toml")) -> None:
    if out.exists():
        raise typer.BadParameter(f"{out} already exists")
    out.write_text(generate_example_config() + "\n", encoding="utf-8")
    console.print(f"wrote {out}")


@app.command("setup")
def setup(
    out: Annotated[Path, typer.Option("--out", help="Config file to write.")] = Path("thinktank.toml"),
    provider: Annotated[str | None, typer.Option("--provider", help="Provider name.")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Primary model.")] = None,
    review_model: Annotated[str | None, typer.Option("--review-model", help="Review model.")] = None,
    model_reasoning: Annotated[str | None, typer.Option("--model-reasoning", "--reasoning", help="Advanced provider reasoning override.")] = None,
    base_url: Annotated[str | None, typer.Option("--base-url", help="OpenAI-compatible base URL.")] = None,
    network: Annotated[str | None, typer.Option("--network", help="enabled|disabled|auto.")] = None,
    disable_storage: Annotated[bool | None, typer.Option("--disable-storage/--store-responses", help="Disable API response storage.")] = None,
    goals: Annotated[bool | None, typer.Option("--goals/--no-goals", help="Enable goal tracking.")] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing config file.")] = False,
) -> None:
    if out.exists() and not force:
        raise typer.BadParameter(f"{out} already exists")
    provider = provider or Prompt.ask("Provider", default="OpenAI")
    model = model or Prompt.ask("Model", default="gpt-5.5")
    review_model = review_model or Prompt.ask("Review model", default=model)
    reasoning = get_reasoning_profile(model_reasoning or Prompt.ask("Advanced model reasoning", default="xhigh")).name
    base_url = base_url or Prompt.ask("Base URL", default="https://openapi.junliai.org")
    network = network or Prompt.ask("Network access", default="enabled")
    disable_storage = (
        _prompt_bool("Disable response storage", default=True)
        if disable_storage is None
        else disable_storage
    )
    goals = _prompt_bool("Enable goals", default=True) if goals is None else goals
    config_text = _primary_config_text(provider, model, review_model, reasoning, base_url, network, disable_storage, goals)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(config_text + "\n", encoding="utf-8")
    console.print(f"wrote {out}")


@daemon_app.command("run")
def daemon_run(
    once: Annotated[bool, typer.Option("--once", help="Consume currently queued wakes and exit.")] = False,
    foreground: Annotated[bool, typer.Option("--foreground", help="Run a foreground daemon loop.")] = False,
) -> None:
    if not once and not foreground:
        raise typer.BadParameter("use --once or --foreground")
    processed = _consume_due_wakes()
    console.print(f"processed {processed} wake(s)")
    if foreground:
        console.print("foreground daemon loop is scaffolded; use --once for deterministic tests")


@daemon_app.command("status")
def daemon_status() -> None:
    wakes = SessionStore().due_wakes()
    console.print(f"queued wakes: {len(wakes)}")


@daemon_app.command("install")
def daemon_install() -> None:
    console.print("launchd/systemd installation is scaffolded; run `thinktank daemon run --once` for local processing")


def _consume_due_wakes() -> int:
    store = SessionStore()
    wakes = store.due_wakes()
    for wake in wakes:
        store.consume_wake(str(wake["id"]))
    return len(wakes)


def _write_output(path: Path, markdown: str, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    json_path = path.with_suffix(path.suffix + ".json") if path.suffix else Path(f"{path}.json")
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    console.print(f"wrote {path}")
    console.print(f"schema JSON {json_path}")


def _emit_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True))


def _primary_config_text(
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


def _write_interactive_config(path: Path, state: InteractiveState) -> None:
    provider = state.provider or "OpenAI"
    model = state.model or "gpt-5.5"
    review_model = state.review_model or model
    reasoning = _reasoning_for_interactive_config(state)
    network = _config_network_value(state.network_access)
    disable_storage = state.storage_preference.lower() in {
        "disabled",
        "disable",
        "no-response-storage",
        "no_storage",
        "off",
        "private",
        "true",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _primary_config_text(provider, model, review_model, reasoning, state.base_url, network, disable_storage, True) + "\n",
        encoding="utf-8",
    )
    console.print(f"wrote {path}")


def _reasoning_for_interactive_config(state: InteractiveState) -> str:
    if state.reasoning_effort != "auto":
        return get_reasoning_profile(state.reasoning_effort).name
    if state.effort in {"vhigh", "max", "ultra"}:
        return "xhigh"
    if state.effort == "medium":
        return "medium"
    if state.effort == "low":
        return "low"
    return "high"


def _config_network_value(network_access: str) -> str:
    if network_access == "disabled":
        return "disabled"
    return "enabled" if network_access == "enabled" else "enabled"


def _prompt_bool(label: str, default: bool) -> bool:
    default_text = "true" if default else "false"
    return Prompt.ask(label, default=default_text).strip().lower() in {"1", "true", "yes", "y", "on"}


def _run_id(question: str, seed: int | None) -> str:
    if seed is None:
        return new_run_id()
    return hashlib.sha256(f"{seed}|{question}".encode("utf-8")).hexdigest()[:8]


def _mode_artifacts(subject: str, mode: str, seed: int | None) -> RunArtifacts:
    artifacts = RunArtifacts(_run_id(f"{mode}|{subject}", seed))
    artifacts.prepare()
    return artifacts


def _set_session_status(session_id: str, status: str) -> None:
    try:
        SessionStore().set_status(session_id, status)
    except KeyError as exc:
        raise typer.BadParameter(f"unknown session {session_id!r}")
    console.print(f"{session_id} {status}")


def _print_resume_state(run_id: str) -> None:
    try:
        state = replay_run(run_id)
    except ResumeError as exc:
        console.print(str(exc), style="red")
        return
    console.print(f"run {state.run_id}: {'complete' if state.complete else 'incomplete'}")
    console.print(f"events: {state.events} · spent ${state.spent_usd:.2f} · next: {state.next_action}")


def _config_defaults(path: Path | None) -> dict[str, str]:
    data = load_config(path)
    provider = data.get("model_provider")
    model = data.get("model")
    review_model = data.get("review_model")
    reasoning = data.get("model_reasoning_effort")
    network = data.get("network_access")
    base_url = _active_provider_base_url(data, provider)
    storage = "no-response-storage" if data.get("disable_response_storage") is True else "default"
    defaults: dict[str, str] = {}
    if isinstance(provider, str):
        defaults["provider"] = provider
    if isinstance(model, str):
        defaults["model"] = model
        defaults["route_model"] = model if "/" in model else f"{provider}/{model}" if isinstance(provider, str) else model
    if isinstance(review_model, str):
        defaults["review_model"] = review_model
        defaults["route_review_model"] = review_model if "/" in review_model else f"{provider}/{review_model}" if isinstance(provider, str) else review_model
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


def _active_provider_base_url(data: dict[str, object], provider: object) -> str | None:
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
            if isinstance(candidate, dict) and isinstance(candidate.get("name"), str) and candidate["name"].lower() == provider_lower:
                raw = candidate
                break
    if isinstance(raw, dict) and isinstance(raw.get("base_url"), str):
        return raw["base_url"]
    return None


def _thinker_panel_prompt(panel: str | None) -> str | None:
    if not panel:
        return None
    try:
        return build_panel(panel).prompt()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _runtime_with_fallback(registry: RuntimeRegistry, requested_runtime, requested_health, gateway: ModelGateway):
    if requested_health.available or requested_runtime.name == "minimal":
        return requested_runtime
    runtime = ApiRuntime(gateway)
    if runtime.health().available:
        return runtime
    return registry.get("minimal")


def _continue_run(run_id: str, completed_nodes: set[str]) -> None:
    artifacts = RunArtifacts(run_id)
    plan_path = artifacts.artifacts / "plan.json"
    if not plan_path.exists():
        raise typer.BadParameter(f"run {run_id!r} has no plan artifact")
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    effort = get_effort(data.get("effort", "high"))
    plan = compile_plan(
        data.get("question", ""),
        effort,
        data.get("runtime", "minimal"),
        float(data.get("budget", effort.default_budget)),
        data.get("mode", "auto"),
        data.get("audience"),
        data.get("seed"),
        data.get("workflow", "auto"),
        data.get("reasoning_effort", "auto"),
        data.get("planner") if isinstance(data.get("planner"), dict) else None,
    )
    context = RunContext(plan.question, run_id, effort.name, plan.mode, plan.audience, plan.seed or 0, artifacts.artifacts)
    artifacts.append_journal("run_resume", {"completed_nodes": sorted(completed_nodes)})
    result = LocalConductor(plan, artifacts, context).run(completed_nodes).report
    artifacts.write_markdown("report.resumed.md", result.report_markdown)
    artifacts.write_ledger("minimal", plan.budget, 0.0)
    artifacts.append_journal("run_complete", {"out": "runs/%s/artifacts/report.resumed.md" % run_id})
    artifacts.write_manifest()
    console.print(f"resumed run {run_id}: complete")


def _handle_question(
    question: str,
    effort_name: str,
