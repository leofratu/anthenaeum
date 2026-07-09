from __future__ import annotations

import pytest
import typer

from athenaeum.cli.errors import bad_parameter, catch_user_error, require


def test_require_passes_when_true() -> None:
    require(True, "should not raise")


def test_require_raises_bad_parameter() -> None:
    with pytest.raises(typer.BadParameter, match="must be set"):
        require(False, "must be set")


def test_catch_user_error_wraps_value_error() -> None:
    with pytest.raises(typer.BadParameter, match="nope"):
        catch_user_error(lambda: (_ for _ in ()).throw(ValueError("nope")))


def test_bad_parameter_chains_cause() -> None:
    cause = KeyError("missing")
    with pytest.raises(typer.BadParameter) as exc_info:
        bad_parameter("unknown key", cause=cause)
    assert exc_info.value.__cause__ is cause
