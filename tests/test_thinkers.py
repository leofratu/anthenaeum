from __future__ import annotations

from athenaeum.effort import get_effort
from athenaeum.thinkers import build_panel, get_lens, get_panel_preset, list_lenses, list_panel_presets


def test_thinker_lenses_are_structured_public_guidance() -> None:
    lenses = list_lenses()

    assert {"einstein", "feynman", "kahneman", "popper", "ostrom", "taleb"} <= {
        lens.key for lens in lenses
    }
    for lens in lenses:
        assert lens.name
        assert lens.short_style
        assert lens.strengths
        assert lens.cautions
        assert "rationale" in lens.prompt_guidance.lower()
        assert "chain of thought" not in lens.prompt_guidance.lower()


def test_lens_lookup_and_panel_creation() -> None:
    assert get_lens("Feynman").key == "feynman"
    assert get_lens("nnt").key == "taleb"

    panel = build_panel("einstein, kahneman, taleb")

    assert panel.names == ("einstein", "kahneman", "taleb")
    prompt = panel.prompt().lower()
    assert "clear conclusions" in prompt
    assert "concise rationale summaries" in prompt
    assert "private reasoning private" in prompt
    assert "not literal impersonation" in prompt
    assert "hidden reasoning traces" in prompt
    assert "chain of thought" not in prompt


def test_panel_presets_expand_to_public_lenses() -> None:
    preset_keys = {preset.key for preset in list_panel_presets()}

    assert {"foundations", "risk", "iq-high", "iq-ultra"} <= preset_keys
    assert get_panel_preset("red-team").key == "redteam"
    assert get_panel_preset("iq160").key == "iq-max"

    risk = build_panel("risk")
    ultra = build_panel("iq-ultra")

    assert risk.preset == "risk"
    assert risk.names == ("kahneman", "taleb", "popper", "franklin")
    assert ultra.preset == "iq-ultra"
    assert "lovelace" in ultra.names
    assert "preset: iq-ultra" in ultra.prompt().lower()


def test_iq_aliases_resolve_to_existing_effort_profiles() -> None:
    assert get_effort("high").name == "high"
    assert get_effort("iq-low").name == "low"
    assert get_effort("iq-medium").name == "medium"
    assert get_effort("iq-high").name == "high"
    assert get_effort("iq-max").name == "max"
    assert get_effort("iq-ultra").name == "ultra"
    assert get_effort("iq120").name == "medium"
    assert get_effort("iq140").name == "high"
    assert get_effort("iq-160").name == "max"
    assert get_effort("160").name == "max"
