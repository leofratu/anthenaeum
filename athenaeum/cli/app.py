from __future__ import annotations

import click
import typer
from typer.core import TyperGroup


class ThinkTankGroup(TyperGroup):
    """Root group: bare questions resolve to ``ask``; ordered help."""

    def resolve_command(self, ctx: click.Context, args: list[str]):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if args and not args[0].startswith("-"):
                return super().resolve_command(ctx, ["ask", *args])
            raise

    def list_commands(self, ctx: click.Context) -> list[str]:
        names = list(super().list_commands(ctx))
        preferred = [
            "ask",
            "interactive",
            "doctor",
            "effort",
            "setup",
            "evolve",
            "review",
            "science",
            "resume",
            "watch",
            "poke",
            "reasoning",
            "runtimes",
            "sessions",
            "personas",
            "thinkers",
            "workflows",
            "schemas",
            "providers",
            "config",
            "daemon",
        ]
        ordered = [name for name in preferred if name in names]
        ordered.extend(name for name in names if name not in ordered)
        return ordered


app = typer.Typer(
    cls=ThinkTankGroup,
    add_completion=False,
    no_args_is_help=True,
    help=(
        "[bold]ATHENAEUM[/] — interactive AI think-tank orchestration.\n\n"
        "Compile a plan, route work across providers or agent CLIs, "
        "and emit inspectable reports instead of one-shot answers."
    ),
    epilog=(
        "[bold]Examples[/]\n"
        '  python3 -m athenaeum --minimal --dry-run "Should we ship?"\n'
        "  python3 -m athenaeum interactive\n"
        "  python3 -m athenaeum doctor\n"
        '  python3 -m athenaeum ask --minimal "What is the trade-off?"'
    ),
    rich_markup_mode="rich",
    context_settings={
        "help_option_names": ["-h", "--help"],
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)

runtimes_app = typer.Typer(
    help="Inspect and run external CLI runtimes (opencode, codex, claude, …).",
    no_args_is_help=True,
)
sessions_app = typer.Typer(help="Manage long-running watch sessions.", no_args_is_help=True)
personas_app = typer.Typer(help="Inspect built-in thinker persona cards.", no_args_is_help=True)
thinkers_app = typer.Typer(help="Inspect public thinker lenses and panel presets.", no_args_is_help=True)
workflows_app = typer.Typer(help="Inspect built-in workflow templates.", no_args_is_help=True)
schemas_app = typer.Typer(help="Inspect ATHENAEUM output schemas (JSON).", no_args_is_help=True)
daemon_app = typer.Typer(help="Run or inspect the long-running session daemon.", no_args_is_help=True)
providers_app = typer.Typer(help="Inspect API providers, routes, and readiness.", no_args_is_help=True)
config_app = typer.Typer(help="Create and inspect thinktank.toml configuration.", no_args_is_help=True)

app.add_typer(runtimes_app, name="runtimes")
app.add_typer(sessions_app, name="sessions")
app.add_typer(personas_app, name="personas")
app.add_typer(thinkers_app, name="thinkers")
app.add_typer(workflows_app, name="workflows")
app.add_typer(schemas_app, name="schemas")
app.add_typer(daemon_app, name="daemon")
app.add_typer(providers_app, name="providers")
app.add_typer(config_app, name="config")
