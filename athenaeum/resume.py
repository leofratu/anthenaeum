from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ResumeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResumeState:
    run_id: str
    complete: bool
    events: int
    completed_nodes: tuple[str, ...]
    artifacts: tuple[str, ...]
    spent_usd: float
    next_action: str


DEFAULT_NODE_ORDER = ("research", "debate", "draft", "verify", "court", "revise")


def replay_run(run_id: str, runs_root: Path = Path("runs")) -> ResumeState:
    run_dir = runs_root / run_id
    journal = run_dir / "journal.jsonl"
    if not journal.exists():
        raise ResumeError(f"run {run_id!r} has no journal")
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines() if line]
    _verify_hash_chain(rows)
    _verify_artifacts(run_dir, rows)
    complete = any(row.get("event") == "run_complete" for row in rows)
    completed_nodes = _trusted_completed_nodes(run_dir, rows, _stored_plan_digest(run_dir))
    artifacts = tuple(str(path.relative_to(run_dir)) for path in sorted((run_dir / "artifacts").rglob("*")) if path.is_file()) if (run_dir / "artifacts").exists() else ()
    ledger_path = run_dir / "ledger.json"
    spent = 0.0
    if ledger_path.exists():
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        spent = float(data.get("spent_usd", data.get("cost_usd", 0.0)))
    next_action = "complete" if complete else "resume from first incomplete node"
    return ResumeState(run_id, complete, len(rows), completed_nodes, artifacts, spent, next_action)


def _verify_hash_chain(rows: list[dict[str, Any]]) -> None:
    prev = "0" * 64
    for expected_seq, row in enumerate(rows):
        event_hash = row.get("event_hash")
        payload = dict(row)
        payload.pop("event_hash", None)
        encoded = json.dumps(payload, sort_keys=True)
        actual = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        if row.get("seq") != expected_seq:
            raise ResumeError(f"journal sequence mismatch at {expected_seq}")
        if row.get("prev_hash") != prev:
            raise ResumeError(f"journal prev_hash mismatch at seq {expected_seq}")
        if event_hash != actual:
            raise ResumeError(f"journal hash mismatch at seq {expected_seq}")
        prev = str(event_hash)


def _verify_artifacts(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row.get("event") != "node_final":
            continue
        payload = row.get("payload", {})
        relative = payload.get("artifact_path")
        expected = payload.get("artifact_sha256")
        if not relative or not expected:
            continue
        path = run_dir / str(relative)
        if not path.exists():
            raise ResumeError(f"artifact missing for node {payload.get('node')}: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ResumeError(f"artifact hash mismatch for node {payload.get('node')}: {relative}")


def _trusted_completed_nodes(run_dir: Path, rows: list[dict[str, Any]], expected_config_digest: str | None = None) -> tuple[str, ...]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("event") != "node_final":
            continue
        payload = row.get("payload", {})
        node = payload.get("node")
        if isinstance(node, str):
            latest[node] = payload
    trusted = {node for node, payload in latest.items() if _node_final_trusted(run_dir, payload, expected_config_digest)}
    if any(node in latest for node in DEFAULT_NODE_ORDER):
        prefix: list[str] = []
        for node in DEFAULT_NODE_ORDER:
            if node not in latest or node not in trusted:
                break
            prefix.append(node)
        return tuple(prefix)
    return tuple(node for node in latest if node in trusted)


def _node_final_trusted(run_dir: Path, payload: dict[str, Any], expected_config_digest: str | None = None) -> bool:
    required = ("input_digest", "config_digest", "output_digest", "artifact_path", "artifact_sha256")
    if any(not payload.get(key) for key in required):
        return False
    if expected_config_digest is not None and payload.get("config_digest") != expected_config_digest:
        return False
    path = run_dir / str(payload["artifact_path"])
    if not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == payload["artifact_sha256"]


def _stored_plan_digest(run_dir: Path) -> str | None:
    plan_path = run_dir / "artifacts" / "plan.json"
    if not plan_path.exists():
        return None
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
