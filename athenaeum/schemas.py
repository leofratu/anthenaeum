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
