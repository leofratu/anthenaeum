from __future__ import annotations

import asyncio
from contextlib import suppress
import json
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from .models import (
    AgentEvent,
    AgentResult,
    CostDelta,
    AgentTask,
    RuntimeExecutionError,
    RuntimeHealth,
    RuntimeUnavailable,
    SchemaValidationError,
    RuntimeMeta,
    Workspace,
    validate_json_schema_subset,
)


@dataclass(frozen=True)
class RuntimeDefinition:
    name: str
    binary: str
    args: tuple[str, ...]
    version_args: tuple[str, ...] = ("--version",)
    aliases: tuple[str, ...] = ()
    fix: str | None = None
    stream_mode: str = "auto"


class CliRuntime:
    def __init__(self, definition: RuntimeDefinition):
        self.definition = definition
        self.name = definition.name

    def health(self) -> RuntimeHealth:
        path = shutil.which(self.definition.binary)
        if path is None:
            return RuntimeHealth(
                name=self.name,
                binary=self.definition.binary,
                available=False,
                fix=self.definition.fix or f"install {self.definition.binary} or choose another --runtime",
            )
        version = None
        detail = None
        try:
            completed = subprocess.run(
                [path, *self.definition.version_args],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            version = _first_line(completed.stdout) or _first_line(completed.stderr)
            if completed.returncode != 0 and version is None:
                detail = f"version probe exited {completed.returncode}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            detail = str(exc)
        return RuntimeHealth(
            name=self.name,
            binary=self.definition.binary,
            available=True,
            version=version,
            auth_ok=None,
            detail=detail,
        )

    def build_command(
        self,
        task: AgentTask,
        workspace: Workspace,
        prompt_file: Path,
        result_file: Path,
        prompt_text: str,
    ) -> list[str]:
        values = {
            "workspace": str(workspace.root),
            "prompt_file": str(prompt_file),
            "result_file": str(result_file),
            "prompt_text": prompt_text,
            "max_turns": str(task.max_turns),
        }
        return [self.definition.binary, *[part.format(**values) for part in self.definition.args]]

    async def spawn(self, task: AgentTask, workspace: Workspace) -> AsyncIterator[AgentEvent]:
        workspace.root.mkdir(parents=True, exist_ok=True)
        prompt_file = workspace.root / "task.md"
        result_file = workspace.root / "result.json"
        if result_file.exists():
            result_file.unlink()
        prompt_text = render_task_prompt(self.name, task, result_file)
        prompt_file.write_text(prompt_text, encoding="utf-8")
        command = self.build_command(task, workspace, prompt_file, result_file, prompt_text)
        if shutil.which(command[0]) is None:
            raise RuntimeUnavailable(f"runtime {self.name!r} binary not found: {command[0]}")

        yield AgentEvent(kind="progress", message=f"starting {self.name}")
        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=workspace.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_lines: list[str] = []
        stderr_task = asyncio.create_task(_read_pipe_lines(process.stderr))
        accumulated = CostDelta()
        final_payload: Any | None = None
        final_events = 0
        try:
            while True:
                raw_line = await _read_stdout_line(process, started, task.deadline_seconds, self.name)
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                stdout_lines.append(line)
                event, payload_candidate = _event_from_json_line(line, self.name, task.model)
                if event is None:
                    continue
                if event.kind == "final" and event.result is not None:
                    final_events += 1
                    if final_events > 1:
                        await _kill_process(process)
                        raise RuntimeExecutionError(f"{self.name} emitted multiple final events")
                    final_payload = event.result.content
                    continue
                if final_events:
                    await _kill_process(process)
                    raise RuntimeExecutionError(f"{self.name} emitted event after final")
                if event.kind == "cost_delta" and event.cost is not None:
                    accumulated = CostDelta(
                        tokens_in=accumulated.tokens_in + event.cost.tokens_in,
                        tokens_out=accumulated.tokens_out + event.cost.tokens_out,
                        usd=round(accumulated.usd + event.cost.usd, 6),
                    )
                    yield event
                    if task.budget_usd > 0 and accumulated.usd > task.budget_usd:
                        await _kill_process(process)
                        raise RuntimeExecutionError(f"{self.name} exceeded task budget ${task.budget_usd:.2f} with reported cost ${accumulated.usd:.2f}")
                    continue
                yield event
            await _wait_for_process(process, started, task.deadline_seconds, self.name)
        finally:
            if process.returncode is None:
                await _kill_process(process)
            stderr_lines = await stderr_task

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        if process.returncode != 0:
            tail = (stderr or stdout).strip().splitlines()[-5:]
