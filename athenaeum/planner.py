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
