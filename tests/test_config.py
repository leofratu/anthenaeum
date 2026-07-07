from __future__ import annotations

from pathlib import Path

from athenaeum.config import feature_enabled, generate_example_config, load_config, render_primary_config


def test_load_config_parses_new_primary_format(tmp_path: Path) -> None:
    config_path = tmp_path / "thinktank.toml"
    config_path.write_text(
        """
model_provider = "OpenAI"
model = "gpt-5"
review_model = "gpt-5-mini"
model_reasoning_effort = "high"
disable_response_storage = true
network_access = false
windows_wsl_setup_acknowledged = true

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
requires_openai_auth = true
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["model_provider"] == "OpenAI"
    assert config["model"] == "gpt-5"
    assert config["review_model"] == "gpt-5-mini"
    assert config["model_reasoning_effort"] == "high"
    assert config["disable_response_storage"] is True
    assert config["network_access"] is False
    assert config["windows_wsl_setup_acknowledged"] is True
    assert config["model_providers"]["openai"] == {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "wire_api": "responses",
        "requires_openai_auth": True,
    }

    assert config["providers"]["openai"] == {
        "kind": "openai-compatible",
        "structured_output": True,
        "base_url": "https://api.openai.com/v1",
        "wire_api": "responses",
        "disable_response_storage": True,
        "key_env": "OPENAI_API_KEY",
        "models": ["gpt-5", "gpt-5-mini"],
        "probe_model": "gpt-5",
    }
    assert config["routes"]["reasoner"] == ["openai/gpt-5"]
    assert config["routes"]["fast"] == ["openai/gpt-5"]
    assert config["routes"]["long-context"] == ["openai/gpt-5"]
    assert config["routes"]["cheap-judge"] == ["openai/gpt-5-mini"]


def test_load_config_parses_features(tmp_path: Path) -> None:
    config_path = tmp_path / "thinktank.toml"
    config_path.write_text(
        """
[features]
goals = true
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["features"] == {"goals": True}
    assert feature_enabled(config, "goals") is True
    assert feature_enabled(config, "missing") is False
    assert feature_enabled(config, "missing", default=True) is True


def test_model_provider_can_resolve_display_name_alias_to_provider_key(tmp_path: Path) -> None:
    config_path = tmp_path / "thinktank.toml"
    config_path.write_text(
        """
model_provider = "OpenAI"
model = "gpt-5"
review_model = "gpt-5-mini"

[model_providers.junlai]
name = "OpenAI"
base_url = "https://openapi.junliai.org"
wire_api = "responses"
requires_openai_auth = true
models = ["gpt-4.1"]
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["providers"]["junlai"]["key_env"] == "OPENAI_API_KEY"
    assert config["providers"]["junlai"]["models"] == ["gpt-4.1", "gpt-5", "gpt-5-mini"]
    assert config["providers"]["junlai"]["probe_model"] == "gpt-4.1"
    assert config["routes"]["reasoner"] == ["junlai/gpt-5"]
    assert config["routes"]["fast"] == ["junlai/gpt-5"]
    assert config["routes"]["long-context"] == ["junlai/gpt-5"]
    assert config["routes"]["cheap-judge"] == ["junlai/gpt-5-mini"]


def test_generate_example_config_uses_new_primary_format(tmp_path: Path) -> None:
    config_path = tmp_path / "thinktank.toml"
    config_path.write_text(generate_example_config(), encoding="utf-8")

    config = load_config(config_path)

    assert config["model_provider"] == "OpenAI"
    assert config["model"] == "gpt-5.5"
    assert config["model_reasoning_effort"] == "xhigh"
    assert config["disable_response_storage"] is True
    assert config["network_access"] == "enabled"
    assert config["model_providers"]["OpenAI"]["wire_api"] == "responses"
    assert config["model_providers"]["OpenAI"]["requires_openai_auth"] is True
    assert config["providers"]["OpenAI"]["kind"] == "openai-compatible"
    assert config["providers"]["OpenAI"]["base_url"] == "https://openapi.junliai.org"
    assert config["providers"]["OpenAI"]["wire_api"] == "responses"
    assert config["providers"]["OpenAI"]["disable_response_storage"] is True
    assert config["routes"]["reasoner"] == ["OpenAI/gpt-5.5"]
    assert feature_enabled(config, "goals") is True


def test_render_primary_config_round_trips_through_loader(tmp_path: Path) -> None:
    config_path = tmp_path / "thinktank.toml"
    config_path.write_text(
        render_primary_config(
            provider="OpenAI",
            model="gpt-5.5",
            review_model="gpt-5.5-review",
            reasoning="high",
            base_url="https://openapi.junliai.org",
            network="enabled",
            disable_storage=True,
            goals=True,
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config["model_provider"] == "OpenAI"
    assert config["model"] == "gpt-5.5"
    assert config["review_model"] == "gpt-5.5-review"
    assert config["model_reasoning_effort"] == "high"
    assert config["providers"]["OpenAI"]["base_url"] == "https://openapi.junliai.org"
    assert config["routes"]["cheap-judge"] == ["OpenAI/gpt-5.5-review"]


def test_empty_and_old_style_configs_remain_compatible(tmp_path: Path) -> None:
    empty_path = tmp_path / "empty.toml"
    empty_path.write_text("", encoding="utf-8")

    assert load_config(empty_path) == {}

    old_style_path = tmp_path / "old.toml"
    old_style_path.write_text(
        """
[routes]
fast = ["legacy/model-a"]
reasoner = ["legacy/model-b"]

[providers.legacy]
kind = "openai-compatible"
key_env = "LEGACY_API_KEY"
base_url = "https://legacy.example/v1"
models = ["model-a", "model-b"]
""".strip(),
        encoding="utf-8",
    )

    old_style = load_config(old_style_path)

    assert old_style["routes"] == {
        "fast": ["legacy/model-a"],
        "reasoner": ["legacy/model-b"],
    }
    assert old_style["providers"] == {
        "legacy": {
            "kind": "openai-compatible",
            "key_env": "LEGACY_API_KEY",
            "base_url": "https://legacy.example/v1",
            "models": ["model-a", "model-b"],
        }
    }
