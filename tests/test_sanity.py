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

