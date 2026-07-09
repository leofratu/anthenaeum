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
    ReviewerCourtOutput,
    ReviewOutput,
    ReviseOutput,
    RevisionIteration,
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
        self._write_jsonl("source_notes.jsonl", [source.model_dump(mode="json") for source in sources])
        return output

    def debate(self, research: ResearchOutput) -> DebateOutput:
        roles = ["economist", "security", "civil-liberties", "operator", "contrarian", "domain"]
        count = {"low": 2, "medium": 3, "high": 4, "vhigh": 5, "max": 6}.get(self.context.effort, 4)
        positions = []
        for index, role in enumerate(roles[:count], start=1):
            arg = ToulminArgument(
                claim=f"{role} position on {self.context.question}",
                grounds=f"Research identified {len(research.sources)} local source notes and {len(research.perspectives)} perspectives.",
                warrant="A decision should survive multiple stakeholder lenses before being treated as robust.",
                backing="ATHENAEUM debate loop design.",
                qualifier="minimal-mode scaffold",
                rebuttal="External evidence can overturn this local analysis.",
            )
            positions.append(Position(id=f"pos-{index}", debater=role, thesis=f"{role} weighs the question through its primary risk lens.", toulmin_args=[arg], concessions=["Requires live evidence for final confidence."]))
        rounds = [DebateRound(round_index=index, exchanges=[f"round {index}: sparse critique exchange among {count} debaters"], converged_position_ids=[] ) for index in range(1, {"low": 1, "medium": 2, "high": 3, "vhigh": 4, "max": 5}.get(self.context.effort, 3) + 1)]
        output = DebateOutput(question=self.context.question, positions=positions, rounds=rounds, convergence=ConvergenceReport(score=0.62, reason="Deterministic local positions overlap but retain unresolved objections."), unresolved_objections=["Evidence quality is not established in minimal mode."])
        self._write("debate.json", output)
        self._write_jsonl("debate_transcript.jsonl", [round_.model_dump(mode="json") for round_ in rounds])
        return output

    def draft(self, research: ResearchOutput, debate: DebateOutput) -> ReportOutput:
        claims = [*research.claims]
        markdown = "\n".join([
            f"# ATHENAEUM Report: {self.context.question}",
            "",
            f"Run: `{self.context.run_id}`  ",
            f"Mode: `{self.context.mode}`  ",
            f"Effort: `{self.context.effort}`  ",
            f"Audience: {self.context.audience or 'educated generalist'}.",
            "",
            "## Executive Summary",
            f"The minimal engine examined {len(research.perspectives)} perspectives and {len(debate.positions)} debate positions. It does not claim live factual completeness.",
            "",
            "## Argument Map",
            *[f"- {position.debater}: {position.thesis}" for position in debate.positions],
            "",
            "## Claim Ledger",
            *[f"- `{claim.status}` {claim.text}" for claim in claims],
        ])
        output = ReportOutput(title=f"ATHENAEUM Report: {self.context.question}", question=self.context.question, summary="Deterministic minimal draft generated from local research and debate artifacts.", report_markdown=markdown, claims=claims, citations=research.citations, run_id=self.context.run_id)
        self._write("draft.initial.json", output)
        self._write_text("draft.initial.md", output.report_markdown)
        return output

    def verify(self, draft: ReportOutput, research: ResearchOutput) -> VerifyOutput:
        rows = []
        skeptic_runs = []
        summary = VerificationSummary()
        source_text = " ".join(quote for source in research.sources for quote in source.quotes).lower()
        for index, claim in enumerate(draft.claims, start=1):
            overlap = any(token in source_text for token in self.context.keywords(claim.text, 4))
            status = "verified" if overlap and claim.citation_ids else "unverified"
            setattr(summary, status, getattr(summary, status) + 1)
            claim = claim.model_copy(update={"status": status, "confidence": 0.72 if status == "verified" else 0.35})
            rows.append(ClaimLedgerRow(claim=claim, source_node="draft", load_bearing=3, checkability=4, verdict_reason="Local source-note token overlap." if overlap else "No supporting source note found."))
            skeptic_runs.append(SkepticVerdict(skeptic_id=f"sk-{index}", claim_id=claim.id, refutes=status != "verified", rationale="Minimal skeptic checks source-note overlap only.", citation_ids=claim.citation_ids))
        output = VerifyOutput(claims=rows, skeptic_runs=skeptic_runs, summary=summary)
        self._write("verify.json", output)
        self._write_jsonl("claims.jsonl", [row.claim.model_dump(mode="json") for row in rows])
        self._write_jsonl("skeptic_transcripts.jsonl", [run.model_dump(mode="json") for run in skeptic_runs])
        return output

    def court(self, draft: ReportOutput, verify: VerifyOutput, debate: DebateOutput) -> ReviewerCourtOutput:
        argmap = ArgumentMap(arguments=[arg for position in debate.positions for arg in position.toulmin_args], weak_chains=[row.claim.id for row in verify.claims if row.claim.status != "verified"])
        panels = []
        panel_names = ["argument", "audience", "sentiment", "thinker", "domain"]
        for name in panel_names:
            severity = "major" if name == "argument" and argmap.weak_chains else "minor"
            panels.append(PanelOpinion(panel=name, verdicts=[Verdict(reviewer=name, severity=severity, section_anchor="report", finding=f"{name} panel completed deterministic review.", evidence="Review used local artifacts only.", suggested_fix="Run with live providers for external evidence.", confidence=0.7)]))
        all_verdicts = [verdict for panel in panels for verdict in panel.verdicts]
        opinion = CourtOpinion(score_before=6.0, score_after=7.0, blockers=0, major_findings=sum(1 for verdict in all_verdicts if verdict.severity == "major"), verdicts=all_verdicts)
        output = ReviewerCourtOutput(argmap=argmap, panels=panels, opinion=opinion)
        self._write("court.json", output)
        self._write("argmap.json", argmap)
        return output

    def revise(self, draft: ReportOutput, verify: VerifyOutput, court: ReviewerCourtOutput) -> ReviseOutput:
        final_claims = [row.claim for row in verify.claims]
        ledger = _claim_status_lines(final_claims)
        body = _replace_section(draft.report_markdown, "Claim Ledger", ledger)
        final_markdown = body + "\n\n## Verification Appendix\n" + _claim_status_summary(final_claims) + "\n\n" + ledger + "\n\n## Court Summary\n" + f"Major findings addressed: {court.opinion.major_findings}."
        final = draft.model_copy(update={"report_markdown": final_markdown, "claims": final_claims, "court": court.opinion, "summary": draft.summary + " Claims were marked with deterministic verification status."})
        iteration = RevisionIteration(index=1, score_before=court.opinion.score_before, score_after=court.opinion.score_after, actions=["Added verification appendix.", "Attached court summary."])
        output = ReviseOutput(iterations=[iteration], final_report=final, plateau_reason="minimal mode performs one deterministic revision")
        self._write_jsonl("revisions.jsonl", [iteration.model_dump(mode="json")])
        self._write_text("report.revised.md", final.report_markdown)
        self._write("revise.json", output)
        return output

    def _write(self, name: str, model) -> None:
        path = self.context.artifact_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(model, "model_dump"):
            data = model.model_dump(mode="json")
        else:
            data = model
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _write_jsonl(self, name: str, rows: list[dict]) -> None:
        path = self.context.artifact_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    def _write_text(self, name: str, text: str) -> None:
        path = self.context.artifact_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _axis_value(self, prompt: str, axis: str, index: int) -> str:
        values = {
            "novelty": ("conventional", "adjacent", "heterodox"),
            "risk": ("conservative", "balanced", "aggressive"),
            "horizon": ("near", "mid", "far"),
        }.get(axis, ("low", "medium", "high"))
        offset = int(self.context.stable_id("axis", prompt, axis, length=2), 16)
        return values[(offset + index) % len(values)]


def _claim_status_lines(claims: list[ClaimRef]) -> str:
    return "\n".join(f"- `{claim.status}` {claim.text}" for claim in claims)


def _claim_status_summary(claims: list[ClaimRef]) -> str:
    counts = {status: 0 for status in ("verified", "contested", "unverified", "refuted")}
    for claim in claims:
        counts[claim.status] += 1
    return " · ".join(f"{status}: {count}" for status, count in counts.items() if count)


def _replace_section(markdown: str, title: str, body: str) -> str:
    heading = f"## {title}"
    lines = markdown.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return f"{markdown.rstrip()}\n\n{heading}\n{body}"
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join([*lines[:start], heading, body, *lines[end:]]).rstrip()
