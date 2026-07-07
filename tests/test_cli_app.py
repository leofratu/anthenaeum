from __future__ import annotations

import json
from pathlib import Path

import athenaeum.cli as cli_module
from typer.testing import CliRunner

from athenaeum.cli import app
from athenaeum.config import load_config


runner = CliRunner()


def test_doctor_lists_cli_runtimes() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "opencode" in result.output
    assert "codex" in result.output
    assert "agy" in result.output
    assert "claude" in result.output


def test_dry_run_accepts_claude_runtime() -> None:
    result = runner.invoke(app, ["--runtime", "claude", "--dry-run", "Should we ship?"])

    assert result.exit_code == 0
    assert "Dry Run" in result.output
    assert "claude" in result.output


def test_help_lists_expanded_command_surface() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ["ask", "evolve", "review", "science", "watch", "sessions", "personas", "thinkers", "workflows", "schemas", "config", "setup"]:
        assert command in result.output


def test_schema_show_prints_report_schema() -> None:
    result = runner.invoke(app, ["schemas", "show", "report"])

    assert result.exit_code == 0
    assert "report_markdown" in result.output
    assert "claims" in result.output


def test_runtimes_run_uses_minimal_runtime() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["runtimes", "run", "minimal", "Summarize", "--out", "runtime.md"])

        assert result.exit_code == 0, result.output
        assert "Report ready" in result.output


def test_reasoning_and_provider_commands() -> None:
    reasoning = runner.invoke(app, ["reasoning", "high"])
    providers = runner.invoke(app, ["providers", "list"])

    assert reasoning.exit_code == 0
    assert "openai=high" in reasoning.output
    assert providers.exit_code == 0
    assert "Routes" in providers.output


def test_effort_command_renders_slider_preview() -> None:
    result = runner.invoke(app, ["effort", "ultra"])

    assert result.exit_code == 0, result.output
    assert "Adversarial exhaustive" in result.output
    assert "animation" in result.output
    assert "red-team" in result.output


def test_effort_select_falls_back_when_not_tty() -> None:
    result = runner.invoke(app, ["effort", "--select"])

    assert result.exit_code == 0, result.output
    assert "selected effort=high" in result.output


def test_effort_list_preserves_table_view() -> None:
    result = runner.invoke(app, ["effort", "--list"])

    assert result.exit_code == 0, result.output
    assert "low" in result.output
    assert "ultra" in result.output


def test_interactive_effort_selector_changes_dry_run_effort(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "select_effort_slider", lambda selected: "medium")

    result = runner.invoke(app, ["--minimal", "--dry-run", "-i", "--effort", "high", "Should we ship?"])

    assert result.exit_code == 0, result.output
    assert "effort medium" in result.output


def test_providers_init_writes_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["providers", "init", "--out", "thinktank.toml"])

        assert result.exit_code == 0, result.output
        text = open("thinktank.toml", encoding="utf-8").read()
        assert "model_provider" in text
        assert "wire_api = \"responses\"" in text
        assert "OPENAI_API_KEY" in text


def test_config_init_writes_primary_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["config", "init", "--out", "thinktank.toml"])

        assert result.exit_code == 0, result.output
        text = open("thinktank.toml", encoding="utf-8").read()
        assert "model = \"gpt-5.5\"" in text
        assert "[features]" in text
        assert "goals = true" in text


def test_config_example_prints_valid_toml_headers() -> None:
    result = runner.invoke(app, ["config", "example"])

    assert result.exit_code == 0, result.output
    assert "[model_providers.OpenAI]" in result.output
    assert "[features]" in result.output


def test_setup_noninteractive_writes_config() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(
            app,
            [
                "setup",
                "--provider",
                "OpenAI",
                "--model",
                "gpt-5.5",
                "--review-model",
                "gpt-5.5",
                "--model-reasoning",
                "auto",
                "--base-url",
                "https://openapi.junliai.org",
                "--network",
                "enabled",
                "--disable-storage",
                "--goals",
                "--out",
                "thinktank.toml",
            ],
        )

        assert result.exit_code == 0, result.output
        config = load_config(Path("thinktank.toml"))
        assert config["model_provider"] == "OpenAI"
        assert config["model"] == "gpt-5.5"
        assert config["model_reasoning_effort"] == "auto"
        assert config["disable_response_storage"] is True
        assert config["features"]["goals"] is True


def test_setup_refuses_existing_file_without_force() -> None:
    with runner.isolated_filesystem():
        Path("thinktank.toml").write_text("old = true\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "setup",
                "--provider",
                "OpenAI",
                "--model",
                "gpt-5.5",
                "--review-model",
                "gpt-5.5",
                "--model-reasoning",
                "high",
                "--base-url",
                "https://openapi.junliai.org",
                "--network",
                "enabled",
                "--disable-storage",
                "--goals",
                "--out",
                "thinktank.toml",
            ],
        )

        assert result.exit_code != 0
        assert "already exists" in result.output


def test_setup_force_overwrites_existing_file() -> None:
    with runner.isolated_filesystem():
        Path("thinktank.toml").write_text("old = true\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "setup",
                "--provider",
                "OpenAI",
                "--model",
                "gpt-5.5",
                "--review-model",
                "gpt-5.5",
                "--model-reasoning",
                "high",
                "--base-url",
                "https://openapi.junliai.org",
                "--network",
                "enabled",
                "--disable-storage",
                "--goals",
                "--out",
                "thinktank.toml",
                "--force",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "old = true" not in Path("thinktank.toml").read_text(encoding="utf-8")
        assert load_config(Path("thinktank.toml"))["model_reasoning_effort"] == "high"


def test_setup_same_model_review_config_can_dry_run(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with runner.isolated_filesystem():
        setup_result = runner.invoke(
            app,
            [
                "setup",
                "--provider",
                "OpenAI",
                "--model",
                "gpt-5.5",
                "--review-model",
                "gpt-5.5",
                "--model-reasoning",
                "xhigh",
                "--base-url",
                "https://openapi.junliai.org",
                "--network",
                "enabled",
                "--disable-storage",
                "--goals",
                "--out",
                "thinktank.toml",
            ],
        )
        assert setup_result.exit_code == 0, setup_result.output

        dry_run = runner.invoke(app, ["--config", "thinktank.toml", "--json", "--dry-run", "--effort", "high", "Should we ship?"])

        assert dry_run.exit_code == 0, dry_run.output
        payload = json.loads(dry_run.output)
        assert payload["plan"]["planner"]["allow_self_judge"] is True
        assert not any(finding["rule"] == "S6" and finding["severity"] == "error" for finding in payload["sanity"])


def test_json_dry_run_includes_planner_metadata() -> None:
    with runner.isolated_filesystem():
        Path("thinktank.toml").write_text(
            """
[routes]
reasoner = ["a/reasoner"]
fast = ["b/fast"]
long-context = ["a/writer"]
cheap-judge = ["b/judge"]

[providers.a]
kind = "openai-compatible"
models = ["reasoner", "writer"]

[providers.b]
kind = "anthropic"
models = ["fast", "judge"]
""".strip(),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["--config", "thinktank.toml", "--minimal", "--json", "--dry-run", "--effort", "iq-ultra", "Should we compare privacy and security risk?"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["plan"]["effort"] == "ultra"
        assert payload["plan"]["planner"]["review_depth"] == "adversarial"
        assert payload["plan"]["planner"]["expert_panel_size"] >= 12


def test_iq_option_maps_to_effort_alias() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["--minimal", "--json", "--dry-run", "--iq", "140", "Should we ship?"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["plan"]["effort"] == "high"


def test_json_dry_run_rejects_unknown_panel_preset() -> None:
    result = runner.invoke(app, ["--minimal", "--json", "--dry-run", "--panel", "not-a-panel", "Should we ship?"])

    assert result.exit_code != 0
    assert "unknown thinker lens" in result.output


def test_json_dry_run_accepts_iq_ultra_panel_preset() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["--minimal", "--json", "--dry-run", "--panel", "iq-ultra", "Should we ship?"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["plan"]["question"] == "Should we ship?"


