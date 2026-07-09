from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .effort import EffortProfile

BUILTIN_WORKFLOW_NAMES = ("auto", "review", "evolve", "science")
VALID_MODES = ("auto", "deliberate", "decide", "brief")

# Incomplete gateway stubs and misconfigured providers must not break dry-run cost projection.
# RuntimeError covers ProviderUnavailable and similar gateway failures; keep BaseException subclasses uncaught.
_GATEWAY_COST_ERRORS = (AttributeError, TypeError, KeyError, ValueError, RuntimeError)


@runtime_checkable
class CostEstimateGateway(Protocol):
    def resolve(self, capability: str | None = None, model: str | None = None) -> Any: ...

    def route_targets(self, capability: str) -> list[str]: ...

    def route_availability(self, capability: str) -> list[Any]: ...


@dataclass(frozen=True)
class PlanInput:
    source: str
    schema: str
    required: bool = True


@dataclass(frozen=True)
class PlanNode:
    name: str
    kind: str
    runtime: str
    capability: str
    output_schema: str
    budget_share: float
    estimated_tokens: int
    estimated_cost: float
    detail: str
    max_iterations: int | None = None
    convergence: str | None = None
    input_schemas: tuple[str, ...] = ()
    inputs: tuple[PlanInput, ...] = ()


@dataclass(frozen=True)
class ExecutionPlan:
    question: str
    effort: EffortProfile
    runtime: str
    budget: float
    nodes: tuple[PlanNode, ...]
    edges: tuple[tuple[str, str], ...]
    mode: str = "auto"
    audience: str | None = None
    seed: int | None = None
    workflow: str = "auto"
    reasoning_effort: str = "auto"
    planner: dict[str, Any] | None = None

    @property
    def estimated_cost(self) -> float:
        return round(sum(node.estimated_cost for node in self.nodes), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "mode": self.mode,
            "audience": self.audience,
            "seed": self.seed,
            "workflow": self.workflow,
            "reasoning_effort": self.reasoning_effort,
            "planner": self.planner,
            "effort": self.effort.name,
            "runtime": self.runtime,
            "budget": self.budget,
            "estimated_cost": self.estimated_cost,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [list(edge) for edge in self.edges],
        }


def compile_plan(
    question: str,
    effort: EffortProfile,
    runtime: str,
    budget: float,
    mode: str = "auto",
    audience: str | None = None,
    seed: int | None = None,
    workflow: str = "auto",
    reasoning_effort: str = "auto",
    planner: dict[str, Any] | None = None,
) -> ExecutionPlan:
    mode = validate_mode(mode)
    workflow = validate_workflow(workflow)
    multiplier = {
        "low": 0.35,
        "medium": 0.65,
        "high": 1.0,
        "vhigh": 1.8,
        "max": 3.2,
        "ultra": 5.0,
    }[effort.name]
    cost_basis = estimated_cost_basis(effort, planner)
    node_specs = (
        ("research", "loop:research", "reasoner", "ResearchOutput", (), 0.35, "perspective sweep and source digestion", 6, "questions exhausted"),
        ("debate", "loop:debate", "reasoner", "DebateOutput", (PlanInput("research", "ResearchOutput"),), 0.20, f"{effort.debaters} debaters x {effort.rounds} rounds", effort.rounds, "stance plateau"),
        ("draft", "writer", "long-context", "ReportOutput", (PlanInput("research", "ResearchOutput"), PlanInput("debate", "DebateOutput")), 0.15, f"scale={effort.scale_strategy}", None, None),
        ("verify", "loop:verify", "fast", "VerifyOutput", (PlanInput("draft", "ReportOutput"), PlanInput("research", "ResearchOutput")), 0.15, f"k={effort.skeptics_per_claim} skeptics per claim", 1, "all triaged"),
        ("court", "reviewer_court", "cheap-judge", "ReviewerCourtOutput", (PlanInput("draft", "ReportOutput"), PlanInput("verify", "VerifyOutput"), PlanInput("debate", "DebateOutput")), 0.10, ",".join(effort.court_panels), 1, "opinion fused"),
        ("revise", "loop:reflexion", "reasoner", "ReviseOutput", (PlanInput("draft", "ReportOutput"), PlanInput("verify", "VerifyOutput"), PlanInput("court", "ReviewerCourtOutput")), 0.05, f"{effort.reflexion_iterations} iterations", effort.reflexion_iterations, "score plateau"),
    )
    nodes: list[PlanNode] = []
    for index, (name, kind, capability, schema, inputs, share, detail, max_iterations, convergence) in enumerate(node_specs, start=1):
        est_cost = round(cost_basis * share, 4)
        tokens = int((12_000 + index * 1_500) * multiplier)
        input_schemas = tuple(input_.schema for input_ in inputs)
        nodes.append(PlanNode(name, kind, runtime, capability, schema, share, tokens, est_cost, detail, max_iterations, convergence, input_schemas, inputs))
    edges = (("research", "debate"), ("debate", "draft"), ("draft", "verify"), ("verify", "court"), ("court", "revise"), ("revise", "emit"))
    return ExecutionPlan(question, effort, runtime, budget, tuple(nodes), edges, mode, audience, seed, workflow, reasoning_effort, planner)


def validate_workflow(workflow: str) -> str:
    value = workflow.strip()
    key = value.lower()
    if key in BUILTIN_WORKFLOW_NAMES:
        return key
    path = Path(value).expanduser()
    if path.exists():
        if not path.is_file():
            raise ValueError(f"workflow template {workflow!r} is not a file")
        return value
    valid = ", ".join(BUILTIN_WORKFLOW_NAMES)
    raise ValueError(f"unknown workflow {workflow!r}; expected one of: {valid}, or an existing template path")


def validate_mode(mode: str) -> str:
    value = mode.strip().lower()
    if value in VALID_MODES:
        return value
    valid = ", ".join(VALID_MODES)
    raise ValueError(f"unknown mode {mode!r}; expected one of: {valid}")


def apply_gateway_estimates(plan: ExecutionPlan, gateway: CostEstimateGateway) -> ExecutionPlan:
    nodes = tuple(replace(node, estimated_cost=estimate_node_cost(node, gateway)) for node in plan.nodes)
    return replace(plan, nodes=nodes)


def estimate_plan_cost(plan: ExecutionPlan, gateway: CostEstimateGateway) -> float:
    return round(sum(estimate_node_cost(node, gateway) for node in plan.nodes), 4)


def estimate_node_cost(node: PlanNode, gateway: CostEstimateGateway) -> float:
    target = preferred_route_target(node.capability, gateway)
    if target is None:
        return node.estimated_cost
    try:
        resolved = gateway.resolve(node.capability, target)
    except _GATEWAY_COST_ERRORS:
        # Best-effort cost projection: fall back to planner estimates.
        return node.estimated_cost
    try:
        price_in = float(resolved.price_input_per_1k)
        price_out = float(resolved.price_output_per_1k)
    except (AttributeError, TypeError, ValueError):
        return node.estimated_cost
    tokens_in = max(int(node.estimated_tokens * 0.75), 0)
    tokens_out = max(node.estimated_tokens - tokens_in, 0)
    projected = round(tokens_in / 1000 * price_in + tokens_out / 1000 * price_out, 4)
    return projected if projected > 0 else node.estimated_cost


def preferred_route_target(capability: str, gateway: CostEstimateGateway) -> str | None:
    try:
        targets = gateway.route_targets(capability)
        healths = gateway.route_availability(capability)
    except _GATEWAY_COST_ERRORS:
        # Missing/partial gateway stubs should not break dry-run.
        return None
    for target, health in zip(targets, healths, strict=False):
        if getattr(health, "available", False):
            return target
    return targets[0] if targets else None


def estimated_cost_basis(effort: EffortProfile, planner: dict[str, Any] | None) -> float:
    if not isinstance(planner, dict):
        return effort.default_budget
    suggested = planner.get("suggested_budget")
    # bool is a subclass of int; reject True/False so they never become budgets.
    if isinstance(suggested, (int, float)) and not isinstance(suggested, bool) and suggested > 0:
        return float(suggested)
    return effort.default_budget


# Backward-compatible private aliases for in-repo callers/tests.
_preferred_route_target = preferred_route_target
_estimated_cost_basis = estimated_cost_basis
