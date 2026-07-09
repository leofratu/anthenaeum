"""Filesystem and JSON emission helpers for the CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import typer

from athenaeum.artifacts import RunArtifacts, new_run_id
from athenaeum.cli.errors import require
from athenaeum.ui import console


def write_text_file(path: Path, text: str, *, overwrite: bool = True) -> None:
    require(overwrite or not path.exists(), f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    console.print(f"wrote {path}", style="green")


def write_new_text_file(path: Path, text: str) -> None:
    write_text_file(path, text, overwrite=False)


def write_output(path: Path, markdown: str, data: dict[str, object]) -> None:
    require(bool(markdown.strip()) or bool(data), "refusing to write empty output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    json_path = path.with_suffix(path.suffix + ".json") if path.suffix else Path(f"{path}.json")
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    console.print(f"wrote {path}", style="green")
    console.print(f"schema JSON {json_path}", style="grey58")


def emit_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2, sort_keys=True))


def make_run_id(question: str, seed: int | None) -> str:
    if seed is None:
        return new_run_id()
    return hashlib.sha256(f"{seed}|{question}".encode()).hexdigest()[:8]


def mode_artifacts(subject: str, mode: str, seed: int | None) -> RunArtifacts:
    artifacts = RunArtifacts(make_run_id(f"{mode}|{subject}", seed))
    artifacts.prepare()
    return artifacts


def as_report_text(content: Any) -> str:
    if isinstance(content, dict) and isinstance(content.get("report_markdown"), str):
        return content["report_markdown"]
    return str(content)
