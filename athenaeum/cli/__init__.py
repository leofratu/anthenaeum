"""ATHENAEUM CLI package.

Public entrypoint remains ``athenaeum.cli:app`` for the console script and tests.
"""

from __future__ import annotations

# Register all commands on ``app``.
from athenaeum.cli import commands_catalog as _commands_catalog  # noqa: F401
from athenaeum.cli import commands_core as _commands_core  # noqa: F401
from athenaeum.cli import commands_modes as _commands_modes  # noqa: F401
from athenaeum.cli import commands_ops as _commands_ops  # noqa: F401
from athenaeum.cli.app import app
from athenaeum.cli.constants import BUILTIN_PERSONAS, BUILTIN_WORKFLOWS
from athenaeum.ui import select_effort_slider

__all__ = [
    "BUILTIN_PERSONAS",
    "BUILTIN_WORKFLOWS",
    "app",
    "select_effort_slider",
]
