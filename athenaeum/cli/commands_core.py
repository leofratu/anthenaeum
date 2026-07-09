from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from athenaeum.cli.app import app
from athenaeum.cli.errors import require
from athenaeum.cli.run import handle_question
from athenaeum.ui import console


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
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
) -> None:
    if version:
        from athenaeum import __version__

        console.print(f"athenaeum {__version__}")
        raise typer.Exit(0)
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


@app.command(help="Ask a question and run the think-tank workflow.")
def ask(
    ctx: typer.Context,
    question: Annotated[str, typer.Argument(help="Question to research.")],
    effort: Annotated[str | None, typer.Option("--effort", help="low|medium|high|vhigh|max|ultra plus iq-* aliases")] = None,
    iq: Annotated[str | None, typer.Option("--iq", help="IQ-style effort alias, e.g. 140, iq160, iq-high")] = None,
    runtime: Annotated[str | None, typer.Option("--runtime", help="auto|minimal|api|opencode|codex|agy|claude|gemini")] = None,
    budget: Annotated[float | None, typer.Option("--budget", help="Hard USD budget ceiling.")] = None,
    dry_run: Annotated[bool | None, typer.Option("--dry-run", help="Compile and print the workflow only.")] = None,
    out: Annotated[Path | None, typer.Option("--out", help="Report output path.")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None,
    mode: Annotated[str | None, typer.Option("--mode", help="auto|deliberate|decide|brief")] = None,
    audience: Annotated[str | None, typer.Option("--audience", help="Audience profile.")] = None,
    panel: Annotated[str | None, typer.Option("--panel", help="Public thinker lenses or preset, e.g. risk or einstein,kahneman.")] = None,
    seed: Annotated[int | None, typer.Option("--seed", help="Deterministic seed.")] = None,
    workflow: Annotated[str | None, typer.Option("--workflow", help="Workflow template name or path.")] = None,
    reasoning_effort: Annotated[str | None, typer.Option("--reasoning-effort", help="auto|off|low|medium|high|vhigh|xhigh|max")] = None,
    no_anim: Annotated[bool | None, typer.Option("--no-anim", help="Disable live animation.")] = None,
    interactive_effort: Annotated[bool | None, typer.Option("-i", "--interactive-effort", help="Open the effort slider before run.")] = None,
    json_output: Annotated[bool | None, typer.Option("--json", help="Emit machine-readable JSON.")] = None,
    minimal: Annotated[bool, typer.Option("--minimal", help="Force deterministic in-process runtime.")] = False,
) -> None:
    require(bool(question.strip()), "question must not be empty")
    parent = ctx.parent.obj if ctx.parent and isinstance(ctx.parent.obj, dict) else {}
    handle_question(
        question,
        str(iq or effort or parent.get("effort", "high")),
        "minimal" if minimal else str(runtime or parent.get("runtime", "minimal")),
        budget if budget is not None else parent.get("budget"),
        bool(dry_run if dry_run is not None else parent.get("dry_run", False)),
        out or parent.get("out", Path("report.md")),
        config or parent.get("config"),
        str(mode or parent.get("mode", "auto")),
        audience if audience is not None else parent.get("audience"),
        panel if panel is not None else parent.get("panel"),
        seed if seed is not None else parent.get("seed"),
        str(workflow or parent.get("workflow", "auto")),
        str(reasoning_effort or parent.get("reasoning_effort", "auto")),
        bool(interactive_effort if interactive_effort is not None else parent.get("interactive_effort", False)),
        bool(no_anim if no_anim is not None else parent.get("no_anim", False)),
        bool(json_output if json_output is not None else parent.get("json_output", False)),
    )
