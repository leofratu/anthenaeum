from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from athenaeum.schemas import CitationRef, ClaimRef


class RuntimeUnavailable(RuntimeError):
    """Raised when a selected runtime cannot be executed."""


class RuntimeExecutionError(RuntimeError):
    """Raised when an external runtime exits unsuccessfully."""


class SchemaValidationError(RuntimeError):
    """Raised when a runtime result does not satisfy the requested schema."""


@dataclass(frozen=True)
class Workspace:
    root: Path


class CostDelta(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0


class RuntimeMeta(BaseModel):
    runtime: str
    model: str | None = None
    command: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    exit_code: int | None = None


class AgentResult(BaseModel):
    content: Any
    claims: list[ClaimRef] = Field(default_factory=list)
    citations: list[CitationRef] = Field(default_factory=list)
    confidence: float = 0.0
    cost: CostDelta = Field(default_factory=CostDelta)
    runtime_meta: RuntimeMeta

    @classmethod
    def from_payload(cls, payload: Any, runtime: str, model: str | None = None) -> "AgentResult":
        if isinstance(payload, dict) and "content" in payload:
            data = dict(payload)
            data.setdefault("runtime_meta", {"runtime": runtime, "model": model})
            return cls.model_validate(data)
        if isinstance(payload, dict):
            return cls(
                content=payload,
                claims=[ClaimRef.model_validate(claim) for claim in payload.get("claims", [])],
                citations=[CitationRef.model_validate(citation) for citation in payload.get("citations", [])],
                runtime_meta=RuntimeMeta(runtime=runtime, model=model),
            )
        return cls(content=payload, runtime_meta=RuntimeMeta(runtime=runtime, model=model))


class AgentEvent(BaseModel):
    kind: Literal["progress", "tool_call", "cost_delta", "final"]
    message: str | None = None
    result: AgentResult | None = None
    cost: CostDelta | None = None
    raw: dict[str, Any] | None = None


class AgentTask(BaseModel):
    prompt: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    tool_policy: str = "workspace"
    budget_usd: float = 0.0
    deadline_seconds: int = 600
    max_turns: int = 8
    model: str | None = None
    capability: str = "reasoner"
    reasoning_effort: str | None = "auto"


class RuntimeHealth(BaseModel):
    name: str
    binary: str
    available: bool
    version: str | None = None
    auth_ok: bool | None = None
    detail: str | None = None
    fix: str | None = None


def validate_json_schema_subset(content: Any, schema: dict[str, Any]) -> None:
    """Validate the small JSON Schema subset used by runtime smoke tasks."""
    if not schema:
        return
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(content, dict):
            raise SchemaValidationError("expected result content to be an object")
        for key in schema.get("required", []):
            if key not in content:
                raise SchemaValidationError(f"missing required result field: {key}")
        properties = schema.get("properties", {})
        for key, value_schema in properties.items():
            if key in content:
                _validate_type(key, content[key], value_schema.get("type"))
    elif expected_type:
        _validate_type("content", content, expected_type)


def _validate_type(key: str, value: Any, expected_type: str | None) -> None:
    if expected_type is None:
        return
    checks = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    check = checks.get(expected_type)
    if check is not None and not isinstance(value, check):
        raise SchemaValidationError(f"field {key!r} expected {expected_type}")
