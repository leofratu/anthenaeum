from __future__ import annotations

from athenaeum.effort import get_effort
from athenaeum.planner import PlannerDecision, PlannerModelRef, plan_run
from athenaeum.workflow import compile_plan


QUESTION = (
    "Should we migrate a regulated healthcare platform to a new multi-provider "
    "AI architecture, and how should we compare privacy, security, compliance, "
    "cost, latency, and operational risk tradeoffs?"
)


def test_required_efforts_and_vhigh_compatibility_are_supported() -> None:
    assert [get_effort(name).name for name in ["low", "medium", "high", "max", "ultra"]] == [
        "low",
        "medium",
        "high",
        "max",
        "ultra",
    ]
    assert get_effort("vhigh").name == "vhigh"


def test_planner_output_scales_with_effort() -> None:
    low = plan_run(QUESTION, "low", "main-model")
    medium = plan_run(QUESTION, "medium", "main-model")
    high = plan_run(QUESTION, "high", "main-model")
    max_plan = plan_run(QUESTION, "max", "main-model")

    assert isinstance(high, PlannerDecision)
    assert len(low.selected_loops) < len(medium.selected_loops) < len(high.selected_loops) < len(max_plan.selected_loops)
    assert low.expert_panel_size < medium.expert_panel_size < high.expert_panel_size < max_plan.expert_panel_size
    assert low.suggested_budget < medium.suggested_budget < high.suggested_budget < max_plan.suggested_budget
    assert low.review_depth == "light"
    assert max_plan.review_depth == "exhaustive"


def test_ultra_goes_beyond_max() -> None:
    max_plan = plan_run(QUESTION, "max", "main-model")
    ultra = plan_run(QUESTION, "ultra", "main-model")

    assert len(ultra.selected_loops) > len(max_plan.selected_loops)
    assert ultra.expert_panel_size > max_plan.expert_panel_size
    assert ultra.provider_runtime_diversity.providers > max_plan.provider_runtime_diversity.providers
    assert ultra.provider_runtime_diversity.runtimes > max_plan.provider_runtime_diversity.runtimes
    assert ultra.suggested_budget > max_plan.suggested_budget
    assert ultra.review_depth == "adversarial"


def test_model_reasoning_effort_does_not_change_planner_shape() -> None:
    model_low = {"model": "main-model", "provider": "openai", "runtime": "api", "model_reasoning_effort": "low"}
    model_high = {"model": "main-model", "provider": "openai", "runtime": "api", "model_reasoning_effort": "max"}
    low_reasoning = plan_run(QUESTION, "high", model_low, model_reasoning_effort="low")
    high_reasoning = plan_run(QUESTION, "high", model_high, model_reasoning_effort="max")

    assert low_reasoning.shape_dict() == high_reasoning.shape_dict()
    assert low_reasoning.planner_model == PlannerModelRef(name="main-model", provider="openai", runtime="api")
    assert high_reasoning.planner_model == low_reasoning.planner_model


def test_ultra_effort_compiles_existing_workflow() -> None:
    effort = get_effort("ultra")
    plan = compile_plan("Should we run ultra?", effort, "minimal", effort.default_budget)

    assert plan.effort.name == "ultra"
    assert plan.nodes[1].detail == "8 debaters x 7 rounds"
