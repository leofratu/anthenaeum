from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.prompt import Prompt

from athenaeum.cli.app import app, config_app, personas_app, providers_app, schemas_app, thinkers_app, workflows_app
from athenaeum.cli.config_util import primary_config_text, prompt_bool
from athenaeum.cli.constants import BUILTIN_PERSONAS, BUILTIN_WORKFLOWS
from athenaeum.cli.io_util import write_new_text_file, write_text_file
from athenaeum.config import generate_example_config
from athenaeum.gateway import ModelGateway
from athenaeum.reasoning import get_reasoning_profile
from athenaeum.schemas import OUTPUT_MODELS, output_schema
from athenaeum.thinkers import build_panel, get_lens, list_lenses, list_panel_presets
from athenaeum.ui import console, render_providers


@personas_app.command("list", help="List built-in persona cards.")
def personas_list() -> None:
    for name, summary in BUILTIN_PERSONAS.items():
        console.print(f"{name:<10} {summary}")


@personas_app.command("show", help="Show one persona card by name.")
def personas_show(name: Annotated[str, typer.Argument(help="Persona name.")]) -> None:
    key = name.lower()
    if key not in BUILTIN_PERSONAS:
        raise typer.BadParameter(f"unknown persona {name!r}")
    console.print(f"[bold]{key}[/]\n{BUILTIN_PERSONAS[key]}")


@thinkers_app.command("list", help="List public thinker lenses.")
def thinkers_list() -> None:
    for lens in list_lenses():
        console.print(f"{lens.key:<10} {lens.short_style}")


@thinkers_app.command("show", help="Show one thinker lens prompt block.")
def thinkers_show(name: Annotated[str, typer.Argument(help="Thinker lens name.")]) -> None:
    try:
        lens = get_lens(name)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(lens.prompt_block())


@thinkers_app.command("presets", help="List ready-made thinker panel presets.")
def thinkers_presets() -> None:
    for preset in list_panel_presets():
        console.print(f"{preset.key:<12} {','.join(preset.lenses):<72} {preset.use}")


@thinkers_app.command("panel", help="Compose a thinker panel from lenses or a preset.")
def thinkers_panel(names: Annotated[str, typer.Argument(help="Comma-separated thinker lens names or a preset.")]) -> None:
    try:
        panel = build_panel(names)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print(panel.prompt())


@workflows_app.command("list", help="List built-in workflow templates.")
def workflows_list() -> None:
    for name, summary in BUILTIN_WORKFLOWS.items():
        console.print(f"{name:<8} {summary}")


@workflows_app.command("show", help="Show one workflow template summary.")
def workflows_show(name: Annotated[str, typer.Argument(help="Workflow template name.")]) -> None:
    key = name.lower()
    if key not in BUILTIN_WORKFLOWS:
        raise typer.BadParameter(f"unknown workflow {name!r}")
    console.print(f"[bold]{key}[/]\n{BUILTIN_WORKFLOWS[key]}")


@schemas_app.command("list", help="List output schema names.")
def schemas_list() -> None:
    for name in sorted(OUTPUT_MODELS):
        console.print(name)


@schemas_app.command("show", help="Print one output schema as JSON.")
def schemas_show(name: Annotated[str, typer.Argument(help="Schema name, e.g. report.")]) -> None:
    console.print(json.dumps(output_schema(name), indent=2, sort_keys=True))


@providers_app.command("list", help="List routes and provider readiness.")
def providers_list(config: Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")] = None) -> None:
    gateway = ModelGateway.from_config(config)
    healths = list(gateway.probe())
    render_providers(gateway.routes, healths)
    console.print("Routes", style="bold")
    for capability, route in gateway.routes.items():
        console.print(f" {capability:<13} {' -> '.join(route)}")
    console.print("\nProviders", style="bold")
    for health in healths:
        status = "available" if health.available else "missing"
        models = ",".join(health.models) or "-"
        console.print(f" {health.name:<12} {status}  models={models}")


@providers_app.command("example-config", help="Print an example thinktank.toml to stdout.")
def providers_example_config() -> None:
    typer.echo(generate_example_config())


@providers_app.command("init", help="Write an example thinktank.toml (refuses overwrite).")
def providers_init(out: Annotated[Path, typer.Option("--out", help="Config file to write.")] = Path("thinktank.toml")) -> None:
    write_new_text_file(out, generate_example_config() + "\n")


@config_app.command("example", help="Print an example thinktank.toml to stdout.")
def config_example() -> None:
    typer.echo(generate_example_config())


@config_app.command("init", help="Write a starter thinktank.toml (refuses overwrite).")
def config_init(out: Annotated[Path, typer.Option("--out", help="Config file to write.")] = Path("thinktank.toml")) -> None:
    write_new_text_file(out, generate_example_config() + "\n")


@app.command("setup", help="Guided wizard to write thinktank.toml (provider, model, network).")
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
        prompt_bool("Disable response storage", default=True)
        if disable_storage is None
        else disable_storage
    )
    goals = prompt_bool("Enable goals", default=True) if goals is None else goals
    config_text = primary_config_text(provider, model, review_model, reasoning, base_url, network, disable_storage, goals)
    write_text_file(out, config_text + "\n", overwrite=True)
