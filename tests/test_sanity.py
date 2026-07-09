from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from athenaeum.cli import app
from athenaeum.effort import get_effort
from athenaeum.gateway import ModelGateway
from athenaeum.gateway.models import ProviderConfig
from athenaeum.sanity import SanityChecker
from athenaeum.workflow import ExecutionPlan, PlanInput, PlanNode, apply_gateway_estimates, compile_plan

MISSING_KEY_ENV = "THINKTANK_TEST_MISSING_PROVIDER_KEY"


def test_sanity_errors_when_capability_routes_only_to_missing_key(monkeypatch) -> None:
    monkeypatch.delenv(MISSING_KEY_ENV, raising=False)
    gateway = _gateway_for_route(["missing/reasoner"])

    report = SanityChecker(gateway).check(_plan_for_capability("reasoner"))

    assert not report.ok
    assert any(
        finding.rule == "S2"
        and finding.severity == "error"
        and "reasoner" in finding.message
        and MISSING_KEY_ENV in finding.message
        for finding in report.errors
    )


def test_sanity_passes_capability_check_when_route_falls_back_to_available_provider(monkeypatch) -> None:
    monkeypatch.delenv(MISSING_KEY_ENV, raising=False)
    gateway = _gateway_for_route(["missing/reasoner", "stub/reasoner"])

    report = SanityChecker(gateway).check(_plan_for_capability("reasoner"))

    assert report.ok
    assert [finding for finding in report.findings if finding.rule == "S2"] == []


def test_sanity_rejects_stub_only_routes_for_api_runtime() -> None:
    gateway = ModelGateway(
        routes={"reasoner": ["stub/reasoner"]},
        providers={"stub": ProviderConfig(name="stub", kind="stub", models=["reasoner"])},
    )
    plan = _plan_for_capability("reasoner")
    plan = ExecutionPlan(
        question=plan.question,
        effort=plan.effort,
        runtime="api",
        budget=plan.budget,
        nodes=plan.nodes,
        edges=plan.edges,
    )

    report = SanityChecker(gateway).check(plan)

    assert not report.ok
    assert any(finding.rule == "S2" for finding in report.errors)


def test_sanity_high_tier_effort_ignores_stub_for_provider_diversity(monkeypatch) -> None:
    key_env = "THINKTANK_TEST_PRESENT_PROVIDER_KEY"
    monkeypatch.setenv(key_env, "secret")
    gateway = ModelGateway(
        routes={"reasoner": ["openai/reasoner"]},
        providers={
            "stub": ProviderConfig(name="stub", kind="stub", models=["reasoner"]),
            "openai": ProviderConfig(name="openai", kind="openai-compatible", key_env=key_env, models=["reasoner"]),
        },
    )
    base = _plan_for_capability("reasoner")
    plan = ExecutionPlan(
        question=base.question,
        effort=get_effort("vhigh"),
        runtime=base.runtime,
        budget=base.budget,
        nodes=base.nodes,
        edges=base.edges,
    )

    report = SanityChecker(gateway).check(plan)

    assert any(
        finding.rule == "S9"
        and finding.severity == "error"
        and "available non-stub providers" in finding.message
        for finding in report.errors
    )


def test_sanity_high_tier_effort_accepts_two_available_non_stub_providers() -> None:
    gateway = ModelGateway(
        routes={"reasoner": ["a/reasoner"]},
        providers={
            "a": ProviderConfig(name="a", kind="openai-compatible", models=["reasoner"]),
            "b": ProviderConfig(name="b", kind="anthropic", models=["judge"]),
            "stub": ProviderConfig(name="stub", kind="stub", models=["reasoner"]),
        },
    )
    base = _plan_for_capability("reasoner")
    plan = ExecutionPlan(
        question=base.question,
        effort=get_effort("vhigh"),
        runtime=base.runtime,
        budget=base.budget,
        nodes=base.nodes,
        edges=base.edges,
    )

    report = SanityChecker(gateway).check(plan)

    assert not any(finding.rule == "S9" for finding in report.errors)


def test_sanity_rejects_same_model_for_generator_and_judge() -> None:
    gateway = ModelGateway(
        routes={
            "reasoner": ["stub/reasoner"],
            "fast": ["stub/fast"],
            "long-context": ["stub/gpt-same"],
            "cheap-judge": ["stub/gpt-same"],
        },
        providers={"stub": ProviderConfig(name="stub", kind="stub", models=["reasoner", "fast", "gpt-same"])},
    )
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 1.0)

    report = SanityChecker(gateway).check(plan)

    assert not report.ok
    assert any(finding.rule == "S6" for finding in report.errors)


def test_sanity_allows_explicit_self_judge_override() -> None:
    gateway = ModelGateway(
        routes={
            "reasoner": ["stub/reasoner"],
            "fast": ["stub/fast"],
            "long-context": ["stub/gpt-same"],
            "cheap-judge": ["stub/gpt-same"],
        },
        providers={"stub": ProviderConfig(name="stub", kind="stub", models=["reasoner", "fast", "gpt-same"])},
    )
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 1.0, planner={"allow_self_judge": True})

    report = SanityChecker(gateway).check(plan)

    assert report.ok
    assert not any(finding.rule == "S6" for finding in report.errors)


def test_sanity_default_workflow_has_schema_assignable_edges() -> None:
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 1.0)

    report = SanityChecker().check(plan)

    assert not any(finding.rule == "S4" for finding in report.errors)


def test_sanity_budget_uses_provider_prices_not_budget_slices() -> None:
    gateway = _priced_gateway(input_price=4.0, output_price=8.0)
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 1.0)

    assert plan.estimated_cost < plan.budget

    report = SanityChecker(gateway).check(plan)

    assert not report.ok
    assert any(finding.rule == "S5" and "exceeds budget" in finding.message for finding in report.errors)


def test_apply_gateway_estimates_updates_visible_plan_costs() -> None:
    gateway = _priced_gateway(input_price=1.0, output_price=2.0)
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 0.01)

    priced = apply_gateway_estimates(plan, gateway)

    assert priced.estimated_cost > plan.estimated_cost
    assert all(node.estimated_cost > 0 for node in priced.nodes)


def test_compile_plan_estimated_cost_is_independent_of_user_budget() -> None:
    planner = {"suggested_budget": 7.5}

    tiny_budget = compile_plan("Should we ship?", get_effort("low"), "minimal", 0.01, planner=planner)
    large_budget = compile_plan("Should we ship?", get_effort("low"), "minimal", 100.0, planner=planner)

    assert tiny_budget.estimated_cost == 7.5
    assert large_budget.estimated_cost == tiny_budget.estimated_cost


def test_sanity_budget_rejects_below_planner_suggested_budget() -> None:
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 0.01, planner={"suggested_budget": 1.25})

    report = SanityChecker().check(plan)

    assert not report.ok
    assert any(finding.rule == "S5" and "exceeds budget" in finding.message for finding in report.errors)


def test_sanity_budget_allows_equal_planner_suggested_budget() -> None:
    plan = compile_plan("Should we ship?", get_effort("low"), "minimal", 1.25, planner={"suggested_budget": 1.25})

    report = SanityChecker().check(plan)

    assert report.ok
    assert not any(finding.rule == "S5" for finding in report.errors)


def test_sanity_budget_rejects_zero_and_negative_budget() -> None:
    for budget in (0.0, -1.0):
        plan = compile_plan("Should we ship?", get_effort("low"), "minimal", budget)

        report = SanityChecker().check(plan)

        assert not report.ok
        assert any(finding.rule == "S5" and "budget must be positive" in finding.message for finding in report.errors)


def test_sanity_rejects_schema_incompatible_edge() -> None:
    source = PlanNode(
        name="source",
        kind="writer",
        runtime="minimal",
        capability="reasoner",
        output_schema="ReportOutput",
        budget_share=0.5,
        estimated_tokens=100,
        estimated_cost=0.01,
        detail="source",
    )
    target = PlanNode(
        name="target",
        kind="writer",
        runtime="minimal",
        capability="reasoner",
        output_schema="ReviewOutput",
        budget_share=0.5,
        estimated_tokens=100,
        estimated_cost=0.01,
        detail="target",
        input_schemas=("ResearchOutput",),
    )
    plan = ExecutionPlan(
        question="Should we ship?",
        effort=get_effort("low"),
        runtime="minimal",
        budget=1.0,
        nodes=(source, target),
        edges=(("source", "target"), ("target", "emit")),
    )

    report = SanityChecker().check(plan)

    assert not report.ok
    assert any(finding.rule == "S4" and "ReportOutput" in finding.message for finding in report.errors)


def test_sanity_rejects_missing_required_predecessor_input() -> None:
    target = PlanNode(
        name="target",
        kind="writer",
        runtime="minimal",
        capability="reasoner",
        output_schema="ReportOutput",
        budget_share=1.0,
        estimated_tokens=100,
        estimated_cost=0.01,
        detail="target",
        inputs=(PlanInput("research", "ResearchOutput"), PlanInput("debate", "DebateOutput")),
    )
    plan = ExecutionPlan(
        question="Should we ship?",
        effort=get_effort("low"),
        runtime="minimal",
        budget=1.0,
        nodes=(target,),
        edges=(("target", "emit"),),
    )

    report = SanityChecker().check(plan)

    assert not report.ok
    assert any(finding.rule == "S4" and "research" in finding.message for finding in report.errors)
    assert any(finding.rule == "S4" and "debate" in finding.message for finding in report.errors)


def test_sanity_rejects_unknown_schema_name() -> None:
    node = PlanNode(
        name="source",
        kind="writer",
        runtime="minimal",
        capability="reasoner",
        output_schema="BogusOutput",
        budget_share=1.0,
        estimated_tokens=100,
        estimated_cost=0.01,
        detail="source",
    )
    plan = ExecutionPlan(
        question="Should we ship?",
        effort=get_effort("low"),
        runtime="minimal",
        budget=1.0,
        nodes=(node,),
        edges=(("source", "emit"),),
    )

    report = SanityChecker().check(plan)

    assert not report.ok
    assert any(finding.rule == "S4" and "BogusOutput" in finding.message for finding in report.errors)


def test_sanity_s5_rejects_provider_priced_plan_over_tiny_budget() -> None:
    plan = _single_node_budget_plan(
        capability="reasoner",
        budget=0.01,
        estimated_tokens=50_000,
        estimated_cost=0.001,
    )
    gateway = _gateway_with_prices(
        "reasoner",
        "priced/reasoner",
        prices={"reasoner": {"input": 2.0, "output": 2.0}},
    )

    assert plan.estimated_cost < plan.budget

    report = SanityChecker(gateway).check(plan)

    assert not report.ok
    assert any(finding.rule == "S5" and finding.severity == "error" for finding in report.errors)


def test_sanity_s5_allows_zero_priced_routes_with_tiny_budget() -> None:
    plan = _single_node_budget_plan(
        capability="reasoner",
        budget=0.01,
        estimated_tokens=50_000,
        estimated_cost=0.001,
    )
    gateway = _gateway_with_prices(
        "reasoner",
        "stub/reasoner",
        prices={"*": {"input": 0.0, "output": 0.0}},
        kind="stub",
    )

    report = SanityChecker(gateway).check(plan)

    assert report.ok
    assert not any(finding.rule == "S5" for finding in report.errors)


def test_sanity_s5_allows_provider_priced_plan_with_sufficient_budget() -> None:
    plan = _single_node_budget_plan(
        capability="reasoner",
        budget=500.0,
        estimated_tokens=50_000,
        estimated_cost=0.001,
    )
    gateway = _gateway_with_prices(
        "reasoner",
        "priced/reasoner",
        prices={"reasoner": {"input": 2.0, "output": 2.0}},
    )

    report = SanityChecker(gateway).check(plan)

    assert report.ok
    assert not any(finding.rule == "S5" for finding in report.errors)


def test_sanity_s5_warns_for_unpriced_non_stub_routes() -> None:
    plan = _single_node_budget_plan(
        capability="reasoner",
        budget=1.0,
        estimated_tokens=50_000,
        estimated_cost=0.001,
    )
    gateway = _gateway_with_prices("reasoner", "priced/reasoner", prices={})

    report = SanityChecker(gateway).check(plan)

    assert report.ok
    assert any(finding.rule == "S5" and finding.severity == "warning" and "no configured prices" in finding.message for finding in report.warnings)


def test_json_dry_run_estimated_costs_use_provider_prices_when_configured() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("thinktank.toml").write_text(
            """
[routes]
reasoner = ["priced/reasoner"]
fast = ["priced/fast"]
long-context = ["priced/long"]
cheap-judge = ["priced/judge"]

[providers.priced]
kind = "openai-compatible"
models = ["reasoner", "fast", "long", "judge"]

[providers.priced.prices."*"]
input = 0.01
output = 0.02
""".strip(),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "--config",
                "thinktank.toml",
                "--json",
                "--dry-run",
                "--effort",
                "high",
                "--budget",
                "100",
                "Should we ship?",
            ],
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        nodes = payload["plan"]["nodes"]

        assert all(isinstance(node["estimated_cost"], float | int) for node in nodes)
        assert [node["estimated_cost"] for node in nodes] != [
            round(payload["plan"]["budget"] * node["budget_share"], 4) for node in nodes
        ]


def _gateway_for_route(targets: list[str]) -> ModelGateway:
    return ModelGateway(
        routes={"reasoner": targets},
        providers={
            "missing": ProviderConfig(
                name="missing",
                kind="openai-compatible",
                key_env=MISSING_KEY_ENV,
                models=["reasoner"],
            ),
            "stub": ProviderConfig(
                name="stub",
                kind="stub",
                models=["reasoner"],
            ),
        },
    )


def _priced_gateway(input_price: float, output_price: float) -> ModelGateway:
    provider = ProviderConfig(
        name="priced",
        kind="openai-compatible",
        models=["reasoner", "fast", "writer", "judge"],
        prices={"*": {"input": input_price, "output": output_price}},
    )
    return ModelGateway(
        routes={
            "reasoner": ["priced/reasoner"],
            "fast": ["priced/fast"],
            "long-context": ["priced/writer"],
            "cheap-judge": ["priced/judge"],
        },
        providers={"priced": provider},
    )


def _plan_for_capability(capability: str) -> ExecutionPlan:
    node = PlanNode(
        name="draft",
        kind="writer",
        runtime="minimal",
        capability=capability,
        output_schema="ReportOutput",
        budget_share=1.0,
        estimated_tokens=100,
        estimated_cost=0.01,
        detail="focused test node",
    )
    return ExecutionPlan(
        question="Should we ship?",
        effort=get_effort("low"),
        runtime="minimal",
        budget=1.0,
        nodes=(node,),
        edges=(("draft", "emit"),),
    )


def _single_node_budget_plan(
    capability: str,
    budget: float,
    estimated_tokens: int,
    estimated_cost: float,
) -> ExecutionPlan:
    node = PlanNode(
        name="priced",
        kind="writer",
        runtime="minimal",
        capability=capability,
        output_schema="ReportOutput",
        budget_share=1.0,
        estimated_tokens=estimated_tokens,
        estimated_cost=estimated_cost,
        detail="provider priced budget test node",
    )
    return ExecutionPlan(
        question="Should we ship?",
        effort=get_effort("low"),
        runtime="minimal",
        budget=budget,
        nodes=(node,),
        edges=(("priced", "emit"),),
    )


def _gateway_with_prices(
    capability: str,
    target: str,
    prices: dict[str, dict[str, float]],
    kind: str = "openai-compatible",
) -> ModelGateway:
    provider_name, model_name = target.split("/", 1)
    return ModelGateway(
        routes={capability: [target]},
        providers={
            provider_name: ProviderConfig(
                name=provider_name,
                kind=kind,
                models=[model_name],
                prices=prices,
            ),
        },
    )
