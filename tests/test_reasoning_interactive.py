from __future__ import annotations

from athenaeum.interactive import InteractiveState, handle_interactive_line
from athenaeum.reasoning import apply_anthropic_reasoning, apply_google_reasoning, apply_openai_reasoning, get_reasoning_profile


def test_reasoning_profiles_map_provider_controls() -> None:
    assert get_reasoning_profile("vhigh").openai_effort == "high"

    openai_body = {}
    anthropic_body = {"max_tokens": 1024}
    google_body = {"generationConfig": {}}
    apply_openai_reasoning(openai_body, "high")
    apply_anthropic_reasoning(anthropic_body, "high")
    apply_google_reasoning(google_body, "high")

    assert openai_body["reasoning"] == {"effort": "high"}
    assert anthropic_body["thinking"]["budget_tokens"] == 8192
    assert anthropic_body["max_tokens"] > anthropic_body["thinking"]["budget_tokens"]
    assert google_body["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 4096


def test_interactive_slash_commands_update_state() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/reasoning max", state)
    assert result.action == "status"
    assert state.reasoning_effort == "max"

    result = handle_interactive_line("/runtime api", state)
    assert result.action == "status"
    assert state.runtime == "api"

    result = handle_interactive_line("Should we ship?", state)
    assert result.action == "run"
    assert result.question == "Should we ship?"


def test_interactive_dry_run_command() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/dry-run Should we ship?", state)

    assert result.action == "dry_run"
    assert result.question == "Should we ship?"
