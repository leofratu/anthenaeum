from __future__ import annotations

import json
from pathlib import Path

from athenaeum.schemas import (
    ArgumentMap,
    CitationRef,
    ClaimLedgerRow,
    ClaimRef,
    ConvergenceReport,
    CourtOpinion,
    DebateOutput,
    DebateRound,
    EvolveCandidate,
    EvolveOutput,
    ExperimentPlan,
    ExperimentResult,
    OutlineSection,
    PanelOpinion,
    Perspective,
    Position,
    ReportOutput,
    ResearchOutput,
    ResearchQuestion,
    ReviewOutput,
    ReviewerCourtOutput,
    RevisionIteration,
    ReviseOutput,
    ScienceOutput,
    ScienceRunOutput,
    SkepticVerdict,
    SourceNote,
    ToulminArgument,
    Verdict,
    VerificationSummary,
    VerifyOutput,
)
from .context import RunContext


class DeterministicLoopEngine:
    def __init__(self, context: RunContext):
        self.context = context
        self.context.artifact_root.mkdir(parents=True, exist_ok=True)

    def run_auto(self) -> ReportOutput:
        research = self.research()
        debate = self.debate(research)
        draft = self.draft(research, debate)
        verify = self.verify(draft, research)
        court = self.court(draft, verify, debate)
        revise = self.revise(draft, verify, court)
        self._write("output.json", revise.final_report)
        return revise.final_report

    def run_evolve(self, prompt: str, generations: int, axes: list[str]) -> EvolveOutput:
        archive: list[EvolveCandidate] = []
        snapshots = []
        operators = ["steelman", "attack-and-repair", "cross-pollinate", "radicalize", "moderate"]
        for generation in range(1, generations + 1):
            operator = operators[(generation - 1) % len(operators)]
            axis_values = {axis: self._axis_value(prompt, axis, generation) for axis in axes}
            candidate = EvolveCandidate(
                id=f"elite-{self.context.stable_id('evolve', generation, length=8)}",
                thesis=f"Generation {generation} uses {operator} to frame: {prompt}",
                axes=axis_values,
                fitness=round(5.0 + min(generation, 8) * 0.45, 2),
                strongest_objection="The thesis needs externally verified evidence before deployment.",
                repair="Send the candidate through research, verify, and court before final use.",
            )
            archive.append(candidate)
            snapshots.append({"generation": generation, "operator": operator, "admitted": candidate.model_dump(mode="json")})
        markdown = "\n".join([f"# Evolve Archive: {prompt}", "", f"Generations: {generations}", "", "## MAP-Elites Archive"] + [f"- `{item.id}` fitness {item.fitness}: {item.thesis}" for item in archive])
        output = EvolveOutput(prompt=prompt, generations=generations, axes=axes, archive=archive, report_markdown=markdown)
        self._write("evolve.archive.json", output)
        self._write_jsonl("evolve.generations.jsonl", snapshots)
        self._write_text("evolve.md", markdown)
        self._write("output.json", output)
        return output

    def run_review(self, source_path: str, draft_text: str, court_name: str, audience: str | None) -> ReviewOutput:
        words = draft_text.split()
        claim = ClaimRef(id=f"claim-{self.context.stable_id('review', source_path, length=8)}", text=f"The reviewed draft contains {len(words)} words.", status="verified", confidence=1.0)
        arg = ToulminArgument(claim=claim.text, grounds="Deterministic parser counted input tokens.", warrant="Input size is directly observable.")
        verdicts = [Verdict(reviewer="argument", severity="minor", section_anchor="document", finding="Standalone review completed with deterministic local court.", evidence=f"Court selection: {court_name}.", suggested_fix="Use API/CLI runtimes for live external review.", confidence=0.75)]
        opinion = CourtOpinion(score_before=6.0, score_after=6.6, blockers=0, major_findings=0, verdicts=verdicts)
        output = ReviewOutput(source_path=source_path, audience=audience, court=opinion, report_markdown="\n".join([f"# Review: {Path(source_path).name}", "", f"Audience: {audience or 'educated generalist'}", "", "## Findings", *[f"- `{v.severity}` {v.finding}" for v in verdicts]]))
        self._write_text("draft.input.md", draft_text)
        self._write("argmap.json", ArgumentMap(arguments=[arg]))
        self._write("court.json", ReviewerCourtOutput(argmap=ArgumentMap(arguments=[arg]), panels=[PanelOpinion(panel="argument", verdicts=verdicts)], opinion=opinion))
        self._write_jsonl("claims.jsonl", [claim.model_dump(mode="json")])
        self._write("output.json", output)
        self._write_text("review.md", output.report_markdown)
        return output

    def run_science(self, hypothesis: str, sandbox: str, max_experiments: int) -> ScienceRunOutput:
        plan = ExperimentPlan(id=f"exp-plan-{self.context.stable_id('science-plan', hypothesis, length=8)}", hypothesis=hypothesis, method="deterministic in-process simulation", sandbox=sandbox, deterministic_seed=self.context.seed)
        results = []
        for index in range(1, max_experiments + 1):
            baseline = 100.0 + index
            improved = baseline * 0.82 if "cache" in hypothesis.lower() or "caching" in hypothesis.lower() else baseline
            status = "simulated" if improved < baseline else "blocked"
            results.append(ExperimentResult(id=f"exp-{index}", plan_id=plan.id, status=status, observations={"baseline_ms": round(baseline, 2), "candidate_ms": round(improved, 2)}))
        verdict = Verdict(reviewer="methods", severity="minor" if any(r.status == "simulated" for r in results) else "major", section_anchor="methods", finding="Science loop used deterministic safe simulation.", evidence="No shell commands or network operations were run.", suggested_fix="Use Codex/Claude sandbox runtime for executable experiments.", confidence=0.85)
        writeup = ScienceOutput(hypothesis=hypothesis, sandbox=sandbox, max_experiments=max_experiments, stage="complete" if any(r.status == "simulated" for r in results) else "blocked", methods_gate=[verdict], report_markdown="\n".join([f"# Science Run: {hypothesis}", "", f"Sandbox: `{sandbox}`", "", "## Results", *[f"- `{r.status}` {r.observations}" for r in results]]))
        output = ScienceRunOutput(plan=plan, results=results, writeup=writeup)
        self._write("experiment_plan.json", plan)
        self._write_jsonl("experiment_results.jsonl", [r.model_dump(mode="json") for r in results])
        self._write("methods_gate.json", {"verdicts": [verdict.model_dump(mode="json")]})
        self._write_text("science.writeup.md", writeup.report_markdown)
        self._write("output.json", output)
        return output

    def research(self) -> ResearchOutput:
        keywords = self.context.keywords()
        perspective_names = ["policy", "security", "economics", "civil liberties", "implementation", "stakeholder"]
        perspectives = [
            Perspective(id=f"p-{index}", name=name, rationale=f"Examines {self.context.question} through {name} tradeoffs.")
            for index, name in enumerate(perspective_names[:4], start=1)
        ]
        questions = [
            ResearchQuestion(id=f"rq-{index}", perspective_id=perspective.id, question=f"What evidence would change the {perspective.name} view on {self.context.question}?")
            for index, perspective in enumerate(perspectives, start=1)
        ]
        citations = [
            CitationRef(id="spec-think-tank", title="ATHENAEUM technical specification", source_type="spec", quote="Every factual claim is ledgered and verified."),
            CitationRef(id="spec-bibliography", title="ATHENAEUM annotated bibliography", source_type="spec", quote="Multi-agent debate, verification, and reviewer courts ground the design."),
        ]
        sources = [
            SourceNote(
                id=f"src-{index}",
                title=f"Local source note for {keyword}",
                reliability="medium",
                stance="background",
                quotes=[f"{keyword} is relevant to the question and should be verified against external evidence in non-minimal mode."],
            )
            for index, keyword in enumerate(keywords[:4], start=1)
        ]
        claims = [
            ClaimRef(id=f"claim-{self.context.stable_id('research', keyword, length=8)}", text=f"The question depends on {keyword} considerations.", status="unverified", citation_ids=["spec-think-tank"], confidence=0.45)
            for keyword in keywords[:3]
        ]
        outline = [OutlineSection(id="sec-summary", title="Executive Summary", claim_ids=[claim.id for claim in claims])]
        output = ResearchOutput(question=self.context.question, perspectives=perspectives, research_questions=questions, sources=sources, outline=outline, claims=claims, citations=citations)
        self._write("research.json", output)
