from __future__ import annotations

from athenaeum.interactive import InteractiveState, handle_interactive_line


def test_help_is_setup_first_and_moves_reasoning_to_advanced() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/help", state)

    assert result.action == "help"
    assert "/setup" in result.message
    assert "/iq [value|select]" in result.message
    assert "/save-config [path]" in result.message
    assert "/reasoning [level]" not in result.message

    advanced = handle_interactive_line("/help advanced", state)

    assert advanced.action == "help"
    assert "/reasoning [level]" in advanced.message


def test_plan_action_is_distinct_from_run_and_dry_run() -> None:
    state = InteractiveState()

    plan = handle_interactive_line("/plan Should we ship?", state)
    run = handle_interactive_line("/run Should we ship?", state)
    dry_run = handle_interactive_line("/dry-run Should we ship?", state)

    assert plan.action == "plan"
    assert plan.question == "Should we ship?"
    assert run.action == "run"
    assert dry_run.action == "dry_run"


def test_provider_and_model_commands_update_state() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/provider openai", state)
    assert result.action == "status"
    assert state.provider == "openai"

    result = handle_interactive_line("/model gpt-5", state)
    assert result.action == "status"
    assert state.model == "gpt-5"

    result = handle_interactive_line("/model anthropic/claude-sonnet-4-5", state)
    assert result.action == "status"
    assert state.provider == "anthropic"
    assert state.model == "claude-sonnet-4-5"

    result = handle_interactive_line("/model review openai/gpt-5-mini", state)
    assert result.action == "status"
    assert state.review_model == "openai/gpt-5-mini"


def test_settings_show_and_update_network_storage() -> None:
    state = InteractiveState(provider="openai", model="gpt-5", runtime="api")

    result = handle_interactive_line("/settings", state)
    assert result.action == "settings"
    assert "provider=openai" in result.message
    assert "model=gpt-5" in result.message
    assert "runtime=api" in result.message
    assert "network=auto" in result.message
    assert "storage=default" in result.message
    assert "goal=none" in result.message

    result = handle_interactive_line("/settings network off", state)
    assert result.action == "settings"
    assert state.network_access == "disabled"

    result = handle_interactive_line("/settings storage project", state)
    assert result.action == "settings"
    assert state.storage_preference == "project"

    result = handle_interactive_line("/network on", state)
    assert result.action == "settings"
    assert state.network_access == "enabled"

    result = handle_interactive_line("/storage no-response-storage", state)
    assert result.action == "settings"
    assert state.storage_preference == "no-response-storage"


def test_settings_accepts_key_value_aliases() -> None:
    state = InteractiveState(network_access="disabled", storage_preference="default")

    result = handle_interactive_line("/settings network_access=enable", state)
    assert result.action == "settings"
    assert state.network_access == "enabled"
    assert result.message == "network=enabled"

    result = handle_interactive_line("/settings network-access=default", state)
    assert result.action == "settings"
    assert state.network_access == "auto"
    assert result.message == "network=auto"

    result = handle_interactive_line("/settings storage-preference=session", state)
    assert result.action == "settings"
    assert state.storage_preference == "session"
    assert result.message == "storage=session"


def test_mode_command_validates_known_modes() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/mode decide", state)

    assert result.action == "status"
    assert state.mode == "decide"
    assert result.message == "mode=decide"

    result = handle_interactive_line("/mode handwave", state)

    assert result.action == "noop"
    assert "unknown mode" in result.message
    assert state.mode == "decide"


def test_iq_command_maps_to_effort_aliases() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/iq 140", state)

    assert result.action == "status"
    assert state.effort == "high"
    assert result.message == "iq=140 maps to effort=high"

    result = handle_interactive_line("/iq", state)

    assert result.action == "select_effort"

    result = handle_interactive_line("/iq select", state)

    assert result.action == "select_effort"

    result = handle_interactive_line("/effort slider", state)

    assert result.action == "select_effort"

    result = handle_interactive_line("/effort", state)

    assert result.action == "select_effort"


def test_setup_base_url_and_save_config_commands() -> None:
    state = InteractiveState(provider="OpenAI", model="gpt-5.5")

    result = handle_interactive_line("/setup", state)

    assert result.action == "settings"
    assert "provider=OpenAI" in result.message
    assert "iq=effort:high" in result.message
    assert "/save-config thinktank.toml" in result.message

    result = handle_interactive_line("/base-url https://example.test/v1", state)

    assert result.action == "status"
    assert state.base_url == "https://example.test/v1"

    result = handle_interactive_line("/review-model gpt-review", state)

    assert result.action == "status"
    assert state.review_model == "gpt-review"

    result = handle_interactive_line("/save-config custom.toml", state)

    assert result.action == "save_config"
    assert result.target == "custom.toml"

    result = handle_interactive_line("/config save nested/thinktank.toml", state)

    assert result.action == "save_config"
    assert result.target == "nested/thinktank.toml"


def test_goal_lifecycle_updates_visible_state() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/goal", state)
    assert result.action == "status"
    assert result.message == "goal=none"

    result = handle_interactive_line("/goal Ship the planner preview", state)
    assert result.action == "status"
    assert state.goal == "Ship the planner preview"
    assert state.current_goal == "Ship the planner preview"
    assert state.goal_status == "active"
    assert result.message == "goal=active:Ship the planner preview"

    result = handle_interactive_line("/goal complete", state)
    assert result.action == "status"
    assert state.goal == "Ship the planner preview"
    assert state.current_goal is None
    assert state.goal_status == "complete"
    assert result.message == "goal=complete:Ship the planner preview"


def test_resume_command_parses_target() -> None:
    state = InteractiveState()

    result = handle_interactive_line("/resume run-123", state)

    assert result.action == "resume"
    assert result.target == "run-123"
