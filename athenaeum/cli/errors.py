"""CLI contracts: exit codes, parameter validation, and fail-loud helpers.

These helpers encode the hard rules of the CLI surface:
- user input errors -> BadParameter / exit 2
- runtime/provider failures -> Exit 2 with journaled context
- never swallow unexpected exceptions
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn

import typer

from athenaeum.ui import console, render_error, render_hint

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_RUNTIME = 2


def bad_parameter(message: str, *, cause: BaseException | None = None) -> NoReturn:
    """Raise a Typer parameter error, optionally chaining the cause."""
    if cause is None:
        raise typer.BadParameter(message)
    raise typer.BadParameter(message) from cause


def exit_error(message: str, *, hint: str | None = None, code: int = EXIT_RUNTIME) -> NoReturn:
    """Print a red error (and optional hint), then exit non-zero."""
    render_error(message)
    if hint:
        render_hint(hint)
    raise typer.Exit(code)


def require(condition: bool, message: str, *, cause: BaseException | None = None) -> None:
    """Kernel-style invariant: fail immediately when a precondition is false."""
    if not condition:
        bad_parameter(message, cause=cause)


def catch_user_error[T](fn: Callable[[], T], *, prefix: str = "") -> T:
    """Run *fn* and convert KeyError/ValueError into BadParameter."""
    try:
        return fn()
    except (KeyError, ValueError) as exc:
        message = f"{prefix}{exc}" if prefix else str(exc)
        bad_parameter(message, cause=exc)


def print_finding(rule: str, message: str) -> None:
    console.print(f"{rule} {message}", style="red")
