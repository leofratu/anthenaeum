from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EffortProfile:
    name: str
    tagline: str
    capability_bias: str
    debaters: int
    rounds: int
    skeptics_per_claim: int
    scale_strategy: str
    court_panels: tuple[str, ...]
    evolve_generations: int
    reflexion_iterations: int
    default_budget: float
    accent: str
    refresh_per_second: int


EFFORTS: dict[str, EffortProfile] = {
    "low": EffortProfile(
        "low", "Faster", "fast", 2, 1, 1, "none", ("argument",), 2, 1, 0.50,
        "steel_blue", 3,
    ),
    "medium": EffortProfile(
        "medium", "Balanced", "fast+reasoner", 3, 2, 2, "best_of_2",
        ("argument", "domain"), 4, 2, 1.50, "cyan3", 8,
    ),
    "high": EffortProfile(
        "high", "Thorough", "reasoner", 4, 3, 3, "best_of_3",
        ("argument", "audience", "sentiment", "thinker", "domain"), 6, 4, 5.00,
        "medium_purple2", 10,
    ),
    "vhigh": EffortProfile(
        "vhigh", "Relentless", "reasoner", 5, 4, 4, "tournament-4",
        ("argument", "audience", "sentiment", "thinker", "domain", "poll"), 8, 6,
        12.00, "orchid", 12,
    ),
    "max": EffortProfile(
        "max", "No stone unturned", "reasoner", 6, 5, 5, "tournament-8",
        ("argument", "audience", "sentiment", "thinker", "domain", "poll", "revision2"),
        12, 8, 30.00, "orange3", 15,
    ),
    "ultra": EffortProfile(
        "ultra", "Adversarial exhaustive", "reasoner", 8, 7, 7, "tournament-16",
        ("argument", "audience", "sentiment", "thinker", "domain", "poll", "revision2", "replication", "redteam"),
        16, 12, 75.00, "gold1", 18,
    ),
}


EFFORT_ALIASES: dict[str, str] = {
    "iq-low": "low",
    "iq-medium": "medium",
    "iq-high": "high",
    "iq-vhigh": "vhigh",
    "iq-very-high": "vhigh",
    "iq-max": "max",
    "iq-ultra": "ultra",
    "iq100": "low",
    "iq110": "low",
    "iq120": "medium",
    "iq130": "high",
    "iq140": "high",
    "iq150": "vhigh",
    "iq160": "max",
    "iq180": "ultra",
}


def get_effort(name: str) -> EffortProfile:
    key = _resolve_effort_key(name)
    if key not in EFFORTS:
        valid = ", ".join((*EFFORTS, *EFFORT_ALIASES))
        raise ValueError(f"unknown effort {name!r}; expected one of: {valid}")
    return EFFORTS[key]


def _resolve_effort_key(name: str) -> str:
    key = name.strip().lower().replace("_", "-")
    if key.isdigit():
        key = f"iq{key}"
    if key.startswith("iq-") and key[3:].isdigit():
        key = f"iq{key[3:]}"
    return EFFORT_ALIASES.get(key, key)
