from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable

from athenaeum.artifacts import RunArtifacts
from athenaeum.loops import DeterministicLoopEngine
from athenaeum.loops.context import RunContext
from athenaeum.runtime.models import AgentEvent, AgentResult, CostDelta, RuntimeMeta
from athenaeum.schemas import DebateOutput, ReportOutput, ResearchOutput, ReviewerCourtOutput, ReviseOutput, VerifyOutput
from athenaeum.workflow import ExecutionPlan


@dataclass
class ConductorResult:
    report: ReportOutput
    skipped_nodes: tuple[str, ...]


class LocalConductor:
    def __init__(self, plan: ExecutionPlan, artifacts: RunArtifacts, context: RunContext, on_event: Callable[[AgentEvent], None] | None = None):
        self.plan = plan
        self.artifacts = artifacts
        self.context = context
        self.engine = DeterministicLoopEngine(context)
        self.on_event = on_event

    def run(self, completed_nodes: set[str] | None = None) -> ConductorResult:
        completed_nodes = completed_nodes or set()
        outputs: dict[str, object] = {}
        skipped: list[str] = []
        cache_prefix_valid = True
        for node in self.plan.nodes:
            if cache_prefix_valid and node.name in completed_nodes:
                cached = self._load_cached(node.name)
                if cached is not None:
                    outputs[node.name] = cached
                    skipped.append(node.name)
                    continue
            cache_prefix_valid = False
            self._node_start(node.name, outputs)
            output = self._execute_node(node.name, outputs)
            outputs[node.name] = output
            self._node_final(node.name, output, outputs)
        report = self._coerce_report(outputs["revise"])
        self.artifacts.write_output(report)
        self.artifacts.write_manifest()
        return ConductorResult(report, tuple(skipped))

    def _execute_node(self, node: str, outputs: dict[str, object]) -> object:
        if node == "research":
            return self.engine.research()
        if node == "debate":
            return self.engine.debate(outputs["research"])
        if node == "draft":
            return self.engine.draft(outputs["research"], outputs["debate"])
        if node == "verify":
            return self.engine.verify(outputs["draft"], outputs["research"])
        if node == "court":
            return self.engine.court(outputs["draft"], outputs["verify"], outputs["debate"])
        if node == "revise":
            return self.engine.revise(outputs["draft"], outputs["verify"], outputs["court"])
        raise ValueError(f"unknown node {node}")

    def _node_start(self, node: str, outputs: dict[str, object]) -> None:
        self.artifacts.append_journal("node_start", {"node": node, "input_digest": self._input_digest(node, outputs), "config_digest": self._config_digest()})
        if self.on_event:
            self.on_event(AgentEvent(kind="progress", message=f"{node} running", raw={"node": node, "state": "running"}))

    def _node_final(self, node: str, output: object, outputs: dict[str, object]) -> None:
        payload = output.model_dump(mode="json") if hasattr(output, "model_dump") else output
        output_digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        event = {
            "node": node,
            "input_digest": self._input_digest(node, outputs),
            "output_digest": output_digest,
            "schema_name": getattr(output, "kind", node),
            "config_digest": self._config_digest(),
        }
        artifact = self._artifact_for_node(node)
        if artifact is not None and artifact.exists():
            event["artifact_path"] = str(artifact.relative_to(self.artifacts.root))
            event["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.artifacts.append_journal("node_final", event)
        if self.on_event:
            self.on_event(AgentEvent(kind="progress", message=f"{node} complete", raw={"node": node, "state": "done"}))

    def _load_cached(self, node: str) -> object | None:
        mapping = {
            "research": ("research.json", ResearchOutput),
            "debate": ("debate.json", DebateOutput),
            "draft": ("draft.initial.json", ReportOutput),
            "verify": ("verify.json", VerifyOutput),
            "court": ("court.json", ReviewerCourtOutput),
            "revise": ("revise.json", ReviseOutput),
        }
        filename, model = mapping[node]
        path = self.artifacts.artifacts / filename
        if not path.exists():
            return None
        return model.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def _coerce_report(self, value: object) -> ReportOutput:
        if isinstance(value, ReviseOutput):
            return value.final_report
        if isinstance(value, ReportOutput):
            return value
        raise TypeError("revise node did not produce a report")

    def _input_digest(self, node: str, outputs: dict[str, object]) -> str:
        raw = json.dumps(
            {
                "node": node,
                "config_digest": self._config_digest(),
                "inputs": {
                    source: self._object_digest(outputs[source])
                    for source, target in self.plan.edges
                    if target == node and source in outputs
                },
            },
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _config_digest(self) -> str:
        raw = json.dumps(self.plan.to_dict(), sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _object_digest(self, value: object) -> str:
        payload = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _artifact_for_node(self, node: str):
        mapping = {
            "research": "research.json",
            "debate": "debate.json",
            "draft": "draft.initial.json",
            "verify": "verify.json",
            "court": "court.json",
            "revise": "revise.json",
        }
        name = mapping.get(node)
        return self.artifacts.artifacts / name if name else None


def result_from_report(report: ReportOutput) -> AgentResult:
    return AgentResult(
        content=report.model_dump(mode="json"),
        claims=report.claims,
        citations=report.citations,
        confidence=0.72,
        cost=CostDelta(usd=0.0),
        runtime_meta=RuntimeMeta(runtime="minimal", model="deterministic-conductor"),
    )
