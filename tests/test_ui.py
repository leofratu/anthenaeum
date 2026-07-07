from __future__ import annotations

from io import StringIO

from rich.console import Console

from athenaeum.effort import get_effort
from athenaeum.ui import _build_effort_slider, _effort_animation_frame


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
