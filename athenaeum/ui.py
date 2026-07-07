from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .effort import EffortProfile
from .effort import EFFORTS
from .runtime.models import AgentEvent, AgentResult
from .runtime.models import RuntimeHealth
from .workflow import ExecutionPlan


console = Console()


@dataclass(frozen=True)
class UiGlyphs:
    logo: str = "◈"
    ok: str = "✓"
    fail: str = "✗"
    warn: str = "!"
    queued: str = "·"
    gear: str = "⚙"


@dataclass(frozen=True)
class UiTheme:
    accent: str
    glyphs: UiGlyphs
    color: bool = True


def make_theme(effort: EffortProfile | None = None) -> UiTheme:
    if _ascii_only():
        return UiTheme(accent="white", glyphs=UiGlyphs("#", "ok", "x", "!", ".", "cfg"), color=False)
    return UiTheme(accent=effort.accent if effort else "medium_purple2", glyphs=UiGlyphs())


def render_launch_header(
    question: str,
    effort: EffortProfile,
    budget: float,
    runtime: str,
    *,
    run_id: str | None = None,
    sanity: str | None = None,
    runtimes: list[str] | None = None,
    reasoning_effort: str | None = None,
) -> None:
    theme = make_theme(effort)
    header = Table.grid(expand=True)
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        Text(f"{theme.glyphs.logo} ATHENAEUM", style=f"{theme.accent} bold"),
        Text(f"run {run_id}" if run_id else "", style="grey58"),
    )
    console.print(header)
    console.rule(style="grey42")
    console.print(f"Q  {question}")
    reasoning = f" · reasoning {reasoning_effort}" if reasoning_effort else ""
    console.print(f"{theme.glyphs.gear}  auto workflow · effort {effort.name}{reasoning} · budget ${budget:.2f} · runtime {runtime}")
    if sanity:
        runtime_text = f" · runtimes: {', '.join(runtimes or [runtime])}" if runtimes else ""
        console.print(f"{theme.glyphs.ok}  sanity {sanity}{runtime_text}", style="green")


def render_dry_run(plan: ExecutionPlan) -> None:
    theme = make_theme(plan.effort)
    render_launch_header(plan.question, plan.effort, plan.budget, plan.runtime, sanity="S1-S9 stub passed", reasoning_effort=plan.reasoning_effort)
    if plan.planner:
        complexity = plan.planner.get("complexity_rating", {})
        diversity = plan.planner.get("provider_runtime_diversity", {})
        console.print(
            f"plan  {plan.planner.get('summary', 'planner preview ready')} "
            f"· complexity {complexity.get('label', '?')}:{complexity.get('score', '?')} "
            f"· experts {plan.planner.get('expert_panel_size', '?')} "
            f"· diversity {diversity.get('providers', '?')}p/{diversity.get('runtimes', '?')}r "
            f"· suggested ${float(plan.planner.get('suggested_budget', plan.budget)):.2f}",
            style="grey58",
        )
    console.print(_build_plan_tree(plan, theme))
    table = Table(title="Dry Run", show_header=True, header_style="bold")
    table.add_column("node")
    table.add_column("runtime")
    table.add_column("resolved model")
    table.add_column("schema")
    table.add_column("est tokens", justify="right")
    table.add_column("est $", justify="right")
    table.add_column("detail")
    for node in plan.nodes:
        table.add_row(
            node.name,
            node.runtime,
            node.capability,
            node.output_schema,
            str(node.estimated_tokens),
            f"${node.estimated_cost:.2f}",
            node.detail,
        )
    table.add_row("total", "", "", "", "", f"${plan.estimated_cost:.2f}", "", style="bold")
    console.print(table)


def render_doctor(healths: list[RuntimeHealth]) -> None:
    theme = make_theme()
    console.print(Text("Runtime Doctor", style=f"{theme.accent} bold"))
    for health in healths:
        status = theme.glyphs.ok if health.available else theme.glyphs.fail
        style = "green" if health.available else "red"
        detail = (health.version or health.detail or "found") if health.available else (health.detail or "not found")
        console.print(Text(f" {status} {health.name:<10} {health.binary:<12} {detail}", style=style))
        if not health.available and health.fix:
            console.print(Text(f"   fix: {health.fix}", style="grey58"))
