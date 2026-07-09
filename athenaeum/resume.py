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
_NODE_FINAL_REQUIRED = ("input_digest", "config_digest", "output_digest", "artifact_path", "artifact_sha256")


def replay_run(run_id: str, runs_root: Path = Path("runs")) -> ResumeState:
    run_dir = runs_root / run_id
    journal = run_dir / "journal.jsonl"
    if not journal.exists():
        raise ResumeError(f"run {run_id!r} has no journal")
    rows = load_journal_rows(journal)
    verify_hash_chain(rows)
    verify_artifacts(run_dir, rows)
    complete = any(row.get("event") == "run_complete" for row in rows)
    completed_nodes = trusted_completed_nodes(run_dir, rows, stored_plan_digest(run_dir))
    artifacts_dir = run_dir / "artifacts"
    artifacts = (
        tuple(str(path.relative_to(run_dir)) for path in sorted(artifacts_dir.rglob("*")) if path.is_file())
        if artifacts_dir.exists()
        else ()
    )
    spent = read_spent_usd(run_dir / "ledger.json")
    next_action = "complete" if complete else "resume from first incomplete node"
    return ResumeState(run_id, complete, len(rows), completed_nodes, artifacts, spent, next_action)


def load_journal_rows(journal: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(journal.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ResumeError(f"journal JSON decode error at line {line_no}") from exc
        if not isinstance(row, dict):
            raise ResumeError(f"journal row at line {line_no} is not an object")
        rows.append(row)
    return rows


def read_spent_usd(ledger_path: Path) -> float:
    if not ledger_path.exists():
        return 0.0
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResumeError(f"ledger JSON decode error: {ledger_path}") from exc
    if not isinstance(data, dict):
        return 0.0
    raw = data.get("spent_usd", data.get("cost_usd", 0.0))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def verify_hash_chain(rows: list[dict[str, Any]]) -> None:
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


def verify_artifacts(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row.get("event") != "node_final":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
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


def trusted_completed_nodes(
    run_dir: Path, rows: list[dict[str, Any]], expected_config_digest: str | None = None
) -> tuple[str, ...]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("event") != "node_final":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        node = payload.get("node")
        if isinstance(node, str):
            latest[node] = payload
    trusted = {
        node for node, payload in latest.items() if node_final_trusted(run_dir, payload, expected_config_digest)
    }
    if any(node in latest for node in DEFAULT_NODE_ORDER):
        prefix: list[str] = []
        for node in DEFAULT_NODE_ORDER:
            if node not in latest or node not in trusted:
                break
            prefix.append(node)
        return tuple(prefix)
    return tuple(node for node in latest if node in trusted)


def node_final_trusted(
    run_dir: Path, payload: dict[str, Any], expected_config_digest: str | None = None
) -> bool:
    if any(not payload.get(key) for key in _NODE_FINAL_REQUIRED):
        return False
    if expected_config_digest is not None and payload.get("config_digest") != expected_config_digest:
        return False
    path = run_dir / str(payload["artifact_path"])
    if not path.exists():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == payload["artifact_sha256"]


def stored_plan_digest(run_dir: Path) -> str | None:
    plan_path = run_dir / "artifacts" / "plan.json"
    if not plan_path.exists():
        return None
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResumeError(f"plan JSON decode error: {plan_path}") from exc
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()


# Private aliases preserve prior internal import paths.
_verify_hash_chain = verify_hash_chain
_verify_artifacts = verify_artifacts
_trusted_completed_nodes = trusted_completed_nodes
_node_final_trusted = node_final_trusted
_stored_plan_digest = stored_plan_digest
