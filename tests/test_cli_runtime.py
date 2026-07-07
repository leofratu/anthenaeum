from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

from athenaeum.runtime import AgentTask, Workspace
from athenaeum.runtime.cli import CliRuntime, RuntimeDefinition
from athenaeum.runtime.models import RuntimeExecutionError


def test_cli_runtime_reads_result_file(tmp_path: Path) -> None:
    script = tmp_path / "fake_runtime.py"
    script.write_text(
        """
import json
import sys

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump({"report_markdown": "# Runtime OK"}, handle)
""".strip(),
        encoding="utf-8",
    )
    runtime = CliRuntime(
        RuntimeDefinition(
            name="fake",
            binary=sys.executable,
            args=(str(script), "{result_file}"),
            version_args=("--version",),
        )
    )
    task = AgentTask(
        prompt="write report",
        output_schema={
            "type": "object",
            "required": ["report_markdown"],
            "properties": {"report_markdown": {"type": "string"}},
        },
    )

    events = asyncio.run(_collect(runtime, task, Workspace(tmp_path / "workspace")))

    assert events[-1].kind == "final"
    assert events[-1].result is not None
    assert events[-1].result.content["report_markdown"] == "# Runtime OK"


def test_cli_runtime_repairs_plain_text_report(tmp_path: Path) -> None:
    script = tmp_path / "fake_runtime.py"
    script.write_text("print('# Plain report')", encoding="utf-8")
    runtime = CliRuntime(RuntimeDefinition(name="fake", binary=sys.executable, args=(str(script),)))
    task = AgentTask(
        prompt="write report",
        output_schema={
            "type": "object",
            "required": ["title", "question", "summary", "report_markdown"],
            "properties": {"report_markdown": {"type": "string"}},
        },
    )

    events = asyncio.run(_collect(runtime, task, Workspace(tmp_path / "workspace-plain")))

    assert events[-1].result is not None
    assert events[-1].result.content["report_markdown"] == "# Plain report"


def test_cli_runtime_parses_json_progress_and_final_events(tmp_path: Path) -> None:
    script = tmp_path / "fake_stream_runtime.py"
    script.write_text(
        """
import json

print(json.dumps({"type": "progress", "message": "working"}))
print(json.dumps({"type": "final", "result": {"report_markdown": "# Stream OK"}}))
""".strip(),
        encoding="utf-8",
    )
    runtime = CliRuntime(RuntimeDefinition(name="fake", binary=sys.executable, args=(str(script),)))
    task = AgentTask(
        prompt="write report",
        output_schema={
            "type": "object",
            "required": ["report_markdown"],
            "properties": {"report_markdown": {"type": "string"}},
        },
    )

    events = asyncio.run(_collect(runtime, task, Workspace(tmp_path / "workspace-stream")))

    assert [event.kind for event in events] == ["progress", "progress", "final"]
    assert events[0].message == "starting fake"
    assert events[1].message == "working"
    assert events[-1].result is not None
    assert events[-1].result.content["report_markdown"] == "# Stream OK"


def test_cli_runtime_streams_progress_before_process_exit(tmp_path: Path) -> None:
    ready_file = tmp_path / "progress-ready"
    done_file = tmp_path / "process-done"
    script = tmp_path / "fake_slow_stream_runtime.py"
    script.write_text(
        """
import json
import sys
import time
from pathlib import Path

ready_file = Path(sys.argv[1])
done_file = Path(sys.argv[2])

print(json.dumps({"type": "progress", "message": "first progress"}), flush=True)
ready_file.write_text("ready", encoding="utf-8")
time.sleep(0.8)
done_file.write_text("done", encoding="utf-8")
print(json.dumps({"type": "final", "result": {"report_markdown": "# Streamed"}}), flush=True)
""".strip(),
        encoding="utf-8",
    )
    runtime = CliRuntime(
        RuntimeDefinition(
            name="fake",
            binary=sys.executable,
            args=(str(script), str(ready_file), str(done_file)),
        )
    )
    task = AgentTask(
        prompt="write report",
        output_schema={
            "type": "object",
            "required": ["report_markdown"],
            "properties": {"report_markdown": {"type": "string"}},
        },
    )

    event = asyncio.run(
        _first_runtime_event_after_start(runtime, task, Workspace(tmp_path / "workspace-slow-stream"), ready_file)
    )

    assert event.kind == "progress"
    assert event.message == "first progress"
