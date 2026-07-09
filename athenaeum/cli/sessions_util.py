"""Session daemon helpers and resume display."""

from __future__ import annotations

import json

from athenaeum.artifacts import RunArtifacts
from athenaeum.cli.errors import bad_parameter, require
from athenaeum.conductor import LocalConductor
from athenaeum.effort import get_effort
from athenaeum.loops.context import RunContext
from athenaeum.resume import ResumeError, replay_run
from athenaeum.store import SessionStore
from athenaeum.ui import console, render_error, render_resume_state
from athenaeum.workflow import compile_plan


def consume_due_wakes() -> int:
    store = SessionStore()
    wakes = store.due_wakes()
    for wake in wakes:
        store.consume_wake(str(wake["id"]))
    return len(wakes)


def set_session_status(session_id: str, status: str) -> None:
    try:
        SessionStore().set_status(session_id, status)
    except KeyError as exc:
        bad_parameter(f"unknown session {session_id!r}", cause=exc)
    console.print(f"{session_id} {status}")


def print_resume_state(run_id: str) -> None:
    try:
        state = replay_run(run_id)
    except ResumeError as exc:
        render_error(str(exc))
        return
    render_resume_state(
        state.run_id,
        complete=state.complete,
        events=state.events,
        spent_usd=state.spent_usd,
        next_action=state.next_action,
    )


def continue_run(run_id: str, completed_nodes: set[str]) -> None:
    artifacts = RunArtifacts(run_id)
    plan_path = artifacts.artifacts / "plan.json"
    require(plan_path.exists(), f"run {run_id!r} has no plan artifact")
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
    context = RunContext(
        plan.question,
        run_id,
        effort.name,
        plan.mode,
        plan.audience,
        plan.seed or 0,
        artifacts.artifacts,
    )
    artifacts.append_journal("run_resume", {"completed_nodes": sorted(completed_nodes)})
    result = LocalConductor(plan, artifacts, context).run(completed_nodes).report
    artifacts.write_markdown("report.resumed.md", result.report_markdown)
    artifacts.write_ledger("minimal", plan.budget, 0.0)
    artifacts.append_journal("run_complete", {"out": f"runs/{run_id}/artifacts/report.resumed.md"})
    artifacts.write_manifest()
    console.print(f"resumed run {run_id}: complete")
