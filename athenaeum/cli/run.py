"""Question execution orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel

from athenaeum.artifacts import RunArtifacts
from athenaeum.cli.config_util import config_defaults
from athenaeum.cli.errors import catch_user_error, exit_error, print_finding, require
from athenaeum.cli.io_util import as_report_text, emit_json, make_run_id
from athenaeum.cli.runtime_util import (
    run_selected_runtime,
    runtime_with_fallback,
    select_requested_runtime,
)
from athenaeum.conductor import LocalConductor, result_from_report
from athenaeum.effort import get_effort
from athenaeum.gateway import BudgetLedger, ModelGateway
from athenaeum.interactive import InteractiveState
from athenaeum.loops.context import RunContext
from athenaeum.planner import plan_run
from athenaeum.reasoning import get_reasoning_profile
from athenaeum.runtime import AgentTask, RuntimeRegistry, Workspace
from athenaeum.runtime.api import ApiRuntime
from athenaeum.runtime.models import (
    RuntimeExecutionError,
    RuntimeUnavailable,
    SchemaValidationError,
)
from athenaeum.sanity import SanityChecker
from athenaeum.schemas import output_schema
from athenaeum.store import CitationDB, ClaimLedger
from athenaeum.thinkers import build_panel
from athenaeum.ui import (
    LiveRunRenderer,
    console,
    render_completion,
    render_dry_run,
    render_error,
    render_hint,
    render_launch_header,
    select_effort_slider,
)
from athenaeum.workflow import apply_gateway_estimates, compile_plan


def thinker_panel_prompt(panel: str | None) -> str | None:
    if not panel:
        return None
    return catch_user_error(lambda: build_panel(panel).prompt())


def print_interactive_message(action: str, message: str) -> None:
    if action == "help":
        console.print(Panel(message, title="Help", border_style="medium_purple2", expand=False))
        return
    if action == "settings" and message.startswith("Setup path:"):
        console.print(Panel(message, title="Setup", border_style="medium_purple2", expand=False))
        return
    if action in {"settings", "status"}:
        if " · " in message and "=" in message and "\n" not in message:
            console.print(Panel(message, title="Settings", border_style="grey42", expand=False))
        else:
            console.print(message, style="grey82")
        return
    if action == "noop" and (message.startswith("unknown") or message.startswith("usage:")):
        render_error(message)
        if message.startswith("unknown"):
            render_hint("Type /help for commands, or ask a question without a slash to run.")
        return
    console.print(message)


def handle_question_from_state(
    question: str,
    state: InteractiveState,
    config: Path | None,
    *,
    dry_run: bool,
) -> str | None:
    return handle_question(
        question,
        state.effort,
        state.runtime,
        state.budget,
        dry_run,
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


def handle_question(
    question: str,
    effort_name: str,
    runtime_name: str,
    budget: float | None,
    dry_run: bool,
    out: Path,
    config: Path | None,
    mode: str,
    audience: str | None,
    panel: str | None,
    seed: int | None,
    workflow: str,
    reasoning_effort: str,
    interactive_effort: bool,
    no_anim: bool,
    json_output: bool,
) -> str | None:
    require(bool(question.strip()), "question must not be empty")
    defaults = config_defaults(config)
    if reasoning_effort == "auto":
        reasoning_effort = defaults.get("reasoning_effort", "auto")

    effort, registry, gateway, requested_runtime, requested_health = catch_user_error(
        lambda: _resolve_run_context(effort_name, runtime_name, config)
    )
    reasoning_profile = catch_user_error(lambda: get_reasoning_profile(reasoning_effort))
    thinker_panel = thinker_panel_prompt(panel)
    if interactive_effort and not json_output:
        effort = get_effort(select_effort_slider(effort.name))

    ceiling = budget if budget is not None else effort.default_budget
    planner_model = {
        "model": defaults.get("model") or "main",
        "provider": defaults.get("provider"),
        "runtime": requested_runtime.name,
    }
    planner_decision = plan_run(question, effort, planner_model, model_reasoning_effort=reasoning_profile.name)
    if budget is None:
        ceiling = planner_decision.suggested_budget
    planner_data = planner_decision.to_dict()
    if defaults.get("route_model") and defaults.get("route_model") == defaults.get("route_review_model"):
        planner_data["allow_self_judge"] = True
        planner_data["self_judge_reason"] = "review_model matches model in primary config"

    plan = catch_user_error(
        lambda: compile_plan(
            question,
            effort,
            requested_runtime.name,
            ceiling,
            mode,
            audience,
            seed,
            workflow,
            reasoning_profile.name,
            planner_data,
        )
    )
    plan = apply_gateway_estimates(plan, gateway)
    sanity = SanityChecker(gateway).check(plan, requested_health)
    if not sanity.ok:
        if json_output:
            emit_json({"ok": False, "sanity": [finding.__dict__ for finding in sanity.findings]})
            raise typer.Exit(2)
        render_error("Sanity checks failed")
        for finding in sanity.errors:
            print_finding(finding.rule, finding.message)
        exit_error(
            f"{len(sanity.errors)} blocking finding(s)",
            hint="Try --minimal --dry-run, or run: python3 -m athenaeum doctor",
        )
    if dry_run:
        if json_output:
            emit_json({"plan": plan.to_dict(), "sanity": [finding.__dict__ for finding in sanity.findings]})
            return None
        render_dry_run(plan)
        return None

    runtime = runtime_with_fallback(registry, requested_runtime, requested_health, gateway)
    if runtime.name != requested_runtime.name:
        plan = catch_user_error(
            lambda: compile_plan(
                question,
                effort,
                runtime.name,
                ceiling,
                mode,
                audience,
                seed,
                workflow,
                reasoning_profile.name,
                planner_data,
            )
        )
        plan = apply_gateway_estimates(plan, gateway)

    return _execute_plan(
        question=question,
        effort=effort,
        runtime=runtime,
        plan=plan,
        ceiling=ceiling,
        out=out,
        config=config,
        mode=mode,
        audience=audience,
        panel=panel,
        seed=seed,
        workflow=workflow,
        thinker_panel=thinker_panel,
        defaults=defaults,
        planner_decision=planner_decision,
        reasoning_profile=reasoning_profile,
        sanity=sanity,
        no_anim=no_anim,
        json_output=json_output,
    )


def _resolve_run_context(
    effort_name: str,
    runtime_name: str,
    config: Path | None,
) -> tuple[Any, RuntimeRegistry, ModelGateway, Any, Any]:
    effort = get_effort(effort_name)
    registry = RuntimeRegistry.from_config(config)
    gateway = ModelGateway.from_config(config)
    requested_runtime = select_requested_runtime(runtime_name, registry, gateway)
    return effort, registry, gateway, requested_runtime, requested_runtime.health()


def _execute_plan(
    *,
    question: str,
    effort: Any,
    runtime: Any,
    plan: Any,
    ceiling: float,
    out: Path,
    config: Path | None,
    mode: str,
    audience: str | None,
    panel: str | None,
    seed: int | None,
    workflow: str,
    thinker_panel: str | None,
    defaults: dict[str, str],
    planner_decision: Any,
    reasoning_profile: Any,
    sanity: Any,
    no_anim: bool,
    json_output: bool,
) -> str:
    run_id = make_run_id(question, seed)
    artifacts = RunArtifacts(run_id)
    artifacts.prepare()
    if runtime.name == "api":
        runtime = ApiRuntime(
            ModelGateway.from_config(config, ledger=BudgetLedger.open(artifacts.root / "ledger.json", ceiling))
        )
    artifacts.append_journal(
        "run_start",
        {
            "question": question,
            "runtime": runtime.name,
            "effort": effort.name,
            "reasoning_effort": reasoning_profile.name,
            "planner": planner_decision.to_dict(),
        },
    )
    for warning in sanity.warnings:
        artifacts.append_journal("sanity_warning", {"rule": warning.rule, "message": warning.message})
    artifacts.write_plan(plan.to_dict())
    if not json_output:
        render_launch_header(
            question,
            effort,
            ceiling,
            runtime.name,
            run_id=run_id,
            sanity=sanity.summary(),
            reasoning_effort=reasoning_profile.name,
        )
    task = AgentTask(
        prompt=question_prompt(question, effort.name),
        input_payload={
            "question": question,
            "effort": effort.name,
            "mode": mode,
            "audience": audience,
            "panel": panel,
            "thinker_panel": thinker_panel,
            "planner": planner_decision.to_dict(),
            "network_access": defaults.get("network_access", "auto"),
            "storage_preference": defaults.get("storage_preference", "default"),
            "seed": seed or 0,
            "workflow": workflow,
            "run_id": run_id,
            "artifact_root": str(artifacts.artifacts),
        },
        output_schema=report_schema(),
        budget_usd=ceiling,
        reasoning_effort=reasoning_profile.name,
        model=defaults.get("route_model"),
    )
    try:
        result = _run_task(
            runtime=runtime,
            task=task,
            plan=plan,
            question=question,
            effort_name=effort.name,
            mode=mode,
            audience=audience,
            seed=seed,
            run_id=run_id,
            artifacts=artifacts,
            no_anim=no_anim,
            json_output=json_output,
        )
    except (RuntimeUnavailable, RuntimeExecutionError, SchemaValidationError) as exc:
        artifacts.append_journal("run_failed", {"error": str(exc)})
        exit_error(f"runtime failed: {exc}", hint="Run: python3 -m athenaeum doctor")

    markdown = as_report_text(result.content)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    output_data = result.content if isinstance(result.content, dict) else {"report_markdown": markdown}
    output_data.setdefault("run_id", run_id)
    output_data.setdefault("planner", planner_decision.to_dict())
    output_data.setdefault("claims", [claim.model_dump(mode="json") for claim in result.claims])
    output_data.setdefault("citations", [citation.model_dump(mode="json") for citation in result.citations])
    artifacts.write_output(output_data)
    claim_ledger = ClaimLedger(artifacts.root / "claims.events.jsonl")
    for claim in result.claims:
        claim_ledger.append(claim, "revise", "final report claim status")
    claim_ledger.write_current(artifacts.root / "claims.current.json")
    citation_db = CitationDB()
    for citation in result.citations:
        citation_db.link_run(run_id, citation, node_id="research")
    artifacts.write_ledger(runtime.name, ceiling, result.cost.usd)
    artifacts.append_journal(
        "run_complete",
        {"out": str(out), "claims": len(result.claims), "citations": len(result.citations)},
    )
    artifacts.write_manifest()
    if json_output:
        emit_json({"output": output_data, "run_dir": str(artifacts.root)})
    else:
        render_completion(str(out), result, markdown, str(artifacts.root))
    return markdown


def _run_task(
    *,
    runtime: Any,
    task: AgentTask,
    plan: Any,
    question: str,
    effort_name: str,
    mode: str,
    audience: str | None,
    seed: int | None,
    run_id: str,
    artifacts: RunArtifacts,
    no_anim: bool,
    json_output: bool,
) -> Any:
    if runtime.name == "minimal":
        context = RunContext(question, run_id, effort_name, mode, audience, seed or 0, artifacts.artifacts)
        if json_output:
            return result_from_report(LocalConductor(plan, artifacts, context).run().report)
        with LiveRunRenderer(plan, no_anim=no_anim) as renderer:
            return result_from_report(
                LocalConductor(plan, artifacts, context, renderer.handle_event).run().report
            )
    if json_output:
        return asyncio.run(run_selected_runtime(runtime, task, Workspace(artifacts.workspace), None))
    with LiveRunRenderer(plan, no_anim=no_anim) as renderer:
        return asyncio.run(
            run_selected_runtime(runtime, task, Workspace(artifacts.workspace), renderer.handle_event)
        )


def question_prompt(question: str, effort: str) -> str:
    return (
        "Produce a concise ATHENAEUM research report for the question below. "
        "Include citations or clearly mark claims as unverified when sources are absent.\n\n"
        f"Question: {question}\nEffort: {effort}\n"
    )


def report_schema() -> dict[str, object]:
    return output_schema("report")
