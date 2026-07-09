from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from athenaeum.artifacts import new_run_id
from athenaeum.cli.app import app, daemon_app, runtimes_app, sessions_app
from athenaeum.cli.io_util import as_report_text, mode_artifacts, write_output
from athenaeum.cli.run import report_schema
from athenaeum.cli.runtime_util import run_selected_runtime
from athenaeum.cli.sessions_util import continue_run, set_session_status
from athenaeum.loops import DeterministicLoopEngine
from athenaeum.loops.context import RunContext
from athenaeum.reasoning import get_reasoning_profile
from athenaeum.resume import ResumeError, replay_run
from athenaeum.runtime import AgentTask, RuntimeRegistry
from athenaeum.runtime.models import RuntimeExecutionError, RuntimeUnavailable, SchemaValidationError
from athenaeum.schemas import SessionRecord
from athenaeum.store import SessionStore
from athenaeum.ui import (
    console,
    render_completion,
    render_hint,
    render_resume_state,
    render_runtime_list,
    render_sessions_table,
)


@runtimes_app.command("list", help="List configured CLI runtimes and their binaries.")
def runtimes_list(config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None) -> None:
    registry = RuntimeRegistry.from_config(config)
    rows = [(runtime.name, runtime.definition.binary, runtime.definition.args) for runtime in registry.all()]
    render_runtime_list(rows)


@runtimes_app.command("run", help="Send a prompt to one external CLI runtime and save the report.")
def runtimes_run(
    runtime: Annotated[str, typer.Argument(help="Runtime name.")],
    prompt: Annotated[str, typer.Argument(help="Task prompt to send to the runtime.")],
    out: Annotated[Path, typer.Option("--out", help="Report output path.")] = Path("runtime-result.md"),
    config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None,
    deadline: Annotated[int, typer.Option("--deadline", help="Hard timeout in seconds.")] = 600,
    reasoning_effort: Annotated[str, typer.Option("--reasoning-effort", help="auto|off|low|medium|high|vhigh|xhigh|max")] = "auto",
) -> None:
    registry = RuntimeRegistry.from_config(config)
    selected = registry.get(runtime)
    task = AgentTask(
        prompt=prompt,
        output_schema=report_schema(),
        deadline_seconds=deadline,
        reasoning_effort=get_reasoning_profile(reasoning_effort).name,
    )
    try:
        result = asyncio.run(run_selected_runtime(selected, task))
    except (RuntimeUnavailable, RuntimeExecutionError, SchemaValidationError) as exc:
        typer.echo(f"runtime failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    text = as_report_text(result.content)
    out.write_text(text, encoding="utf-8")
    render_completion(str(out), result, text)


@app.command(help="Evolve ideas through MAP-Elites style archive generations.")
def evolve(
    prompt: Annotated[str, typer.Argument(help="Idea or thesis prompt.")],
    generations: Annotated[int, typer.Option("--generations", help="Number of archive generations.")] = 6,
    axes: Annotated[str, typer.Option("--axes", help="Comma-separated archive axes.")] = "novelty,risk,horizon",
    out: Annotated[Path, typer.Option("--out", help="Report output path.")] = Path("evolve.md"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print report without writing artifacts.")] = False,
    seed: Annotated[int, typer.Option("--seed", help="Deterministic seed.")] = 0,
) -> None:
    axis_list = [axis.strip() for axis in axes.split(",") if axis.strip()]
    if not axis_list:
        axis_list = ["novelty", "risk", "horizon"]
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="athenaeum-dryrun-") as temp:
            output = DeterministicLoopEngine(
                RunContext(prompt, "dryrun", "high", "evolve", None, seed, Path(temp))
            ).run_evolve(prompt, generations, axis_list)
        console.print(output.report_markdown)
        return
    artifacts = mode_artifacts(prompt, "evolve", seed)
    engine = DeterministicLoopEngine(
        RunContext(prompt, artifacts.run_id, "high", "evolve", None, seed, artifacts.artifacts)
    )
    artifacts.append_journal("run_start", {"mode": "evolve", "prompt": prompt})
    output = engine.run_evolve(prompt, generations, axis_list)
    artifacts.append_journal("run_complete", {"out": str(out), "archive": len(output.archive)})
    artifacts.write_manifest()
    write_output(out, output.report_markdown, output.model_dump(mode="json"))


@app.command(help="Review a markdown draft through the reviewer court.")
def review(
    file: Annotated[Path, typer.Argument(help="Markdown draft to review.")],
    court: Annotated[str, typer.Option("--court", help="Court profile, e.g. full.")] = "full",
    audience: Annotated[str | None, typer.Option("--audience", help="Audience profile.")] = None,
    out: Annotated[Path, typer.Option("--out", help="Report output path.")] = Path("review.md"),
) -> None:
    draft = file.read_text(encoding="utf-8")
    artifacts = mode_artifacts(str(file), "review", 0)
    engine = DeterministicLoopEngine(
        RunContext(str(file), artifacts.run_id, "high", "review", audience, 0, artifacts.artifacts)
    )
    artifacts.append_journal("run_start", {"mode": "review", "file": str(file)})
    output = engine.run_review(str(file), draft, court, audience)
    artifacts.append_journal("run_complete", {"out": str(out), "verdicts": len(output.court.verdicts)})
    artifacts.write_manifest()
    write_output(out, output.report_markdown, output.model_dump(mode="json"))


@app.command(help="Run a sandbox science loop for a hypothesis.")
def science(
    hypothesis: Annotated[str, typer.Argument(help="Hypothesis to test.")],
    sandbox: Annotated[Path, typer.Option("--sandbox", help="Sandbox directory for experiments.")] = Path("lab"),
    max_experiments: Annotated[int, typer.Option("--max-experiments", help="Max experiments to run.")] = 5,
    out: Annotated[Path, typer.Option("--out", help="Report output path.")] = Path("science.md"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print report without writing artifacts.")] = False,
) -> None:
    if dry_run:
        with tempfile.TemporaryDirectory(prefix="athenaeum-dryrun-") as temp:
            output = (
                DeterministicLoopEngine(
                    RunContext(hypothesis, "dryrun", "high", "science", None, 0, Path(temp))
                )
                .run_science(hypothesis, str(sandbox), max_experiments)
                .writeup
            )
        console.print(output.report_markdown)
        return
    sandbox.mkdir(parents=True, exist_ok=True)
    artifacts = mode_artifacts(hypothesis, "science", 0)
    engine = DeterministicLoopEngine(
        RunContext(hypothesis, artifacts.run_id, "high", "science", None, 0, artifacts.artifacts)
    )
    artifacts.append_journal("run_start", {"mode": "science", "hypothesis": hypothesis, "sandbox": str(sandbox)})
    run_output = engine.run_science(hypothesis, str(sandbox), max_experiments)
    artifacts.append_journal("run_complete", {"out": str(out), "experiments": len(run_output.results)})
    artifacts.write_manifest()
    write_output(out, run_output.writeup.report_markdown, run_output.writeup.model_dump(mode="json"))


@app.command(help="Start a long-running watch session with a daily budget.")
def watch(
    question: Annotated[str, typer.Argument(help="Question for a long-running session.")],
    daily_budget: Annotated[float, typer.Option("--daily-budget", help="USD budget per day.")] = 3.0,
    for_duration: Annotated[str, typer.Option("--for", help="Session duration, e.g. 14d or 48h.")] = "14d",
) -> None:
    session = SessionRecord(id=new_run_id(), question=question, daily_budget=daily_budget, duration=for_duration)
    SessionStore().create(session)
    console.print(f"started session {session.id}: {question}")
    render_hint(f"Wake it later with: python3 -m athenaeum poke {session.id}")
    render_hint("List sessions: python3 -m athenaeum sessions list")


@app.command(help="Wake a long-running session for another processing cycle.")
def poke(session_id: Annotated[str, typer.Argument(help="Session id to wake.")]) -> None:
    store = SessionStore()
    if store.get(session_id) is None:
        raise typer.BadParameter(f"unknown session {session_id!r}")
    store.enqueue_wake(session_id, "manual")
    console.print(f"poked session {session_id}")
    render_hint("Process queued wakes: python3 -m athenaeum daemon run --once")


@app.command(help="Inspect or continue a previous run from its journal.")
def resume(
    run_id: Annotated[str, typer.Argument(help="Run id to inspect/resume.")],
    continue_run_flag: Annotated[bool, typer.Option("--continue", help="Continue an incomplete deterministic run.")] = False,
) -> None:
    try:
        state = replay_run(run_id)
    except ResumeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if continue_run_flag and not state.complete:
        continue_run(run_id, set(state.completed_nodes))
        return
    render_resume_state(
        state.run_id,
        complete=state.complete,
        events=state.events,
        spent_usd=state.spent_usd,
        artifacts=len(state.artifacts),
        next_action=state.next_action,
    )


@sessions_app.command("list", help="List long-running sessions.")
def sessions_list() -> None:
    sessions = SessionStore().list()
    render_sessions_table(sessions)
    if not sessions:
        return
    for row in sessions:
        console.print(f"{row.get('id')}  {row.get('status')}  ${row.get('daily_budget')}/day  {row.get('question')}")


@sessions_app.command("show", help="Show one session as JSON.")
def sessions_show(session_id: Annotated[str, typer.Argument(help="Session id.")]) -> None:
    row = SessionStore().get(session_id)
    if row is None:
        raise typer.BadParameter(f"unknown session {session_id!r}")
    console.print(json.dumps(row, indent=2, sort_keys=True))


@sessions_app.command("pause", help="Pause a running session.")
def sessions_pause(session_id: Annotated[str, typer.Argument(help="Session id.")]) -> None:
    set_session_status(session_id, "paused")


@sessions_app.command("resume", help="Resume a paused session.")
def sessions_resume(session_id: Annotated[str, typer.Argument(help="Session id.")]) -> None:
    set_session_status(session_id, "running")


@sessions_app.command("stop", help="Stop a session permanently.")
def sessions_stop(session_id: Annotated[str, typer.Argument(help="Session id.")]) -> None:
    set_session_status(session_id, "stopped")


@daemon_app.command("run", help="Process session wakes once or in the foreground.")
def daemon_run(
    once: Annotated[bool, typer.Option("--once", help="Consume currently queued wakes and exit.")] = False,
    foreground: Annotated[bool, typer.Option("--foreground", help="Run a foreground daemon loop.")] = False,
) -> None:
    if not once and not foreground:
        raise typer.BadParameter("use --once or --foreground")
    from athenaeum.cli.sessions_util import consume_due_wakes

    processed = consume_due_wakes()
    console.print(f"processed {processed} wake(s)")
    if foreground:
        console.print("foreground daemon loop is scaffolded; use --once for deterministic tests")


@daemon_app.command("status", help="Show how many session wakes are queued.")
def daemon_status() -> None:
    wakes = SessionStore().due_wakes()
    console.print(f"queued wakes: {len(wakes)}")


@daemon_app.command("install", help="Scaffold OS service install (launchd/systemd).")
def daemon_install() -> None:
    console.print("launchd/systemd installation is scaffolded; run `thinktank daemon run --once` for local processing")
