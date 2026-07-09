from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from athenaeum.schemas import utc_now

from .models import BudgetExceeded, ResolvedModel


@dataclass
class BudgetToken:
    id: str
    node_id: str
    remaining_usd: float


class BudgetLedger:
    def __init__(self, path: Path, budget_usd: float):
        self.path = path
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.entries: list[dict[str, Any]] = []
        self.degradations: list[str] = []

    @classmethod
    def open(cls, path: Path, budget_usd: float) -> BudgetLedger:
        ledger = cls(path, budget_usd)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            ledger.spent_usd = float(data.get("spent_usd", data.get("cost_usd", 0.0)))
            ledger.entries = list(data.get("entries", []))
            ledger.degradations = list(data.get("degradations", []))
        return ledger

    @property
    def remaining_usd(self) -> float:
        return round(max(self.budget_usd - self.spent_usd, 0.0), 6)

    def mint(self, node_id: str, share: float) -> BudgetToken:
        amount = min(self.budget_usd * share, self.remaining_usd)
        return BudgetToken(str(uuid.uuid4()), node_id, round(amount, 6))

    def reserve(self, token: BudgetToken, projected_usd: float) -> None:
        if projected_usd > token.remaining_usd or projected_usd > self.remaining_usd:
            raise BudgetExceeded(f"projected ${projected_usd:.4f} exceeds remaining budget ${min(token.remaining_usd, self.remaining_usd):.4f}")

    def settle(self, token: BudgetToken, model: ResolvedModel, tokens_in: int, tokens_out: int, usd: float, reason: str = "completion") -> None:
        self.spent_usd = round(self.spent_usd + usd, 6)
        self.entries.append(
            {
                "at": utc_now(),
                "token_id": token.id,
                "node_id": token.node_id,
                "provider": model.provider,
                "model": model.model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "usd": usd,
                "budget_after": self.remaining_usd,
                "reason": reason,
            }
        )
        self.write()

    def degrade(self, message: str) -> None:
        self.degradations.append(message)
        self.write()

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "budget_usd": self.budget_usd,
            "spent_usd": self.spent_usd,
            "remaining_usd": self.remaining_usd,
            "entries": self.entries,
            "by_node": _totals_by(self.entries, "node_id"),
            "by_model": _totals_by_model(self.entries),
            "degradations": self.degradations,
        }
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _totals_by(entries: list[dict[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
    totals: dict[str, dict[str, float | int]] = {}
    for entry in entries:
        name = str(entry.get(key) or "unknown")
        bucket = totals.setdefault(name, {"tokens_in": 0, "tokens_out": 0, "usd": 0.0})
        bucket["tokens_in"] = int(bucket["tokens_in"]) + int(entry.get("tokens_in", 0) or 0)
        bucket["tokens_out"] = int(bucket["tokens_out"]) + int(entry.get("tokens_out", 0) or 0)
        bucket["usd"] = round(float(bucket["usd"]) + float(entry.get("usd", 0.0) or 0.0), 6)
    return totals


def _totals_by_model(entries: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    totals: dict[str, dict[str, float | int]] = {}
    for entry in entries:
        provider = str(entry.get("provider") or "unknown")
        model = str(entry.get("model") or "unknown")
        name = f"{provider}/{model}"
        bucket = totals.setdefault(name, {"tokens_in": 0, "tokens_out": 0, "usd": 0.0})
        bucket["tokens_in"] = int(bucket["tokens_in"]) + int(entry.get("tokens_in", 0) or 0)
        bucket["tokens_out"] = int(bucket["tokens_out"]) + int(entry.get("tokens_out", 0) or 0)
        bucket["usd"] = round(float(bucket["usd"]) + float(entry.get("usd", 0.0) or 0.0), 6)
    return totals
