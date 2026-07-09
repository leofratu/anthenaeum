from __future__ import annotations

from io import StringIO

from rich.console import Console

from athenaeum.effort import get_effort
from athenaeum.runtime.models import RuntimeHealth
from athenaeum.ui import (
    _build_effort_slider,
    _effort_animation_frame,
    render_doctor,
    render_effort_table,
    render_sessions_table,
)


def _render(renderable: object) -> str:
    buffer = StringIO()
    Console(file=buffer, force_terminal=False, color_system=None, width=120).print(renderable)
    return buffer.getvalue()


def test_high_effort_animation_frames_change() -> None:
    max_effort = get_effort("max")
    ultra = get_effort("ultra")

    assert _effort_animation_frame(max_effort, 0) != _effort_animation_frame(max_effort, 1)
    assert _effort_animation_frame(ultra, 0) != _effort_animation_frame(ultra, 1)


def test_effort_slider_shows_marker_selected_tier_and_help() -> None:
    text = _render(_build_effort_slider("ultra", tick=0, interactive=True))

    assert "▲" in text or "^" in text
    assert "Selected ULTRA - Adversarial exhaustive" in text
    assert "red-team" in text
    assert "Enter confirm" in text


def test_effort_slider_has_ascii_fallback(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    text = _render(_build_effort_slider("medium", tick=0, interactive=True))

    assert "^" in text
    assert "Selected MEDIUM - Balanced" in text
    assert " | " in text
    assert "←" not in text
    assert "·" not in text


def test_effort_table_lists_all_levels(capsys) -> None:
    render_effort_table()
    text = capsys.readouterr().out
    assert "Effort Levels" in text
    assert "ultra" in text
    assert "Adversarial exhaustive" in text


def test_sessions_table_empty(capsys) -> None:
    render_sessions_table([])
    assert "no sessions" in capsys.readouterr().out


def test_doctor_shows_ready_count(capsys) -> None:
    healths = [
        RuntimeHealth(name="minimal", binary="in-process", available=True, detail="ok"),
        RuntimeHealth(name="missing", binary="gone", available=False, detail="not found", fix="install gone"),
    ]
    render_doctor(healths)
    text = capsys.readouterr().out
    assert "Runtime Doctor" in text
    assert "1/2 runtimes ready" in text
    assert "fix: install gone" in text
