"""Runtime selection and execution helpers for the CLI."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from athenaeum.cli.errors import require
from athenaeum.gateway import ModelGateway
from athenaeum.runtime import AgentTask, RuntimeRegistry, Workspace
from athenaeum.runtime.api import ApiRuntime
from athenaeum.runtime.models import (
    AgentEvent,
    CostDelta,
    RuntimeExecutionError,
    RuntimeUnavailable,
)


def runtime_with_fallback(
    registry: RuntimeRegistry,
    requested_runtime: Any,
    requested_health: Any,
    gateway: ModelGateway,
) -> Any:
    if requested_health.available or requested_runtime.name == "minimal":
        return requested_runtime
    runtime = ApiRuntime(gateway)
    if runtime.health().available:
        return runtime
    return registry.get("minimal")


async def run_selected_runtime(
    runtime: Any,
    task: AgentTask,
    workspace: Workspace | None = None,
    on_event: Callable[[AgentEvent], None] | None = None,
) -> Any:
    health = runtime.health()
    if not health.available:
        raise RuntimeUnavailable(health.detail or f"{runtime.name} is unavailable")
    if workspace is not None:
        return await run_in_workspace(runtime, task, workspace, on_event)
    with tempfile.TemporaryDirectory(prefix="athenaeum-") as temp:
        return await run_in_workspace(runtime, task, Workspace(Path(temp)), on_event)


async def run_in_workspace(
    runtime: Any,
    task: AgentTask,
    workspace: Workspace,
    on_event: Callable[[AgentEvent], None] | None = None,
) -> Any:
    final = None
    accumulated = CostDelta()
    async for event in runtime.spawn(task, workspace):
        if on_event is not None:
            on_event(event)
        if event.kind == "cost_delta" and event.cost is not None:
            accumulated = CostDelta(
                tokens_in=accumulated.tokens_in + event.cost.tokens_in,
                tokens_out=accumulated.tokens_out + event.cost.tokens_out,
                usd=round(accumulated.usd + event.cost.usd, 6),
            )
            if task.budget_usd > 0 and accumulated.usd > task.budget_usd:
                raise RuntimeExecutionError(
                    f"{runtime.name} exceeded task budget ${task.budget_usd:.2f} "
                    f"with reported cost ${accumulated.usd:.2f}"
                )
        if event.kind == "final":
            final = event.result
    if final is None:
        raise RuntimeExecutionError(f"{runtime.name} did not emit a final event")
    if accumulated.usd > 0 and final.cost.usd <= 0:
        final.cost = accumulated
    return final


def select_requested_runtime(runtime_name: str, registry: RuntimeRegistry, gateway: ModelGateway) -> Any:
    name = runtime_name.lower().strip()
    require(bool(name), "runtime name must not be empty")
    if name == "api":
        return ApiRuntime(gateway)
    if name != "auto":
        return registry.get(runtime_name)
    api_runtime = ApiRuntime(gateway)
    if api_runtime.health().available:
        return api_runtime
    return registry.get("minimal")
