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


def render_runtime_list(rows: list[tuple[str, str, tuple[str, ...]]]) -> None:
    table = Table(title="Configured Runtimes", show_header=True, header_style="bold")
    table.add_column("runtime")
    table.add_column("binary")
    table.add_column("args")
    for name, binary, args in rows:
        table.add_row(name, binary, " ".join(args))
    console.print(table)


def render_effort_slider(selected: str = "high") -> None:
    console.print(_build_effort_slider(selected))


def select_effort_slider(selected: str = "high") -> str:
    selected = selected if selected in EFFORTS else "high"
    if not console.is_terminal or not sys.stdin.isatty():
        render_effort_slider(selected)
        return selected

    try:
        import select
        import termios
        import tty
    except ImportError:
        render_effort_slider(selected)
        return selected

    labels = list(EFFORTS)
    index = labels.index(selected)
    original = index
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tick = 0

    try:
        tty.setcbreak(fd)
        with Live(
            _build_effort_slider(labels[index], tick, interactive=True),
            console=console,
            refresh_per_second=EFFORTS[labels[index]].refresh_per_second,
            transient=False,
        ) as live:
            while True:
                profile = EFFORTS[labels[index]]
                live.update(_build_effort_slider(profile.name, tick, interactive=True), refresh=True)
                timeout = max(1 / max(profile.refresh_per_second, 3), 0.04)
                readable, _, _ = select.select([sys.stdin], [], [], timeout)
                if readable:
                    key = _read_key(select)
                    if key in {"\r", "\n"}:
                        return labels[index]
                    if key in {"q", "Q", "\x1b"}:
                        return labels[original]
                    if key in {"left", "h", "H", "a", "A"}:
                        index = max(0, index - 1)
                    elif key in {"right", "l", "L", "d", "D"}:
                        index = min(len(labels) - 1, index + 1)
                    elif key in {str(i + 1) for i in range(len(labels))}:
                        index = int(key) - 1
                tick += 1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _read_key(select_module: Any) -> str:
    char = sys.stdin.read(1)
    if char != "\x1b":
        return char
    sequence = char
    while True:
        readable, _, _ = select_module.select([sys.stdin], [], [], 0)
        if not readable:
            break
        sequence += sys.stdin.read(1)
        if len(sequence) >= 3:
            break
    if sequence == "\x1b[D":
        return "left"
    if sequence == "\x1b[C":
        return "right"
    return "\x1b"


def _build_effort_slider(selected: str = "high", tick: int = 0, interactive: bool = False) -> Group:
    profile = EFFORTS[selected]
    theme = make_theme(profile)
    labels = list(EFFORTS)
    index = labels.index(selected)
    marker = "▲" if theme.color else "^"
    filled = "━" if theme.color else "="
    empty = "─" if theme.color else "-"
    tick_mark = "┬" if theme.color else "+"
    segment_width = 9
    positions = [i * segment_width + segment_width // 2 for i in range(len(labels))]
    track_chars: list[str] = []
    for i, _label in enumerate(labels):
        character = filled if i <= index else empty
        track_chars.extend(character for _ in range(segment_width))
    for position in positions:
        track_chars[position] = tick_mark
    track = "".join(track_chars)
    marker_chars = [" " for _ in track]
    marker_chars[positions[index]] = marker
    marker_line = "".join(marker_chars)
    label_line = " ".join(f"{label.upper():^8}" if label == selected else f"{label:^8}" for label in labels)
    preview = _effort_animation_frame(profile, tick)
    separator = " · " if theme.color else " | "
    details = (
        f"{profile.debaters} debaters x {profile.rounds} rounds{separator}"
        f"{profile.skeptics_per_claim} skeptics/claim{separator}{profile.scale_strategy}{separator}"
        f"budget ${profile.default_budget:.2f}"
    )
    lines: list[Any] = [
        Text("IQ / Effort", style=f"{theme.accent} bold"),
        Text("Faster".ljust(len(track) - 7) + "Deeper", style="grey58"),
        Text(marker_line, style=f"{theme.accent} bold"),
        Text(track, style=theme.accent),
        Text(label_line, style="grey70"),
        Text(f"Selected {profile.name.upper()} - {profile.tagline}", style=f"{theme.accent} bold"),
        Text(details, style=f"{theme.accent} bold" if selected in {"vhigh", "max", "ultra"} else "grey82"),
        Text(f"animation {preview}  {profile.refresh_per_second} fps preview", style=theme.accent),
