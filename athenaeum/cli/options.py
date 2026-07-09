"""Shared CLI option fragments and command registration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

ConfigOpt = Annotated[Path | None, typer.Option("--config", help="Path to thinktank.toml.")]
OutOpt = Annotated[Path, typer.Option("--out", help="Output path.")]
BudgetOpt = Annotated[float | None, typer.Option("--budget", help="Hard USD budget ceiling.")]
DryRunOpt = Annotated[bool, typer.Option("--dry-run", help="Compile and print the workflow only.")]

EFFORT_HELP = "low|medium|high|vhigh|max|ultra plus iq-* aliases"
RUNTIME_HELP = "auto|minimal|api|opencode|codex|agy|claude|gemini"
REASONING_HELP = "auto|off|low|medium|high|vhigh|xhigh|max"
MODE_HELP = "auto|deliberate|decide|brief"

# Command groups for help ordering (Typer preserves registration order).
PRIMARY_COMMANDS = (
    "ask",
    "interactive",
    "doctor",
    "effort",
    "setup",
)
WORKFLOW_COMMANDS = (
    "evolve",
    "review",
    "science",
    "resume",
)
