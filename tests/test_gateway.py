from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from athenaeum.gateway import BudgetLedger, ModelGateway
from athenaeum.gateway.models import BudgetExceeded, CompletionRequest, ProviderConfig, ResolvedModel
from athenaeum.gateway.transport import FakeTransport
from athenaeum.schemas import ReportOutput


def test_gateway_resolves_builtin_capability() -> None:
    gateway = ModelGateway.from_config()

    resolved = gateway.resolve("reasoner")

    assert resolved.provider == "stub"
    assert resolved.model == "reasoner"


def test_gateway_uses_zero_config_openai_env_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = tmp_path / "empty.toml"
    config.write_text("", encoding="utf-8")

    gateway = ModelGateway.from_config(config)
    resolved = gateway.resolve("reasoner")

    assert resolved.provider == "openai"
    assert gateway.providers["openai"].wire_api == "responses"
    assert gateway.route_targets("cheap-judge") == ["openai/gpt-5.5-mini"]


def test_gateway_uses_all_zero_config_env_providers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "secret")
    config = tmp_path / "empty.toml"
    config.write_text("", encoding="utf-8")

    gateway = ModelGateway.from_config(config)

    assert {"openai", "anthropic", "google"}.issubset(gateway.providers)
    assert gateway.route_targets("reasoner") == [
        "openai/gpt-5.5",
        "anthropic/claude-fable-5",
        "google/gemini-3-pro",
    ]
    assert gateway.route_targets("cheap-judge") == [
        "openai/gpt-5.5-mini",
        "anthropic/claude-haiku-4-5",
        "google/gemini-3-flash",
    ]


def test_gateway_configured_providers_disable_env_defaults(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    config = tmp_path / "configured.toml"
    config.write_text(
        """
[providers.local]
kind = "stub"
models = ["reasoner"]
""".strip(),
        encoding="utf-8",
    )

    gateway = ModelGateway.from_config(config)

    assert "openai" not in gateway.providers
    assert gateway.resolve("reasoner").provider == "stub"


def test_budget_ledger_rejects_projected_overrun(tmp_path: Path) -> None:
    ledger = BudgetLedger.open(tmp_path / "ledger.json", budget_usd=0.01)
    token = ledger.mint("node", 1.0)

    with pytest.raises(BudgetExceeded):
        ledger.reserve(token, 1.0)


def test_budget_ledger_writes_node_and_model_totals(tmp_path: Path) -> None:
    ledger = BudgetLedger.open(tmp_path / "ledger.json", budget_usd=1.0)
    token = ledger.mint("draft", 1.0)

    ledger.settle(token, ResolvedModel(capability="reasoner", provider="openai", model="gpt-test"), 10, 5, 0.123)

    data = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert data["by_node"]["draft"] == {"tokens_in": 10, "tokens_out": 5, "usd": 0.123}
    assert data["by_model"]["openai/gpt-test"] == {"tokens_in": 10, "tokens_out": 5, "usd": 0.123}


def test_gateway_complete_json_returns_report_output(tmp_path: Path) -> None:
    ledger = BudgetLedger.open(tmp_path / "ledger.json", budget_usd=1.0)
    gateway = ModelGateway.from_config(ledger=ledger)
    token = ledger.mint("draft", 1.0)

    result = asyncio.run(
        gateway.complete_json(
            CompletionRequest(messages=[{"role": "user", "content": "Should we ship?"}], capability="reasoner"),
            ReportOutput,
            token=token,
        )
    )

    assert result.kind == "report"
    assert ledger.path.exists()


def test_probe_distinguishes_configured_from_available_provider(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_OPENAI_KEY", raising=False)
    gateway = ModelGateway(
        providers={
            "openai": ProviderConfig(name="openai", kind="openai", key_env="MISSING_OPENAI_KEY", models=["gpt-test"]),
        }
    )

    health = gateway.probe()[0]

    assert health.name == "openai"
    assert health.configured is True
    assert health.available is False
    assert "MISSING_OPENAI_KEY" in (health.detail or "")


def test_gateway_projection_uses_full_requested_max_tokens() -> None:
    gateway = ModelGateway(
        routes={"reasoner": ["priced/gpt-test"]},
        providers={
            "priced": ProviderConfig(
                name="priced",
                kind="openai-compatible",
                models=["gpt-test"],
                prices={"gpt-test": {"input": 1.0, "output": 2.0}},
            ),
        },
    )
    resolved = gateway.resolve("reasoner")
    req = CompletionRequest(
        messages=[{"role": "user", "content": "one two three four"}],
        capability="reasoner",
        max_tokens=1000,
    )

    projected = gateway.projected_cost(req, resolved)

    assert projected == 2.004


def test_complete_json_primes_first_call_with_schema_instruction(monkeypatch) -> None:
    monkeypatch.setenv("TEST_KEY", "secret")
    response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "title": "Report",
                            "question": "q",
                            "summary": "s",
                            "report_markdown": "# Report",
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5},
    }
    transport = FakeTransport(response)
    gateway = ModelGateway(
        routes={"reasoner": ["openai/gpt-test"]},
        providers={"openai": ProviderConfig(name="openai", kind="openai", key_env="TEST_KEY", base_url="https://example.test/v1")},
        transport=transport,
    )

    result = asyncio.run(
        gateway.complete_json(
            CompletionRequest(messages=[{"role": "user", "content": "write report"}], capability="reasoner"),
            ReportOutput,
        )
    )

    assert result.kind == "report"
    assert len(transport.requests) == 1
    first_message = transport.requests[0]["json"]["messages"][0]
    assert first_message["role"] == "system"
    assert "Return only valid JSON matching schema ReportOutput" in first_message["content"]
    assert "report_markdown" in first_message["content"]
