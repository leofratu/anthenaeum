from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThinkerLens:
    key: str
    name: str
    short_style: str
    strengths: tuple[str, ...]
    cautions: tuple[str, ...]
    prompt_guidance: str

    def prompt_block(self) -> str:
        strengths = "; ".join(self.strengths)
        cautions = "; ".join(self.cautions)
        return (
            f"{self.name} ({self.key})\n"
            f"Style: {self.short_style}\n"
            f"Strengths: {strengths}\n"
            f"Cautions: {cautions}\n"
            f"Guidance: {self.prompt_guidance}"
        )


@dataclass(frozen=True)
class ThinkerPanel:
    lenses: tuple[ThinkerLens, ...]
    preset: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(lens.key for lens in self.lenses)

    def prompt(self) -> str:
        blocks = "\n\n".join(lens.prompt_block() for lens in self.lenses)
        preset_text = f" Preset: {self.preset}." if self.preset else ""
        return (
            f"Use these public thinker lenses as review styles, not literal impersonation.{preset_text} "
            "Report clear conclusions, assumptions, strongest objections, falsifiers or tests, "
            "evidence needed, confidence, and concise rationale summaries; keep private reasoning "
            "private and do not provide hidden reasoning traces.\n\n"
            f"{blocks}"
        )


@dataclass(frozen=True)
class PanelPreset:
    key: str
    lenses: tuple[str, ...]
    use: str


THINKER_LENSES: dict[str, ThinkerLens] = {
    "einstein": ThinkerLens(
        key="einstein",
        name="Albert Einstein",
        short_style="Search for invariants, simple models, and hidden assumptions.",
        strengths=(
            "reduces complex systems to load-bearing principles",
            "tests conclusions against limiting cases",
            "notices symmetry, equivalence, and frame-of-reference errors",
        ),
        cautions=(
            "may overvalue elegant abstractions",
            "can underweight implementation friction or messy institutions",
        ),
        prompt_guidance=(
            "State the simplest model that explains the issue, identify assumptions that would change "
            "the conclusion, and give a concise rationale summary with any limiting-case checks."
        ),
    ),
    "feynman": ThinkerLens(
        key="feynman",
        name="Richard Feynman",
        short_style="Rebuild from first principles in plain language.",
        strengths=(
            "exposes jargon and hand-waving",
            "checks mechanisms rather than labels",
            "turns abstractions into concrete examples",
        ),
        cautions=(
            "may discount useful expert shorthand",
            "can spend too long reconstructing settled background",
        ),
        prompt_guidance=(
            "Explain the mechanism plainly, name what would be observed if the explanation is right, "
            "and summarize the rationale without showing private reasoning."
        ),
    ),
    "kahneman": ThinkerLens(
        key="kahneman",
        name="Daniel Kahneman",
        short_style="Audit bias, base rates, noise, and confidence.",
        strengths=(
            "calibrates confidence against base rates",
            "spots cognitive biases and forecast overreach",
            "separates evidence quality from narrative fluency",
        ),
        cautions=(
            "can become overly conservative",
            "may underweight rare structural breaks",
        ),
        prompt_guidance=(
            "Give the likely base rate, main bias risks, confidence level, and a concise rationale "
            "for how the evidence changes the prior."
        ),
    ),
    "popper": ThinkerLens(
        key="popper",
        name="Karl Popper",
        short_style="Prefer falsifiable claims and risky predictions.",
        strengths=(
            "turns vague claims into testable propositions",
            "highlights disconfirming evidence",
            "separates explanation from prediction",
        ),
        cautions=(
            "can be too strict for exploratory or interpretive questions",
            "may miss value judgments that are not empirical claims",
        ),
        prompt_guidance=(
            "List the claim that would be falsified, the strongest potential disconfirmers, and the "
            "conclusion that survives those tests with a brief rationale summary."
        ),
    ),
    "ostrom": ThinkerLens(
        key="ostrom",
        name="Elinor Ostrom",
        short_style="Analyze governance, incentives, trust, and local rules.",
        strengths=(
            "maps stakeholders and enforcement incentives",
            "checks institutional fit instead of assuming central control",
            "balances shared-resource risks with practical monitoring",
        ),
        cautions=(
            "may add governance complexity where simple ownership works",
            "can underweight fast-moving technical constraints",
        ),
        prompt_guidance=(
            "Identify the relevant actors, incentives, monitoring needs, and governance failure modes; "
            "then provide a concise rationale for the recommended institutional design."
        ),
    ),
    "taleb": ThinkerLens(
        key="taleb",
        name="Nassim Nicholas Taleb",
        short_style="Stress-test tail risk, fragility, convexity, and optionality.",
        strengths=(
            "surfaces hidden downside and ruin risks",
            "distinguishes robust, fragile, and antifragile choices",
            "values optionality under uncertainty",
        ),
        cautions=(
            "may overemphasize worst-case scenarios",
            "can underweight steady compounding benefits",
        ),
        prompt_guidance=(
            "Call out ruin risks, asymmetry, optionality, and fragility; provide the conclusion and a "
            "concise rationale summary focused on payoff shape."
        ),
    ),
    "darwin": ThinkerLens(
        key="darwin",
        name="Charles Darwin",
        short_style="Look for selection pressures, adaptation, and variation.",
        strengths=(
            "tracks incentives and environmental pressures over time",
            "compares competing adaptations",
            "notices gradual accumulation and path dependence",
        ),
        cautions=(
            "may overfit evolutionary metaphors",
            "can make current outcomes seem more optimal than they are",
        ),
        prompt_guidance=(
            "Describe the selection pressures, variants, and likely adaptations over time; summarize "
            "the rationale for which traits or strategies should persist."
        ),
    ),
    "lovelace": ThinkerLens(
        key="lovelace",
        name="Ada Lovelace",
        short_style="Combine formal procedure with imaginative use cases.",
        strengths=(
            "connects symbolic systems to practical workflows",
            "finds expressive uses beyond the obvious calculation",
            "keeps algorithmic steps tied to human purpose",
        ),
        cautions=(
            "may speculate beyond available implementation evidence",
            "can underweight operational maintenance costs",
        ),
        prompt_guidance=(
            "Specify the procedure, its intended human use, and where the design can generalize; give "
            "a concise rationale summary for the proposed abstraction."
        ),
    ),
    "turing": ThinkerLens(
        key="turing",
        name="Alan Turing",
        short_style="Formalize the problem, interfaces, and computable tests.",
        strengths=(
            "turns ambiguous tasks into precise procedures",
            "checks interfaces and observable behavior",
            "separates capability claims from implementation details",
        ),
        cautions=(
            "may abstract away social context",
            "can focus on decidability when approximate judgment is enough",
        ),
        prompt_guidance=(
            "Define inputs, outputs, tests, and failure cases; present the conclusion with a concise "
            "rationale for why the procedure would or would not work."
        ),
    ),
    "franklin": ThinkerLens(
        key="franklin",
        name="Rosalind Franklin",
        short_style="Inspect evidence quality, measurement, and structural fit.",
        strengths=(
            "checks whether data actually supports the structure claimed",
            "prioritizes careful measurement and reproducibility",
            "separates signal from interpretive overreach",
        ),
        cautions=(
            "may delay action until evidence is cleaner",
            "can underweight useful abductive leaps",
        ),
        prompt_guidance=(
            "Assess evidence quality, measurement limits, and alternative structures; give the "
            "supported conclusion with a concise rationale summary."
        ),
    ),
}


PANEL_PRESETS: dict[str, PanelPreset] = {
    "foundations": PanelPreset("foundations", ("einstein", "feynman", "popper", "turing"), "assumptions, mechanisms, falsifiable tests, formal interfaces"),
    "risk": PanelPreset("risk", ("kahneman", "taleb", "popper", "franklin"), "calibration, tail risk, disconfirmation, evidence quality"),
    "governance": PanelPreset("governance", ("ostrom", "kahneman", "taleb", "popper"), "incentives, institutions, bias, downside"),
    "invention": PanelPreset("invention", ("lovelace", "turing", "feynman", "darwin"), "procedures, computability, mechanisms, adaptation"),
    "science": PanelPreset("science", ("franklin", "popper", "feynman", "darwin"), "measurement, falsification, mechanism, selection effects"),
    "executive": PanelPreset("executive", ("kahneman", "ostrom", "taleb", "einstein"), "decision quality, stakeholder fit, risk, simplifying model"),
    "redteam": PanelPreset("redteam", ("popper", "taleb", "kahneman", "franklin", "turing"), "adversarial tests, downside, calibration, evidence, interfaces"),
    "iq-high": PanelPreset("iq-high", ("einstein", "feynman", "kahneman", "popper"), "balanced high-effort review for serious questions"),
    "iq-vhigh": PanelPreset("iq-vhigh", ("einstein", "feynman", "kahneman", "popper", "taleb", "franklin"), "broader high-stakes review with risk and evidence checks"),
    "iq-max": PanelPreset("iq-max", ("einstein", "feynman", "kahneman", "popper", "taleb", "ostrom", "turing", "franklin"), "deep audit across first principles, risk, governance, computability, and evidence"),
    "iq-ultra": PanelPreset("iq-ultra", ("einstein", "feynman", "kahneman", "popper", "taleb", "ostrom", "darwin", "lovelace", "turing", "franklin"), "full public-lens panel for exhaustive adversarial review"),
}


def list_lenses() -> tuple[ThinkerLens, ...]:
    return tuple(THINKER_LENSES.values())


def list_panel_presets() -> tuple[PanelPreset, ...]:
    return tuple(PANEL_PRESETS.values())


def get_panel_preset(name: str) -> PanelPreset:
    key = name.strip().lower().replace("_", "-")
    aliases = {"red-team": "redteam", "iq160": "iq-max", "iq180": "iq-ultra"}
    key = aliases.get(key, key)
    if key not in PANEL_PRESETS:
        valid = ", ".join(PANEL_PRESETS)
        raise ValueError(f"unknown panel preset {name!r}; expected one of: {valid}")
    return PANEL_PRESETS[key]


def get_lens(name: str) -> ThinkerLens:
    key = name.strip().lower().replace("_", "-")
    aliases = {"nnt": "taleb", "ada": "lovelace", "rosalind": "franklin"}
    key = aliases.get(key, key)
    if key not in THINKER_LENSES:
        valid = ", ".join(THINKER_LENSES)
        raise ValueError(f"unknown thinker lens {name!r}; expected one of: {valid}")
    return THINKER_LENSES[key]


def build_panel(names: list[str] | tuple[str, ...] | str) -> ThinkerPanel:
    if isinstance(names, str):
        requested = tuple(part.strip() for part in names.split(",") if part.strip())
    else:
        requested = tuple(names)
    if not requested:
        raise ValueError("thinker panel requires at least one lens")
    if len(requested) == 1:
        key = requested[0].strip().lower().replace("_", "-")
        if key in PANEL_PRESETS or key in {"red-team", "iq160", "iq180"}:
            preset = get_panel_preset(requested[0])
            return ThinkerPanel(tuple(get_lens(name) for name in preset.lenses), preset.key)
    return ThinkerPanel(tuple(get_lens(name) for name in requested))
