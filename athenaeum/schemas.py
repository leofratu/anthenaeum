from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CitationRef(BaseModel):
    id: str
    title: str
    url: str | None = None
    source_type: Literal["web", "paper", "repo", "file", "spec", "generated"] = "generated"
    retrieved_at: str = Field(default_factory=utc_now)
    quote: str | None = None


class ClaimRef(BaseModel):
    id: str
    text: str
    status: Literal["verified", "contested", "unverified", "refuted"] = "unverified"
    citation_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SourceNote(BaseModel):
    id: str
    title: str
    url: str | None = None
    reliability: Literal["high", "medium", "low", "unknown"] = "unknown"
    stance: Literal["supports", "opposes", "mixed", "background"] = "background"
    quotes: list[str] = Field(default_factory=list)


class ArtifactRef(BaseModel):
    path: str
    kind: Literal["json", "jsonl", "markdown", "text"]
    producer: str
    sha256: str
    schema_name: str | None = None


class Perspective(BaseModel):
    id: str
    name: str
    rationale: str


class ResearchQuestion(BaseModel):
    id: str
    perspective_id: str
    question: str


class OutlineSection(BaseModel):
    id: str
    title: str
    claim_ids: list[str] = Field(default_factory=list)


class ResearchOutput(BaseModel):
    kind: Literal["research"] = "research"
    question: str
    perspectives: list[Perspective]
    research_questions: list[ResearchQuestion]
    sources: list[SourceNote]
    outline: list[OutlineSection]
    claims: list[ClaimRef] = Field(default_factory=list)
    citations: list[CitationRef] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)


class ToulminArgument(BaseModel):
    claim: str
    grounds: str
    warrant: str
    backing: str | None = None
    qualifier: str | None = None
    rebuttal: str | None = None


class Position(BaseModel):
    id: str
    debater: str
    thesis: str
    toulmin_args: list[ToulminArgument]
    concessions: list[str] = Field(default_factory=list)


class DebateRound(BaseModel):
    round_index: int
    exchanges: list[str]
    converged_position_ids: list[str] = Field(default_factory=list)


class ConvergenceReport(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    injected_contrarian: bool = False


class DebateOutput(BaseModel):
    kind: Literal["debate"] = "debate"
    question: str
    positions: list[Position]
    rounds: list[DebateRound]
    convergence: ConvergenceReport
    unresolved_objections: list[str] = Field(default_factory=list)


class ClaimLedgerRow(BaseModel):
    claim: ClaimRef
    source_node: str
    load_bearing: int = Field(ge=0, le=5)
    checkability: int = Field(ge=0, le=5)
    verdict_reason: str


class SkepticVerdict(BaseModel):
    skeptic_id: str
    claim_id: str
    refutes: bool
    rationale: str
    citation_ids: list[str] = Field(default_factory=list)


class VerificationSummary(BaseModel):
    verified: int = 0
    contested: int = 0
    unverified: int = 0
    refuted: int = 0


class VerifyOutput(BaseModel):
    kind: Literal["verify"] = "verify"
    claims: list[ClaimLedgerRow]
    skeptic_runs: list[SkepticVerdict]
    summary: VerificationSummary


class ArgumentMap(BaseModel):
    arguments: list[ToulminArgument]
    weak_chains: list[str] = Field(default_factory=list)


class PanelOpinion(BaseModel):
    panel: Literal["argument", "audience", "sentiment", "thinker", "domain"]
    verdicts: list["Verdict"]


class ReviewerCourtOutput(BaseModel):
    kind: Literal["court"] = "court"
    argmap: ArgumentMap
    panels: list[PanelOpinion]
    opinion: "CourtOpinion"


class RevisionIteration(BaseModel):
    index: int
    score_before: float = Field(ge=0.0, le=10.0)
    score_after: float = Field(ge=0.0, le=10.0)
    actions: list[str]


class ReviseOutput(BaseModel):
    kind: Literal["revise"] = "revise"
    iterations: list[RevisionIteration]
    final_report: "ReportOutput"
    plateau_reason: str | None = None


class Verdict(BaseModel):
    reviewer: str
    severity: Literal["blocker", "major", "minor", "nit"]
    section_anchor: str
    finding: str
    evidence: str
    suggested_fix: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CourtOpinion(BaseModel):
    score_before: float = Field(default=0.0, ge=0.0, le=10.0)
    score_after: float = Field(default=0.0, ge=0.0, le=10.0)
    blockers: int = 0
    major_findings: int = 0
    verdicts: list[Verdict] = Field(default_factory=list)


class ReportOutput(BaseModel):
    kind: Literal["report"] = "report"
    title: str
    question: str
    summary: str
    report_markdown: str
    claims: list[ClaimRef] = Field(default_factory=list)
    citations: list[CitationRef] = Field(default_factory=list)
    court: CourtOpinion | None = None
    run_id: str | None = None
    generated_at: str = Field(default_factory=utc_now)


class EvolveCandidate(BaseModel):
    id: str
    thesis: str
    axes: dict[str, str] = Field(default_factory=dict)
    fitness: float = Field(default=0.0, ge=0.0, le=10.0)
    strongest_objection: str
    repair: str


class EvolveOutput(BaseModel):
    kind: Literal["evolve"] = "evolve"
    prompt: str
    generations: int = Field(ge=1)
    axes: list[str]
    archive: list[EvolveCandidate]
    report_markdown: str
    generated_at: str = Field(default_factory=utc_now)


class ReviewOutput(BaseModel):
    kind: Literal["review"] = "review"
    source_path: str
    audience: str | None = None
    court: CourtOpinion
    report_markdown: str
    generated_at: str = Field(default_factory=utc_now)


class ScienceOutput(BaseModel):
    kind: Literal["science"] = "science"
    hypothesis: str
    sandbox: str
    max_experiments: int = Field(ge=1)
    stage: Literal["planned", "blocked", "complete"] = "planned"
    methods_gate: list[Verdict] = Field(default_factory=list)
    report_markdown: str
    generated_at: str = Field(default_factory=utc_now)


class ExperimentPlan(BaseModel):
    id: str
    hypothesis: str
    method: str
    sandbox: str
    deterministic_seed: int


class ExperimentResult(BaseModel):
    id: str
    plan_id: str
    status: Literal["blocked", "simulated", "complete"]
    observations: dict[str, float | str]
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)


class ScienceRunOutput(BaseModel):
    kind: Literal["science_run"] = "science_run"
    plan: ExperimentPlan
    results: list[ExperimentResult]
    writeup: ScienceOutput


class SessionRecord(BaseModel):
    id: str
    question: str
    status: Literal["running", "paused", "stopped", "complete"] = "running"
    daily_budget: float = Field(ge=0.0)
    duration: str
    created_at: str = Field(default_factory=utc_now)
    last_wake_at: str | None = None


class CommandStatus(BaseModel):
    ok: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


OUTPUT_MODELS: dict[str, type[BaseModel]] = {
    "research": ResearchOutput,
    "debate": DebateOutput,
    "verify": VerifyOutput,
    "court": ReviewerCourtOutput,
    "revise": ReviseOutput,
    "report": ReportOutput,
    "evolve": EvolveOutput,
    "review": ReviewOutput,
    "science": ScienceOutput,
    "science_run": ScienceRunOutput,
    "session": SessionRecord,
    "status": CommandStatus,
}


for _model in (PanelOpinion, ReviewerCourtOutput, ReviseOutput):
    _model.model_rebuild()


def output_schema(name: str) -> dict[str, Any]:
    try:
        return OUTPUT_MODELS[name].model_json_schema()
    except KeyError as exc:
        valid = ", ".join(sorted(OUTPUT_MODELS))
        raise ValueError(f"unknown output schema {name!r}; expected one of: {valid}") from exc
