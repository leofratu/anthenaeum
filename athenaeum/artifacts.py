from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from athenaeum.schemas import ClaimRef, ReportOutput, utc_now


def new_run_id() -> str:
    return uuid.uuid4().hex[:8]


class RunArtifacts:
    def __init__(self, run_id: str, root: Path = Path("runs")):
        self.run_id = run_id
        self.root = root / run_id
        self.artifacts = self.root / "artifacts"
        self.workspace = self.root / "workspace"

    def prepare(self) -> None:
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def append_journal(self, event: str, payload: dict[str, Any] | None = None) -> None:
        self.prepare()
        journal = self.root / "journal.jsonl"
        prev_hash = "0" * 64
        seq = 0
        if journal.exists():
            lines = [line for line in journal.read_text(encoding="utf-8").splitlines() if line]
            if lines:
                last = json.loads(lines[-1])
                prev_hash = str(last.get("event_hash", prev_hash))
                seq = int(last.get("seq", len(lines) - 1)) + 1
        row = {"seq": seq, "at": utc_now(), "event": event, "payload": payload or {}, "prev_hash": prev_hash}
        encoded = json.dumps(row, sort_keys=True)
        row["event_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with journal.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def append_jsonl(self, relative_path: str, row: Any) -> None:
        self.prepare()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_jsonable(row), sort_keys=True) + "\n")

    def write_model(self, relative_path: str, model: BaseModel | dict[str, Any] | list[Any]) -> None:
        self.write_json(self.root / relative_path, _jsonable(model))

    def write_markdown(self, relative_path: str, text: str) -> None:
        self.prepare()
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._index_artifact(path, "markdown")

    def write_plan(self, plan: Any) -> None:
        self.write_json(self.artifacts / "plan.json", _jsonable(plan))

    def write_output(self, output: ReportOutput | dict[str, Any]) -> None:
        data = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
        self.write_json(self.artifacts / "output.json", data)
        claims = [ClaimRef.model_validate(claim) for claim in data.get("claims", [])]
        self.write_claims(claims)

    def write_claims(self, claims: list[ClaimRef]) -> None:
        self.prepare()
        with (self.root / "claims.jsonl").open("w", encoding="utf-8") as handle:
            for claim in claims:
                handle.write(json.dumps(claim.model_dump(mode="json"), sort_keys=True) + "\n")

    def write_ledger(self, runtime: str, budget: float, cost: float = 0.0) -> None:
        path = self.root / "ledger.json"
        existing: dict[str, Any] = {}
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
        entries = list(existing.get("entries", []))
        if cost > 0 and not entries:
            entries.append(
                {
                    "at": utc_now(),
                    "token_id": "runtime-reported",
                    "node_id": "run",
                    "provider": runtime,
                    "model": runtime,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "usd": round(cost, 6),
                    "budget_after": round(max(budget - cost, 0.0), 6),
                    "reason": "runtime_reported_total",
                }
            )
        spent = round(sum(float(entry.get("usd", 0.0) or 0.0) for entry in entries), 6)
        if not entries:
            spent = round(cost, 6)
        self.write_json(
            path,
            {
                "run_id": self.run_id,
                "runtime": runtime,
                "budget_usd": budget,
                "spent_usd": spent,
                "remaining_usd": round(max(budget - spent, 0.0), 6),
                "entries": entries,
                "by_node": _ledger_totals_by(entries, "node_id"),
                "by_model": _ledger_totals_by_model(entries),
                "degradations": list(existing.get("degradations", [])),
            },
        )

    def write_json(self, path: Path, data: Any) -> None:
        self.prepare()
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        self._index_artifact(path, "json")

    def write_manifest(self) -> None:
        self.prepare()
        index_path = self.artifacts / "index.jsonl"
        refs = []
        if index_path.exists():
            refs = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line]
        seen = {ref.get("path") for ref in refs}
        for path in sorted(self.artifacts.rglob("*")):
            if not path.is_file() or path.name == "index.jsonl":
                continue
            relative = str(path.relative_to(self.root))
            if relative in seen:
                continue
            kind = "jsonl" if path.suffix == ".jsonl" else "json" if path.suffix == ".json" else "markdown" if path.suffix == ".md" else "text"
            refs.append({"path": relative, "kind": kind, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "indexed_at": utc_now()})
        manifest = {"run_id": self.run_id, "generated_at": utc_now(), "artifacts": refs}
        (self.root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    def _index_artifact(self, path: Path, kind: str) -> None:
        self.prepare()
        if not path.exists() or path.name in {"index.jsonl"}:
            return
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            relative = path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row = {"path": str(relative), "kind": kind, "sha256": digest, "indexed_at": utc_now()}
        with (self.artifacts / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _ledger_totals_by(entries: list[dict[str, Any]], key: str) -> dict[str, dict[str, float | int]]:
    totals: dict[str, dict[str, float | int]] = {}
    for entry in entries:
        name = str(entry.get(key) or "unknown")
        bucket = totals.setdefault(name, {"tokens_in": 0, "tokens_out": 0, "usd": 0.0})
        bucket["tokens_in"] = int(bucket["tokens_in"]) + int(entry.get("tokens_in", 0) or 0)
        bucket["tokens_out"] = int(bucket["tokens_out"]) + int(entry.get("tokens_out", 0) or 0)
        bucket["usd"] = round(float(bucket["usd"]) + float(entry.get("usd", 0.0) or 0.0), 6)
    return totals


def _ledger_totals_by_model(entries: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
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
