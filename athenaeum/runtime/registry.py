from __future__ import annotations

from pathlib import Path
from typing import Iterable

from athenaeum.config import load_config

from .api import ApiRuntime
from .cli import CliRuntime, RuntimeDefinition, definition_from_command
from .minimal import MinimalRuntime


BUILTIN_DEFINITIONS: tuple[RuntimeDefinition, ...] = (
    RuntimeDefinition(
        name="opencode",
        binary="opencode",
        args=("run", "--json", "--cwd", "{workspace}", "{prompt_text}"),
        aliases=("open-code", "open_code"),
        fix="install OpenCode or set [runtimes.opencode].command in thinktank.toml",
    ),
    RuntimeDefinition(
        name="codex",
        binary="codex",
        args=("exec", "--json", "--skip-git-repo-check", "-C", "{workspace}", "{prompt_text}"),
        fix="install Codex CLI or set [runtimes.codex].command in thinktank.toml",
    ),
    RuntimeDefinition(
        name="agy",
        binary="agy",
        args=("run", "--json", "--workspace", "{workspace}", "{prompt_file}"),
        aliases=("agy-cli",),
        fix="install AGY CLI or set [runtimes.agy].command in thinktank.toml",
    ),
    RuntimeDefinition(
        name="claude",
        binary="claude",
        args=("-p", "{prompt_text}", "--output-format", "stream-json", "--max-turns", "{max_turns}"),
        aliases=("claude-code", "claude_cli"),
        fix="install Claude CLI or set [runtimes.claude].command in thinktank.toml",
    ),
    RuntimeDefinition(
        name="gemini",
        binary="gemini",
        args=("-p", "{prompt_text}", "--output-format", "json"),
        aliases=("gemini-cli",),
        fix="install Gemini CLI or set [runtimes.gemini].command in thinktank.toml",
    ),
)


class RuntimeRegistry:
    def __init__(self, definitions: Iterable[RuntimeDefinition] = BUILTIN_DEFINITIONS):
        self._definitions = {definition.name: definition for definition in definitions}
        self._aliases: dict[str, str] = {"stub": "minimal", "local": "minimal"}
        for definition in self._definitions.values():
            for alias in definition.aliases:
                self._aliases[alias.lower()] = definition.name

    @classmethod
    def from_config(cls, path: Path | None = None) -> "RuntimeRegistry":
        registry = cls()
        data = load_config(path)
        for name, value in data.get("runtimes", {}).items():
            if not isinstance(value, dict):
                raise ValueError(f"[runtimes.{name}] must be a table")
            registry.register(_definition_from_config(name, value))
        return registry

    def register(self, definition: RuntimeDefinition) -> None:
        old = self._definitions.get(definition.name)
        self._definitions[definition.name] = definition
        if old is not None:
            for alias in old.aliases:
                self._aliases[alias.lower()] = definition.name
        for alias in definition.aliases:
            self._aliases[alias.lower()] = definition.name

    def names(self) -> tuple[str, ...]:
        return tuple(sorted((*self._definitions, "api", "minimal")))

    def resolve_name(self, name: str) -> str:
        key = name.lower()
        if key == "minimal":
            return key
        if key == "api":
            return key
        if key in self._definitions:
            return key
        if key in self._aliases:
            return self._aliases[key]
        valid = ", ".join(self.names())
        raise KeyError(f"unknown runtime {name!r}; expected one of: {valid}")

    def get(self, name: str) -> CliRuntime:
        if self.resolve_name(name) == "minimal":
            return MinimalRuntime()
        if self.resolve_name(name) == "api":
            return ApiRuntime()
        return CliRuntime(self._definitions[self.resolve_name(name)])

    def all(self) -> tuple[CliRuntime, ...]:
        runtimes = []
        for name in self.names():
            runtimes.append(self.get(name))
        return tuple(runtimes)


def _definition_from_config(name: str, value: dict[str, object]) -> RuntimeDefinition:
    version_args = tuple(str(part) for part in value.get("version_args", ["--version"]))
    aliases = tuple(str(part) for part in value.get("aliases", []))
    fix = str(value["fix"]) if "fix" in value else None
    if "command" in value:
        definition = definition_from_command(name, str(value["command"]), version_args)
        return RuntimeDefinition(definition.name, definition.binary, definition.args, version_args, aliases, fix)
    binary = str(value.get("binary", name))
    args_value = value.get("args", [])
    if not isinstance(args_value, list):
        raise ValueError(f"[runtimes.{name}].args must be a list")
    args = tuple(str(part) for part in args_value)
    return RuntimeDefinition(name=name, binary=binary, args=args, version_args=version_args, aliases=aliases, fix=fix)
