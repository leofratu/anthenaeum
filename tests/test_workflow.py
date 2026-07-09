from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from athenaeum.effort import get_effort
from athenaeum.workflow import (
    apply_gateway_estimates,
    compile_plan,
    estimate_node_cost,
    estimate_plan_cost,
    validate_mode,
    validate_workflow,
)


def test_compile_plan_builds_default_graph_and_shares() -> None:
    effort = get_effort("low")
    plan = compile_plan(
        "Should we ship?",
        effort,
        "minimal",
        1.0,
        mode="deliberate",
        audience="exec",
        seed=7,
        workflow="review",
        reasoning_effort="high",
        planner={"suggested_budget": 2.0},
    )

    assert plan.question == "Should we ship?"
    assert plan.mode == "deliberate"
    assert plan.audience == "exec"
    assert plan.seed == 7
    assert plan.workflow == "review"
    assert plan.reasoning_effort == "high"
    assert [node.name for node in plan.nodes] == [
        "research",
        "debate",
        "draft",
        "verify",
        "court",
        "revise",
    ]
    assert plan.edges[0] == ("research", "debate")
    assert plan.edges[-1] == ("revise", "emit")
    assert abs(sum(node.budget_share for node in plan.nodes) - 1.0) < 1e-9
    assert plan.estimated_cost == 2.0
    assert plan.nodes[0].inputs == ()
    assert plan.nodes[1].input_schemas == ("ResearchOutput",)
    assert plan.nodes[1].max_iterations == effort.rounds


def test_compile_plan_falls_back_to_effort_budget_without_planner() -> None:
    effort = get_effort("medium")
    plan = compile_plan("q", effort, "minimal", 99.0)

    assert plan.estimated_cost == effort.default_budget
    assert plan.to_dict()["effort"] == "medium"
    assert plan.to_dict()["estimated_cost"] == effort.default_budget


def test_compile_plan_ignores_invalid_suggested_budget() -> None:
    effort = get_effort("low")
    for suggested in (0, -1, True, "nope", None):
        plan = compile_plan("q", effort, "minimal", 1.0, planner={"suggested_budget": suggested})
        assert plan.estimated_cost == effort.default_budget


def test_validate_mode_and_workflow_accept_known_values(tmp_path: Path) -> None:
    assert validate_mode(" Decide ") == "decide"
    assert validate_workflow("AUTO") == "auto"
    template = tmp_path / "custom.yaml"
    template.write_text("nodes: []\n", encoding="utf-8")
    assert validate_workflow(str(template)) == str(template)


def test_validate_mode_and_workflow_reject_unknown(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown mode"):
        validate_mode("sprint")
    with pytest.raises(ValueError, match="unknown workflow"):
        validate_workflow("mystery")
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises(ValueError, match="not a file"):
        validate_workflow(str(directory))


def test_estimate_node_cost_falls_back_when_gateway_unavailable() -> None:
    effort = get_effort("low")
    plan = compile_plan("q", effort, "minimal", 1.0)
    node = plan.nodes[0]
    broken = SimpleNamespace(
        route_targets=lambda capability: (_ for _ in ()).throw(RuntimeError("boom")),
        route_availability=lambda capability: [],
        resolve=lambda capability, target: None,
    )

    assert estimate_node_cost(node, broken) == node.estimated_cost
    assert estimate_plan_cost(plan, broken) == plan.estimated_cost


def test_estimate_node_cost_falls_back_when_resolve_fails() -> None:
    effort = get_effort("low")
    node = compile_plan("q", effort, "minimal", 1.0).nodes[0]
    health = SimpleNamespace(available=True)
    gateway = SimpleNamespace(
        route_targets=lambda capability: ["stub/model"],
        route_availability=lambda capability: [health],
        resolve=lambda capability, target: (_ for _ in ()).throw(KeyError(target)),
    )

    assert estimate_node_cost(node, gateway) == node.estimated_cost


def test_estimate_node_cost_uses_route_prices_when_available() -> None:
    effort = get_effort("low")
    node = compile_plan("q", effort, "minimal", 1.0).nodes[0]
    health = SimpleNamespace(available=True)
    resolved = SimpleNamespace(price_input_per_1k=1.0, price_output_per_1k=2.0)
    gateway = SimpleNamespace(
        route_targets=lambda capability: ["stub/model"],
        route_availability=lambda capability: [health],
        resolve=lambda capability, target: resolved,
    )

    priced = estimate_node_cost(node, gateway)
    tokens_in = max(int(node.estimated_tokens * 0.75), 0)
    tokens_out = max(node.estimated_tokens - tokens_in, 0)
    expected = round(tokens_in / 1000 * 1.0 + tokens_out / 1000 * 2.0, 4)
    assert priced == expected
    assert priced != node.estimated_cost


def test_estimate_node_cost_falls_back_on_zero_projection() -> None:
    effort = get_effort("low")
    node = compile_plan("q", effort, "minimal", 1.0).nodes[0]
    health = SimpleNamespace(available=False)
    resolved = SimpleNamespace(price_input_per_1k=0.0, price_output_per_1k=0.0)
    gateway = SimpleNamespace(
        route_targets=lambda capability: ["stub/model"],
        route_availability=lambda capability: [health],
        resolve=lambda capability, target: resolved,
    )

    assert estimate_node_cost(node, gateway) == node.estimated_cost


def test_estimate_node_cost_falls_back_when_no_targets() -> None:
    effort = get_effort("low")
    node = compile_plan("q", effort, "minimal", 1.0).nodes[0]
    gateway = SimpleNamespace(
        route_targets=lambda capability: [],
        route_availability=lambda capability: [],
        resolve=lambda capability, target: None,
    )

    assert estimate_node_cost(node, gateway) == node.estimated_cost


def test_apply_gateway_estimates_replaces_node_costs() -> None:
    effort = get_effort("low")
    plan = compile_plan("q", effort, "minimal", 1.0)
    health = SimpleNamespace(available=True)
    resolved = SimpleNamespace(price_input_per_1k=0.5, price_output_per_1k=1.5)
    gateway = SimpleNamespace(
        route_targets=lambda capability: ["stub/model"],
        route_availability=lambda capability: [health],
        resolve=lambda capability, target: resolved,
    )

    priced = apply_gateway_estimates(plan, gateway)

    assert priced is not plan
    assert all(
        node.estimated_cost == estimate_node_cost(original, gateway)
        for node, original in zip(priced.nodes, plan.nodes, strict=True)
    )
    assert priced.estimated_cost == estimate_plan_cost(plan, gateway)
