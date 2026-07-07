from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

from .effort import EffortProfile, get_effort


ComplexityLabel = Literal["simple", "moderate", "complex", "frontier"]
ReviewDepth = Literal["light", "standard", "deep", "exhaustive", "adversarial"]


@dataclass(frozen=True)
class ComplexityRating:
    score: int
    label: ComplexityLabel
    rationale: str


@dataclass(frozen=True)
class PlannerModelRef:
    name: str
    provider: str | None = None
    runtime: str | None = None


@dataclass(frozen=True)
class PlannerLoop:
    name: str
    iterations: int
    purpose: str


@dataclass(frozen=True)
class ProviderRuntimeDiversity:
    providers: int
    runtimes: int
    strategy: str


@dataclass(frozen=True)
class PlannerDecision:
    question: str
    effort: str
    planner_model: PlannerModelRef
    complexity_rating: ComplexityRating
    selected_loops: tuple[PlannerLoop, ...]
    expert_panel_size: int
    agent_roles: tuple[str, ...]
    review_depth: ReviewDepth
    provider_runtime_diversity: ProviderRuntimeDiversity
    suggested_budget: float
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def shape_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("planner_model", None)
        return data


RunPlan = PlannerDecision


@dataclass(frozen=True)
class _PlannerTuning:
    loops: tuple[str, ...]
    panel_size: int
    roles: tuple[str, ...]
    review_depth: ReviewDepth
    providers: int
    runtimes: int
    diversity_strategy: str


_TUNING: dict[str, _PlannerTuning] = {
    "low": _PlannerTuning(
        ("research", "draft", "verify"),
        1,
        ("researcher", "writer"),
        "light",
        1,
        1,
        "single stable runtime",
    ),
    "medium": _PlannerTuning(
        ("research", "debate", "draft", "verify", "revise"),
        3,
        ("researcher", "domain_expert", "writer", "skeptic"),
        "standard",
        1,
        1,
        "primary runtime with deterministic fallback",
    ),
    "high": _PlannerTuning(
        ("research", "debate", "synthesis", "draft", "verify", "court", "revise"),
        5,
        ("researcher", "domain_expert", "operator", "skeptic", "judge", "writer"),
        "deep",
        2,
        1,
        "cross-provider review where available",
    ),
    "vhigh": _PlannerTuning(
        ("research", "debate", "source_audit", "synthesis", "draft", "verify", "court", "revise"),
        6,
        ("researcher", "domain_expert", "operator", "skeptic", "red_team", "judge", "writer"),
        "exhaustive",
        2,
        2,
        "independent reviewer runtime plus primary runtime",
    ),
    "max": _PlannerTuning(
        ("research", "debate", "source_audit", "synthesis", "draft", "verify", "red_team", "court", "revise", "final_judge"),
        8,
        ("researcher", "domain_expert", "operator", "skeptic", "red_team", "policy_reviewer", "judge", "writer"),
        "exhaustive",
        3,
        2,
        "provider and runtime tournament with final adjudication",
    ),
    "ultra": _PlannerTuning(
        (
            "research",
            "debate",
            "source_audit",
            "independent_replication",
            "synthesis",
            "draft",
            "verify",
            "red_team",
            "adversarial_tournament",
            "court",
            "revise",
            "final_judge",
        ),
        12,
        (
            "researcher",
            "domain_expert",
            "operator",
            "skeptic",
            "red_team",
            "policy_reviewer",
            "replicator",
            "judge",
            "writer",
        ),
        "adversarial",
        4,
        3,
        "multi-provider tournament with independent replication",
    ),
}


_LOOP_PURPOSES: dict[str, str] = {
    "research": "collect background and candidate evidence",
    "debate": "compare competing positions",
    "source_audit": "stress-test source quality and gaps",
    "independent_replication": "rerun key reasoning through a separate path",
    "synthesis": "merge evidence into a coherent answer shape",
    "draft": "produce the report candidate",
    "verify": "check load-bearing claims",
    "red_team": "seek failure modes and counterarguments",
    "adversarial_tournament": "pit strongest alternatives against the draft",
    "court": "adjudicate reviewer findings",
    "revise": "apply critique and tighten the answer",
    "final_judge": "make final acceptance call",
}

_COMPLEXITY_TERMS = {
    "architecture",
    "compliance",
    "constitutional",
    "deployment",
    "economic",
    "forecast",
    "governance",
    "legal",
    "medical",
    "migration",
    "policy",
    "privacy",
    "regulation",
    "risk",
    "safety",
    "security",
    "strategy",
    "tradeoff",
}


def plan_run(
    question: str,
    effort: str | EffortProfile,
    model_setting: str | PlannerModelRef | Mapping[str, Any],
    *,
    model_reasoning_effort: str | None = None,
) -> PlannerDecision:
    """Return a deterministic pre-run plan shape.

    The live planner will eventually use ``planner_model`` to call the main
    model. For now, ``model_reasoning_effort`` is intentionally ignored so API
    reasoning controls cannot alter the planned run shape.
    """
    del model_reasoning_effort

    effort_profile = effort if isinstance(effort, EffortProfile) else get_effort(effort)
    tuning = _TUNING[effort_profile.name]
    complexity = rate_complexity(question)
    complexity_bonus = _complexity_bonus(complexity.score)

    loops = tuple(
        PlannerLoop(
            name=name,
            iterations=_loop_iterations(name, effort_profile, complexity_bonus),
            purpose=_LOOP_PURPOSES[name],
        )
        for name in tuning.loops
    )
    diversity = ProviderRuntimeDiversity(
        providers=tuning.providers + (1 if complexity.label == "frontier" and tuning.providers < 4 else 0),
        runtimes=tuning.runtimes + (1 if complexity.label == "frontier" and tuning.runtimes < 3 else 0),
        strategy=tuning.diversity_strategy,
    )
    panel_size = tuning.panel_size + complexity_bonus
    budget = round(effort_profile.default_budget * _budget_multiplier(complexity.score), 2)
    loop_summary = ", ".join(loop.name for loop in loops[:3])
    summary = (
        f"{complexity.label} question planned at {effort_profile.name} effort: "
        f"{len(loops)} loops starting with {loop_summary}; {panel_size} experts; "
        f"{tuning.review_depth} review."
    )
    return PlannerDecision(
        question=question,
        effort=effort_profile.name,
        planner_model=_model_ref(model_setting),
        complexity_rating=complexity,
        selected_loops=loops,
        expert_panel_size=panel_size,
        agent_roles=tuning.roles,
        review_depth=tuning.review_depth,
        provider_runtime_diversity=diversity,
        suggested_budget=budget,
        summary=summary,
    )


def rate_complexity(question: str) -> ComplexityRating:
    tokens = [token.strip(".,;:!?()[]{}\"'").lower() for token in question.split()]
    words = [token for token in tokens if token]
    term_hits = sorted(set(words) & _COMPLEXITY_TERMS)
    score = 1
    score += min(len(words) // 18, 4)
    score += min(question.count("?"), 2)
    score += min(len(term_hits), 3)
    if any(marker in question.lower() for marker in ("compare", "trade off", "tradeoff", "versus", " vs ")):
        score += 1
    score = max(1, min(score, 10))

    if score <= 2:
        label: ComplexityLabel = "simple"
    elif score <= 4:
        label = "moderate"
    elif score <= 7:
        label = "complex"
    else:
        label = "frontier"

    if term_hits:
        rationale = f"{len(words)} words with complexity terms: {', '.join(term_hits[:4])}"
    else:
        rationale = f"{len(words)} words with limited explicit risk markers"
    return ComplexityRating(score=score, label=label, rationale=rationale)


def _model_ref(model_setting: str | PlannerModelRef | Mapping[str, Any]) -> PlannerModelRef:
    if isinstance(model_setting, PlannerModelRef):
        return model_setting
    if isinstance(model_setting, str):
        return PlannerModelRef(name=model_setting)
    return PlannerModelRef(
        name=str(model_setting.get("model") or model_setting.get("name") or "main"),
        provider=_optional_str(model_setting.get("provider")),
        runtime=_optional_str(model_setting.get("runtime")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _complexity_bonus(score: int) -> int:
    if score >= 8:
        return 2
    if score >= 5:
        return 1
    return 0


def _budget_multiplier(score: int) -> float:
    return max(0.85, min(1.45, 1 + ((score - 3) * 0.08)))


def _loop_iterations(name: str, effort: EffortProfile, complexity_bonus: int) -> int:
    effort_rounds = max(effort.rounds, 1)
    if name in {"debate", "red_team", "adversarial_tournament"}:
        return effort_rounds + complexity_bonus
    if name in {"verify", "source_audit", "independent_replication", "court", "final_judge"}:
        return max(1, effort.skeptics_per_claim // 2) + complexity_bonus
    if name == "revise":
        return max(1, effort.reflexion_iterations)
    return 1
