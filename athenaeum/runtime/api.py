from __future__ import annotations

from collections.abc import AsyncIterator

from athenaeum.gateway import ModelGateway
from athenaeum.gateway.models import CompletionRequest
from athenaeum.schemas import ReportOutput

from .models import AgentEvent, AgentResult, AgentTask, CostDelta, RuntimeHealth, RuntimeMeta, Workspace


class ApiRuntime:
    name = "api"

    def __init__(self, gateway: ModelGateway | None = None):
        self.gateway = gateway or ModelGateway.from_config()
        self.definition = type("Definition", (), {"binary": "api", "args": ("gateway",)})()

    def health(self) -> RuntimeHealth:
        providers = self.gateway.probe()
        available = any(provider.available and provider.name != "stub" for provider in providers)
        detail = ", ".join(f"{provider.name}:{'ok' if provider.available else 'missing'}" for provider in providers)
        return RuntimeHealth(name=self.name, binary="in-process", available=available, version="gateway", auth_ok=available, detail=detail)

    async def spawn(self, task: AgentTask, workspace: Workspace) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(kind="progress", message="api gateway dispatch", raw={"node": "draft", "state": "running"})
        token = self.gateway.ledger.mint(str(task.input_payload.get("node_id") or "api"), 1.0) if self.gateway.ledger else None
        before = self.gateway.ledger.spent_usd if self.gateway.ledger else 0.0
        result_model = await self.gateway.complete_json(
            req=CompletionRequest(
                messages=[{"role": "user", "content": task.prompt}],
                capability=task.capability,
                model=task.model,
                max_tokens=task.max_turns * 256,
                reasoning_effort=task.reasoning_effort,
            ),
            schema=ReportOutput,
            token=token,
        )
        after = self.gateway.ledger.spent_usd if self.gateway.ledger else 0.0
        yield AgentEvent(
            kind="final",
            result=AgentResult(
                content=result_model.model_dump(mode="json"),
                claims=result_model.claims,
                citations=result_model.citations,
                confidence=0.5,
                cost=CostDelta(usd=round(after - before, 6)),
                runtime_meta=RuntimeMeta(runtime=self.name, model="gateway"),
            ),
        )
