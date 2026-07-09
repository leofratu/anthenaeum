from __future__ import annotations

import asyncio
import json
import shlex
import shutil
import subprocess
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    AgentEvent,
    AgentResult,
    AgentTask,
    CostDelta,
    RuntimeExecutionError,
    RuntimeHealth,
    RuntimeMeta,
    RuntimeUnavailable,
    SchemaValidationError,
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
            raise RuntimeExecutionError(f"{self.name} exited {process.returncode}: {' | '.join(tail)}")

        payload = _extract_payload(stdout, result_file)
        if final_payload is not None:
            payload = final_payload
        result = AgentResult.from_payload(payload, runtime=self.name, model=task.model)
        try:
            validate_json_schema_subset(result.content, task.output_schema)
        except SchemaValidationError:
            repaired = _repair_payload(result.content, task.output_schema, stdout)
            result = AgentResult.from_payload(repaired, runtime=self.name, model=task.model)
            validate_json_schema_subset(result.content, task.output_schema)
        result.runtime_meta = RuntimeMeta(
            runtime=self.name,
            model=task.model,
            command=command,
            duration_seconds=round(time.perf_counter() - started, 3),
            exit_code=process.returncode,
        )
        if accumulated.usd > 0 and result.cost.usd <= 0:
            result.cost = accumulated
        yield AgentEvent(kind="final", result=result)


def definition_from_command(name: str, command: str, version_args: tuple[str, ...]) -> RuntimeDefinition:
    parts = shlex.split(command)
    if not parts:
        raise ValueError(f"runtime {name!r} has an empty command")
    return RuntimeDefinition(name=name, binary=parts[0], args=tuple(parts[1:]), version_args=version_args)


async def _read_pipe_lines(stream: asyncio.StreamReader | None) -> list[str]:
    if stream is None:
        return []
    lines: list[str] = []
    while True:
        line = await stream.readline()
        if not line:
            return lines
        lines.append(line.decode("utf-8", errors="replace").rstrip("\r\n"))


async def _read_stdout_line(process: asyncio.subprocess.Process, started: float, deadline_seconds: int, runtime_name: str) -> bytes:
    if process.stdout is None:
        return b""
    remaining = _remaining_seconds(started, deadline_seconds)
    if remaining <= 0:
        await _kill_process(process)
        raise RuntimeExecutionError(f"{runtime_name} exceeded {deadline_seconds}s deadline")
    try:
        return await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
    except TimeoutError as exc:
        await _kill_process(process)
        raise RuntimeExecutionError(f"{runtime_name} exceeded {deadline_seconds}s deadline") from exc


async def _wait_for_process(process: asyncio.subprocess.Process, started: float, deadline_seconds: int, runtime_name: str) -> None:
    remaining = _remaining_seconds(started, deadline_seconds)
    if remaining <= 0:
        await _kill_process(process)
        raise RuntimeExecutionError(f"{runtime_name} exceeded {deadline_seconds}s deadline")
    try:
        await asyncio.wait_for(process.wait(), timeout=remaining)
    except TimeoutError as exc:
        await _kill_process(process)
        raise RuntimeExecutionError(f"{runtime_name} exceeded {deadline_seconds}s deadline") from exc


async def _kill_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    with suppress(ProcessLookupError):
        process.kill()
    with suppress(ProcessLookupError):
        await process.wait()


def _remaining_seconds(started: float, deadline_seconds: int) -> float:
    return max(float(deadline_seconds) - (time.perf_counter() - started), 0.0)


def render_task_prompt(runtime_name: str, task: AgentTask, result_file: Path) -> str:
    schema = json.dumps(task.output_schema or {"type": "object"}, indent=2, sort_keys=True)
    payload = json.dumps(task.input_payload, indent=2, sort_keys=True)
    return (
        f"You are running as the ATHENAEUM {runtime_name} runtime.\n\n"
        f"Task:\n{task.prompt}\n\n"
        f"Input payload:\n{payload}\n\n"
        f"Tool policy: {task.tool_policy}\nBudget ceiling for this task: ${task.budget_usd:.2f}\n\n"
        "Return the final answer as JSON. Prefer writing that JSON to this file:\n"
        f"{result_file}\n\n"
        "The JSON content must satisfy this schema:\n"
        f"{schema}\n"
    )


def _extract_payload(stdout: str, result_file: Path) -> Any:
    if result_file.exists():
        return json.loads(result_file.read_text(encoding="utf-8"))
    for line in reversed(stdout.splitlines()):
        parsed = _loads_json(line)
        if parsed is None:
            continue
        if isinstance(parsed, dict) and parsed.get("type") in {"final", "result", "completed"}:
            return parsed.get("result", parsed.get("content", parsed))
        return parsed
    stripped = stdout.strip()
    if stripped:
        return {"content": stripped}
    raise RuntimeExecutionError("runtime completed without result JSON or stdout content")


def _event_from_json_line(line: str, runtime: str, model: str | None) -> tuple[AgentEvent | None, Any | None]:
    parsed = _loads_json(line)
    if not isinstance(parsed, dict):
        return None, None
    event_type = parsed.get("type") or parsed.get("kind")
    if event_type in {"progress", "status"}:
        return AgentEvent(kind="progress", message=str(parsed.get("message") or parsed.get("status") or "progress"), raw=parsed), None
    if event_type in {"cost", "cost_delta"}:
        from .models import CostDelta

        cost = CostDelta.model_validate(parsed.get("cost") or parsed.get("delta") or {})
        return AgentEvent(kind="cost_delta", cost=cost, raw=parsed), None
    if event_type in {"tool", "tool_call"}:
        return AgentEvent(kind="tool_call", message=str(parsed.get("name") or parsed.get("message") or "tool_call"), raw=parsed), None
    if event_type in {"final", "result", "completed"}:
        payload = parsed.get("result", parsed.get("content", parsed))
        return AgentEvent(kind="final", result=AgentResult.from_payload(payload, runtime=runtime, model=model), raw=parsed), payload
    return None, None


def _repair_payload(content: Any, schema: dict[str, Any], stdout: str) -> Any:
    required = set(schema.get("required", []))
    properties = schema.get("properties", {})
    if "report_markdown" in required or "report_markdown" in properties:
        if isinstance(content, str):
            return {"report_markdown": content, "title": "CLI Runtime Output", "question": "runtime task", "summary": "Repaired plain-text CLI output."}
        if isinstance(content, dict):
            repaired = dict(content)
            repaired.setdefault("report_markdown", repaired.get("text") or repaired.get("message") or stdout.strip() or "")
            repaired.setdefault("title", "CLI Runtime Output")
            repaired.setdefault("question", "runtime task")
            repaired.setdefault("summary", "Repaired CLI output to match the report schema.")
            return repaired
    return content


def _loads_json(value: str) -> Any | None:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _first_line(value: str) -> str | None:
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None
