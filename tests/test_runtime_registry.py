from __future__ import annotations

from pathlib import Path

from athenaeum.runtime import AgentTask, RuntimeRegistry, Workspace


def test_registry_includes_requested_cli_runtimes() -> None:
    registry = RuntimeRegistry()

    assert {"opencode", "codex", "agy", "claude"}.issubset(set(registry.names()))
    assert registry.resolve_name("open-code") == "opencode"
    assert registry.resolve_name("claude-code") == "claude"
    assert registry.resolve_name("agy-cli") == "agy"


def test_codex_command_renders_workspace_and_prompt() -> None:
    runtime = RuntimeRegistry().get("codex")
    task = AgentTask(prompt="do work", max_turns=3)
    workspace = Workspace(Path("/tmp/athenaeum-test"))

    command = runtime.build_command(task, workspace, workspace.root / "task.md", workspace.root / "result.json", "PROMPT")

    assert command[:5] == ["codex", "exec", "--json", "--skip-git-repo-check", "-C"]
    assert command[5] == "/tmp/athenaeum-test"
    assert command[-1] == "PROMPT"


def test_config_override_can_replace_builtin_runtime(tmp_path: Path) -> None:
    config = tmp_path / "thinktank.toml"
    config.write_text(
        """
[runtimes.agy]
command = "python3 fake_agy.py {result_file}"
version_args = ["--version"]
aliases = ["local-agy"]
""".strip(),
        encoding="utf-8",
    )

    registry = RuntimeRegistry.from_config(config)
    runtime = registry.get("local-agy")

    assert runtime.definition.binary == "python3"
    assert runtime.definition.args == ("fake_agy.py", "{result_file}")
