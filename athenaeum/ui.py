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

from . import __version__
from .effort import EFFORTS, EffortProfile
from .runtime.models import AgentEvent, AgentResult, RuntimeHealth
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
    tip: str = "→"


@dataclass(frozen=True)
class UiTheme:
    accent: str
    glyphs: UiGlyphs
    color: bool = True


def make_theme(effort: EffortProfile | None = None) -> UiTheme:
    if _ascii_only():
        return UiTheme(accent="white", glyphs=UiGlyphs("#", "ok", "x", "!", ".", "cfg", "->"), color=False)
    return UiTheme(accent=effort.accent if effort else "medium_purple2", glyphs=UiGlyphs())


def render_banner(subtitle: str | None = None) -> None:
    theme = make_theme()
    title = Text()
    title.append(f"{theme.glyphs.logo} ATHENAEUM", style=f"{theme.accent} bold")
    title.append(f"  v{__version__}", style="grey58")
    console.print(title)
    if subtitle:
        console.print(Text(subtitle, style="grey70"))
    console.rule(style="grey42")


def render_error(message: str) -> None:
    theme = make_theme()
    console.print(Text(f"{theme.glyphs.fail} {message}", style="red bold"))


def render_success(message: str) -> None:
    theme = make_theme()
    console.print(Text(f"{theme.glyphs.ok} {message}", style="green"))


def render_hint(message: str) -> None:
    theme = make_theme()
    console.print(Text(f"{theme.glyphs.tip} {message}", style="grey58"))


def render_key_value_panel(title: str, rows: list[tuple[str, str]], *, border: str | None = None) -> None:
    theme = make_theme()
    table = Table.grid(padding=(0, 2))
    table.add_column(style="grey58", justify="right")
    table.add_column(style="bold")
    for key, value in rows:
        table.add_row(key, value)
    console.print(Panel(table, title=title, border_style=border or theme.accent, expand=False))


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
        Text(f"v{__version__}" + (f" · run {run_id}" if run_id else ""), style="grey58"),
    )
    console.print(header)
    console.rule(style="grey42")
    console.print(Text("Q  ", style="grey58") + Text(question, style="bold"))
    reasoning = f" · reasoning {reasoning_effort}" if reasoning_effort else ""
    console.print(
        f"{theme.glyphs.gear}  auto workflow · effort {effort.name}{reasoning} · budget ${budget:.2f} · runtime {runtime}"
    )
    if sanity:
        runtime_text = f" · runtimes: {', '.join(runtimes or [runtime])}" if runtimes else ""
        console.print(f"{theme.glyphs.ok}  sanity {sanity}{runtime_text}", style="green")


def render_dry_run(plan: ExecutionPlan) -> None:
    theme = make_theme(plan.effort)
    render_launch_header(
        plan.question,
        plan.effort,
        plan.budget,
        plan.runtime,
        sanity="S1-S9 stub passed",
        reasoning_effort=plan.reasoning_effort,
    )
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
    meta = Table.grid(padding=(0, 2))
    meta.add_column(style="grey58", justify="right")
    meta.add_column(style="bold")
    meta.add_row("nodes", str(len(plan.nodes)))
    meta.add_row("workflow", plan.workflow)
    meta.add_row("mode", plan.mode)
    if plan.audience:
        meta.add_row("audience", plan.audience)
    console.print(Panel(meta, title="Plan", border_style="grey42", expand=False))
    console.print(_build_plan_tree(plan, theme))
    table = Table(
        title="Dry Run",
        show_header=True,
        header_style=f"{theme.accent} bold",
        border_style="grey42",
        show_lines=False,
        pad_edge=False,
    )
    table.add_column("#", justify="right", style="grey58")
    table.add_column("node", style="bold")
    table.add_column("runtime")
    table.add_column("resolved model")
    table.add_column("schema")
    table.add_column("est tokens", justify="right")
    table.add_column("est $", justify="right")
    table.add_column("detail", overflow="fold")
    for index, node in enumerate(plan.nodes, start=1):
        table.add_row(
            str(index),
            node.name,
            node.runtime,
            node.capability,
            node.output_schema,
            f"{node.estimated_tokens:,}",
            f"${node.estimated_cost:.2f}",
            node.detail,
        )
    table.add_row("", "total", "", "", "", "", f"${plan.estimated_cost:.2f}", "", style="bold")
    console.print(table)
    within = plan.estimated_cost <= plan.budget
    budget_note = "within budget" if within else "over budget"
    style = "green" if within else "yellow"
    glyph = theme.glyphs.ok if within else theme.glyphs.warn
    console.print(Text(f"{glyph} projected ${plan.estimated_cost:.2f} / ${plan.budget:.2f} ({budget_note})", style=style))
    render_hint("Execute: drop --dry-run  ·  Interactive: python3 -m athenaeum interactive")


def render_doctor(healths: list[RuntimeHealth], providers: list[Any] | None = None) -> None:
    theme = make_theme()
    render_banner("Environment diagnostics")
    console.print(Text("Runtime Doctor", style=f"{theme.accent} bold"))
    table = Table(show_header=True, header_style="bold", border_style="grey42", box=None, padding=(0, 1))
    table.add_column("status", width=6)
    table.add_column("runtime", style="bold", min_width=10)
    table.add_column("binary", min_width=12)
    table.add_column("detail")
    ready = 0
    for health in healths:
        if health.available:
            ready += 1
            status = Text(f"{theme.glyphs.ok}", style="green")
            detail = health.version or health.detail or "found"
            style = "green"
        else:
            status = Text(f"{theme.glyphs.fail}", style="red")
            detail = health.detail or "not found"
            style = "red"
        table.add_row(status, Text(health.name, style=style), health.binary, Text(str(detail), style=style))
        if not health.available and health.fix:
            table.add_row("", "", "", Text(f"fix: {health.fix}", style="grey58"))
    console.print(table)
    ready_style = "green" if ready == len(healths) else "yellow" if ready else "red"
    console.print(Text(f"{ready}/{len(healths)} runtimes ready", style=f"{ready_style} bold"))
    if providers is not None:
        console.print()
        console.print(Text("API Providers", style=f"{theme.accent} bold"))
        provider_table = Table(show_header=True, header_style="bold", border_style="grey42", box=None, padding=(0, 1))
        provider_table.add_column("status", width=8)
        provider_table.add_column("provider", style="bold", min_width=12)
        provider_table.add_column("detail")
        ready_providers = 0
        for health in providers:
            available = bool(getattr(health, "available", False))
            name = str(getattr(health, "name", "?"))
            detail = str(getattr(health, "detail", "") or ("configured" if available else "missing key"))
            status = "ok" if available else "missing"
            style = "green" if available else "red"
            if available:
                ready_providers += 1
            provider_table.add_row(Text(status, style=style), name, Text(detail, style="grey70"))
        console.print(provider_table)
        if providers:
            p_style = "green" if ready_providers == len(providers) else "yellow" if ready_providers else "red"
            console.print(Text(f"{ready_providers}/{len(providers)} providers ready", style=p_style))
    render_hint("Offline path: python3 -m athenaeum --minimal --dry-run \"Your question\"")
    render_hint("Interactive: python3 -m athenaeum interactive")
    render_hint("Setup: python3 -m athenaeum setup")


def render_runtime_list(rows: list[tuple[str, str, tuple[str, ...]]]) -> None:
    theme = make_theme()
    table = Table(
        title="Configured Runtimes",
        show_header=True,
        header_style=f"{theme.accent} bold",
        border_style="grey42",
    )
    table.add_column("runtime", style="bold")
    table.add_column("binary")
    table.add_column("args")
    for name, binary, args in rows:
        table.add_row(name, binary, " ".join(args) or "—")
    console.print(table)


def render_effort_table(efforts: dict[str, EffortProfile] | None = None) -> None:
    theme = make_theme()
    profiles = efforts or EFFORTS
    table = Table(
        title="Effort Levels",
        show_header=True,
        header_style=f"{theme.accent} bold",
        border_style="grey42",
    )
    table.add_column("level", style="bold")
    table.add_column("tagline")
    table.add_column("scale")
    table.add_column("budget", justify="right")
    table.add_column("debaters", justify="right")
    table.add_column("rounds", justify="right")
    for name, profile in profiles.items():
        table.add_row(
            name,
            profile.tagline,
            profile.scale_strategy,
            f"${profile.default_budget:.2f}",
            str(profile.debaters),
            str(profile.rounds),
        )
    console.print(table)


def render_sessions_table(sessions: list[dict[str, Any]]) -> None:
    theme = make_theme()
    if not sessions:
        console.print(Text("no sessions", style="grey58"))
        return
    table = Table(
        title="Sessions",
        show_header=True,
        header_style=f"{theme.accent} bold",
        border_style="grey42",
    )
    table.add_column("id", style="bold")
    table.add_column("status")
    table.add_column("budget/day", justify="right")
    table.add_column("question", overflow="fold")
    for row in sessions:
        status = str(row.get("status", "?"))
        style = {"active": "green", "paused": "yellow", "complete": "grey58"}.get(status, "white")
        table.add_row(
            str(row.get("id", "")),
            Text(status, style=style),
            f"${row.get('daily_budget', 0)}",
            str(row.get("question", "")),
        )
    console.print(table)


def render_resume_state(
    run_id: str,
    *,
    complete: bool,
    events: int,
    spent_usd: float,
    artifacts: int | None = None,
    next_action: str,
) -> None:
    theme = make_theme()
    status = "complete" if complete else "incomplete"
    status_style = "green" if complete else "yellow"
    rows = [
        ("run", run_id),
        ("status", status),
        ("events", str(events)),
        ("spent", f"${spent_usd:.2f}"),
        ("next", next_action),
    ]
    if artifacts is not None:
        rows.insert(4, ("artifacts", str(artifacts)))
    table = Table.grid(padding=(0, 2))
    table.add_column(style="grey58", justify="right")
    table.add_column()
    for key, value in rows:
        if key == "status":
            table.add_row(key, Text(value, style=f"{status_style} bold"))
        else:
            table.add_row(key, value)
    console.print(Panel(table, title="Resume", border_style=theme.accent, expand=False))
    # Keep plain lines for tests/scripts that grep simple text.
    console.print(f"run {run_id}: {status}")
    if artifacts is not None:
        console.print(f"events: {events} · spent ${spent_usd:.2f}")
        console.print(f"artifacts: {artifacts}")
        console.print(f"next: {next_action}")
    else:
        console.print(f"events: {events} · spent ${spent_usd:.2f} · next: {next_action}")


def render_interactive_welcome(settings_line: str) -> None:
    theme = make_theme()
    body = Table.grid(padding=(0, 0))
    body.add_column()
    body.add_row(Text("ATHENAEUM interactive", style=f"{theme.accent} bold"))
    body.add_row(Text("Type a question to run · /help · /plan · /iq · /exit", style="grey70"))
    body.add_row(Text(""))
    body.add_row(Text(settings_line, style="grey58"))
    body.add_row(Text(""))
    body.add_row(Text(f"{theme.glyphs.tip} Offline: /runtime minimal then ask anything", style="grey58"))
    body.add_row(Text(f"{theme.glyphs.tip} Setup: /setup · save with /save-config", style="grey58"))
    console.print(Panel(body, border_style=theme.accent, expand=False, title=f"v{__version__}"))
    # Stable line for scripts/tests.
    console.print("ATHENAEUM interactive. Use /help for commands, /exit to quit.", style="bold")


def render_providers(routes: dict[str, list[str]], healths: list[Any]) -> None:
    theme = make_theme()
    console.print(Text("Routes", style=f"{theme.accent} bold"))
    route_table = Table(show_header=True, header_style="bold", border_style="grey42", box=None, padding=(0, 1))
    route_table.add_column("capability", style="bold", min_width=13)
    route_table.add_column("targets")
    for capability, route in routes.items():
        route_table.add_row(capability, " -> ".join(route))
    console.print(route_table)
    console.print()
    console.print(Text("Providers", style="bold"))
    provider_table = Table(show_header=True, header_style="bold", border_style="grey42", box=None, padding=(0, 1))
    provider_table.add_column("provider", style="bold", min_width=12)
    provider_table.add_column("status")
    provider_table.add_column("models")
    for health in healths:
        available = bool(getattr(health, "available", False))
        name = str(getattr(health, "name", "?"))
        models = getattr(health, "models", None) or []
        status = "available" if available else "missing"
        style = "green" if available else "red"
        provider_table.add_row(name, Text(status, style=style), ",".join(models) or "-")
    console.print(provider_table)


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
    ]
    if selected in {"vhigh", "max", "ultra"}:
        lines.append(Text(_high_effort_note(selected), style=theme.accent))
    if interactive:
        help_text = "<-/-> or h/l to adjust | 1-6 jump | Enter confirm | q/Esc cancel"
        if theme.color:
            help_text = "←/→ or h/l to adjust · 1-6 jump · Enter confirm · q/Esc cancel"
        lines.append(Text(help_text, style="grey58"))
    return Group(*lines)


def _high_effort_note(selected: str) -> str:
    notes = {
        "vhigh": "provider-diverse council animation for broad review",
        "max": "orbit sweep marks tournament-style review",
        "ultra": "red-team pulse marks replication and adversarial review",
    }
    return notes.get(selected, "")


def _effort_animation_frame(profile: EffortProfile, tick: int) -> str:
    if _ascii_only():
        frames = {
            "low": (".", "..", "..."),
            "medium": ("-", "\\", "|", "/"),
            "high": ("_", "__", "___", "__"),
            "vhigh": ("oooo", "oOOo", "OOOo", "oOOo"),
            "max": ("o....", ".o...", "..O..", "...o.", "....o", "...o.", "..O..", ".o..."),
            "ultra": ("x-x", "-x-", "XXX", "-x-"),
        }
        values = frames.get(profile.name, frames["high"])
        return values[tick % len(values)]
    frames = {
        "low": ("·  ", "·· ", "···"),
        "medium": ("⠋", "⠙", "⠸", "⠴", "⠦", "⠇"),
        "high": ("▁▂▃▅▃", "▂▃▅▃▂", "▃▅▃▂▁", "▂▃▅▃▂"),
        "vhigh": ("◐◓◑◒", "◓◑◒◐", "◑◒◐◓", "◒◐◓◑"),
        "max": ("◉○∘∙∘○", "○◉○∘∙∘", "∘○◉○∘∙", "∙∘○◉○∘", "∘∙∘○◉○", "○∘∙∘○◉"),
        "ultra": ("◇◆◇  ✓", "◆◇◆  ⇄", "◇◆◇  ⚑", "◆◇◆  ✓"),
    }
    values = frames.get(profile.name, frames["high"])
    return values[tick % len(values)]


def render_completion(path: str, result: AgentResult, report_text: str, run_dir: str | None = None) -> None:
    theme = make_theme()
    words = len(report_text.split())
    summary = Table.grid(padding=(0, 1))
    summary.add_column()
    summary.add_row(Text(f"{theme.glyphs.ok} Report ready  {path} · {words:,} words", style="green bold"))
    summary.add_row(Text(f"claims: {len(result.claims)} · citations: {len(result.citations)}", style="grey70"))
    summary.add_row(
        Text(
            f"runtime: {result.runtime_meta.runtime} · {result.runtime_meta.duration_seconds:.1f}s · cost ${result.cost.usd:.2f}",
            style="grey70",
        )
    )
    if run_dir:
        summary.add_row(Text(f"artifacts: {run_dir}", style="grey58"))
    console.print(Panel(summary, border_style="green", expand=False, title="Complete"))
    render_hint("Resume later: python3 -m athenaeum resume <run-id>")


class LiveRunRenderer:
    def __init__(self, plan: ExecutionPlan, no_anim: bool = False):
        self.plan = plan
        self.theme = make_theme(plan.effort)
        self.no_anim = no_anim
        self.started = perf_counter()
        self.statuses = {node.name: "queued" for node in plan.nodes}
        self.live: Live | None = None

    def __enter__(self) -> LiveRunRenderer:
        if console.is_terminal and not self.no_anim:
            self.live = Live(self, console=console, refresh_per_second=self.plan.effort.refresh_per_second)
            self.live.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.live is not None:
            self.live.__exit__(exc_type, exc, tb)

    def handle_event(self, event: AgentEvent) -> None:
        if event.kind == "progress" and event.raw:
            node = event.raw.get("node")
            state = event.raw.get("state", "done")
            if isinstance(node, str) and node in self.statuses:
                self.statuses[node] = str(state)
        if self.live is not None:
            self.live.update(self, refresh=True)
        elif event.kind == "progress" and event.message:
            console.print(Text(f"{self.theme.glyphs.ok} {event.message}", style="green"))

    def __rich_console__(self, _console: Console, _options: Any) -> Any:
        yield self.render()

    def render(self) -> Group:
        tree = Tree(Text("deliberation", style=f"{self.theme.accent} bold"))
        tick = int((perf_counter() - self.started) * max(self.plan.effort.refresh_per_second, 1))
        for offset, node in enumerate(self.plan.nodes):
            state = self.statuses[node.name]
            if state == "done":
                glyph = self.theme.glyphs.ok
                style = "green"
            elif state == "running" and not self.no_anim:
                glyph = _effort_animation_frame(self.plan.effort, tick + offset)
                style = self.theme.accent
            else:
                glyph = self.theme.glyphs.queued
                style = "grey58"
            tree.add(Text(f"{glyph} {node.name:<9} {node.detail}", style=style))
        elapsed = perf_counter() - self.started
        footer = Text(f"${self.plan.estimated_cost:.2f} / ${self.plan.budget:.2f} projected · elapsed {elapsed:.1f}s", style="grey58")
        return Group(tree, footer)


def _build_plan_tree(plan: ExecutionPlan, theme: UiTheme) -> Tree:
    tree = Tree(Text("compiled workflow", style=f"{theme.accent} bold"))
    for node in plan.nodes:
        label = f"{theme.glyphs.queued} {node.name} [{node.kind}]"
        branch = tree.add(Text(label, style="grey70"))
        branch.add(Text(f"runtime {node.runtime} · capability {node.capability} · schema {node.output_schema}", style="grey58"))
        if node.max_iterations is not None:
            branch.add(Text(f"max_iterations {node.max_iterations} · convergence {node.convergence}", style="grey58"))
    return tree


def _ascii_only() -> bool:
    return bool(os.environ.get("NO_COLOR")) or (console.encoding or "utf-8").lower() in {"ascii", "us-ascii"}
