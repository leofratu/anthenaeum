from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from athenaeum.gateway import ModelGateway
from athenaeum.runtime.models import RuntimeHealth
from athenaeum.schemas import OUTPUT_MODELS
from athenaeum.workflow import ExecutionPlan, estimate_plan_cost


@dataclass(frozen=True)
class SanityFinding:
    rule: str
    severity: str
    message: str


@dataclass
class SanityReport:
    findings: list[SanityFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[SanityFinding]:
        return [finding for finding in self.findings if finding.severity == "error"]

    @property
    def warnings(self) -> list[SanityFinding]:
        return [finding for finding in self.findings if finding.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, rule: str, severity: str, message: str) -> None:
        self.findings.append(SanityFinding(rule, severity, message))

    def summary(self) -> str:
        if self.ok:
            return "S1-S9 passed" if not self.warnings else f"S1-S9 passed · {len(self.warnings)} warnings"
        return f"{len(self.errors)} sanity errors"


class SanityChecker:
    def __init__(self, gateway: ModelGateway | None = None):
        self.gateway = gateway or ModelGateway.from_config()

    def check(self, plan: ExecutionPlan, runtime_health: RuntimeHealth | None = None, science_sandbox: Path | None = None) -> SanityReport:
        report = SanityReport()
        self._check_dag(plan, report)
        self._check_capabilities(plan, report)
        self._check_runtime(runtime_health, report)
        self._check_schema_assignability(plan, report)
        self._check_budget(plan, report)
        self._check_judge_generator_separation(plan, report)
        self._check_loops(plan, report)
        self._check_diversity(plan, report)
        if plan.workflow == "science" or science_sandbox is not None:
            self._check_science_sandbox(science_sandbox, report)
        return report

    def _check_dag(self, plan: ExecutionPlan, report: SanityReport) -> None:
        node_names = {node.name for node in plan.nodes} | {"emit"}
        if len(node_names) != len({node.name for node in plan.nodes}) + 1:
            report.add("S1", "error", "duplicate node id in workflow")
        for source, target in plan.edges:
            if source not in node_names or target not in node_names:
                report.add("S1", "error", f"edge {source}->{target} references an unknown node")
        graph = {node: [] for node in node_names}
        for source, target in plan.edges:
            if source in graph and target in graph:
                graph[source].append(target)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                report.add("S1", "error", f"cycle detected at {node}")
                return
            if node in visited:
                return
            visiting.add(node)
            for child in graph.get(node, []):
                visit(child)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def _check_runtime(self, health: RuntimeHealth | None, report: SanityReport) -> None:
        if health is not None and not health.available:
            report.add("S3", "warning", health.fix or f"runtime {health.name} unavailable; use --runtime minimal")

    def _check_capabilities(self, plan: ExecutionPlan, report: SanityReport) -> None:
        checked: set[str] = set()
        for node in plan.nodes:
            capability = node.capability
            if capability in checked:
                continue
            checked.add(capability)
            healths = self.gateway.route_availability(capability)
            if not healths:
                report.add("S2", "error", f"capability {capability!r} has no configured route")
                continue
            available = [health for health in healths if health.available]
            if available and not (plan.runtime == "api" and all(health.name == "stub" for health in available)):
                continue
            details = "; ".join(f"{health.name}: {health.detail or 'unavailable'}" for health in healths)
            report.add("S2", "error", f"capability {capability!r} has no available provider ({details})")

    def _check_schema_assignability(self, plan: ExecutionPlan, report: SanityReport) -> None:
        nodes = {node.name: node for node in plan.nodes}
        for node in plan.nodes:
            if _canonical_schema(node.output_schema) is None:
                report.add("S4", "error", f"node {node.name} declares unknown output schema {node.output_schema!r}")
        for node in plan.nodes:
            if node.inputs:
                for input_ in node.inputs:
                    source = nodes.get(input_.source)
                    expected = _canonical_schema(input_.schema)
                    if expected is None:
                        report.add("S4", "error", f"node {node.name} declares unknown input schema {input_.schema!r} from {input_.source}")
                        continue
                    if source is None:
                        if input_.required:
                            report.add("S4", "error", f"node {node.name} missing required input source {input_.source!r}")
                        continue
                    actual = _canonical_schema(source.output_schema)
                    if actual != expected:
                        report.add("S4", "error", f"input {input_.source}->{node.name} passes {source.output_schema}, expected {input_.schema}")
                continue
            if not node.input_schemas and any(target == node.name for _, target in plan.edges):
                report.add("S4", "error", f"node {node.name} declares no input schema")
        for source_name, target_name in plan.edges:
            if target_name == "emit":
                continue
            source = nodes.get(source_name)
            target = nodes.get(target_name)
            if source is None or target is None:
                continue
            if target.inputs:
                continue
            if not target.input_schemas:
                report.add("S4", "error", f"node {target.name} declares no input schema for edge {source.name}->{target.name}")
                continue
            actual = _canonical_schema(source.output_schema)
            expected = tuple(_canonical_schema(schema) for schema in target.input_schemas)
            if any(schema is None for schema in expected):
                report.add("S4", "error", f"node {target.name} declares unknown input schema in {target.input_schemas}")
                continue
            if actual not in expected:
                expected = ", ".join(target.input_schemas)
                report.add("S4", "error", f"edge {source.name}->{target.name} passes {source.output_schema}, expected one of: {expected}")

    def _check_budget(self, plan: ExecutionPlan, report: SanityReport) -> None:
        if plan.budget <= 0:
            report.add("S5", "error", f"budget must be positive, got ${plan.budget:.2f}")
            return
        estimated_cost = estimate_plan_cost(plan, self.gateway)
        if estimated_cost > plan.budget:
            report.add("S5", "error", f"estimated ${estimated_cost:.2f} exceeds budget ${plan.budget:.2f}")
        for capability, target in _unpriced_non_stub_routes(plan, self.gateway):
            report.add("S5", "warning", f"capability {capability!r} route {target!r} has no configured prices; using fallback estimate")

    def _check_judge_generator_separation(self, plan: ExecutionPlan, report: SanityReport) -> None:
        if isinstance(plan.planner, dict) and plan.planner.get("allow_self_judge") is True:
            return
        generators = {node.capability for node in plan.nodes if node.name in {"draft", "revise"}}
        judges = {node.capability for node in plan.nodes if node.name in {"court", "verify"}}
        generator_targets = {_first_available_target(capability, self.gateway) for capability in generators}
        judge_targets = {_first_available_target(capability, self.gateway) for capability in judges}
        generator_targets.discard(None)
        judge_targets.discard(None)
        overlap = sorted(generator_targets & judge_targets)
        if overlap:
            report.add("S6", "error", f"judge/generator model separation violated: {', '.join(overlap)}")

    def _check_loops(self, plan: ExecutionPlan, report: SanityReport) -> None:
        for node in plan.nodes:
            if node.kind.startswith("loop:") and (node.max_iterations is None or not node.convergence):
                report.add("S7", "error", f"loop node {node.name} lacks max_iterations or convergence")

    def _check_diversity(self, plan: ExecutionPlan, report: SanityReport) -> None:
        providers = {
            health.name
            for health in self.gateway.probe()
            if health.available and self.gateway.providers.get(health.name) and self.gateway.providers[health.name].kind != "stub"
        }
        if plan.effort.name in {"vhigh", "max", "ultra"} and len(providers) < 2:
            report.add("S9", "error", f"effort {plan.effort.name} requires at least 2 available non-stub providers")
        elif len(providers) < 2:
            detail = "no available non-stub providers" if not providers else "only one available non-stub provider"
            report.add("S9", "warning", f"provider diversity degraded; {detail}")

    def _check_science_sandbox(self, sandbox: Path | None, report: SanityReport) -> None:
        if sandbox is None:
            report.add("S8", "error", "science mode requires --sandbox")
            return
        if sandbox.exists() and not sandbox.is_dir():
            report.add("S8", "error", f"sandbox {sandbox} is not a directory")


def _first_available_target(capability: str, gateway: ModelGateway) -> str | None:
    for target, health in zip(gateway.route_targets(capability), gateway.route_availability(capability), strict=False):
        if health.available:
            return target
    return None


def _unpriced_non_stub_routes(plan: ExecutionPlan, gateway: ModelGateway) -> list[tuple[str, str]]:
    unpriced: list[tuple[str, str]] = []
    seen: set[str] = set()
    for node in plan.nodes:
        capability = node.capability
        if capability in seen:
            continue
        seen.add(capability)
        target = _first_available_target(capability, gateway)
        if target is None:
            continue
        provider_name, _, model_name = target.partition("/")
        provider = gateway.providers.get(provider_name)
        if provider is None or provider.kind == "stub":
            continue
        prices = provider.prices.get(model_name) or provider.prices.get("*")
        if not prices:
            unpriced.append((capability, target))
    return unpriced


_SCHEMA_ALIASES = {
    **{key: model.__name__ for key, model in OUTPUT_MODELS.items()},
    **{model.__name__: model.__name__ for model in OUTPUT_MODELS.values()},
}


def _canonical_schema(name: str) -> str | None:
    return _SCHEMA_ALIASES.get(name) or _SCHEMA_ALIASES.get(name.lower())
