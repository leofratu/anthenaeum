from __future__ import annotations

import json
from pathlib import Path

from athenaeum.artifacts import RunArtifacts, new_run_id
from athenaeum.schemas import ClaimRef, ReportOutput


def test_new_run_id_is_short_hex() -> None:
    run_id = new_run_id()
    assert len(run_id) == 8
    int(run_id, 16)


def test_append_journal_chains_hashes_and_sequences(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run1", tmp_path / "runs")
    artifacts.append_journal("run_start", {"question": "q"})
    artifacts.append_journal("node_final", {"node": "research"})

    journal = tmp_path / "runs" / "run1" / "journal.jsonl"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["seq"] == 0
    assert rows[1]["seq"] == 1
    assert rows[0]["prev_hash"] == "0" * 64
    assert rows[1]["prev_hash"] == rows[0]["event_hash"]
    assert rows[0]["event"] == "run_start"
    assert rows[1]["payload"]["node"] == "research"
    assert (tmp_path / "runs" / "run1" / "artifacts").is_dir()
    assert (tmp_path / "runs" / "run1" / "workspace").is_dir()


def test_write_manifest_indexes_artifacts(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run2", tmp_path / "runs")
    artifacts.write_plan({"question": "q", "budget": 1.0})
    artifacts.write_markdown("artifacts/notes.md", "# notes\n")
    artifacts.append_jsonl("artifacts/events.jsonl", {"kind": "event", "n": 1})
    artifacts.write_manifest()

    manifest = json.loads((artifacts.root / "manifest.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in manifest["artifacts"]}
    assert manifest["run_id"] == "run2"
    assert "artifacts/plan.json" in paths
    assert "artifacts/notes.md" in paths
    assert "artifacts/events.jsonl" in paths
    kinds = {item["path"]: item["kind"] for item in manifest["artifacts"]}
    assert kinds["artifacts/plan.json"] == "json"
    assert kinds["artifacts/notes.md"] == "markdown"
    assert kinds["artifacts/events.jsonl"] == "jsonl"
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])


def test_write_output_writes_claims_jsonl(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run3", tmp_path / "runs")
    output = ReportOutput(
        title="Ship?",
        question="Should we ship?",
        summary="Maybe.",
        report_markdown="# Ship?\n\nMaybe.\n",
        claims=[ClaimRef(id="c1", text="claim one", status="unverified")],
    )
    artifacts.write_output(output)

    data = json.loads((artifacts.artifacts / "output.json").read_text(encoding="utf-8"))
    assert data["title"] == "Ship?"
    claims_path = artifacts.root / "claims.jsonl"
    claims = [json.loads(line) for line in claims_path.read_text(encoding="utf-8").splitlines()]
    assert claims == [{"id": "c1", "text": "claim one", "status": "unverified", "citation_ids": [], "confidence": 0.0}]


def test_write_ledger_creates_runtime_reported_entry_when_empty(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run4", tmp_path / "runs")
    artifacts.write_ledger("minimal", budget=2.0, cost=0.75)

    data = json.loads((artifacts.root / "ledger.json").read_text(encoding="utf-8"))
    assert data["spent_usd"] == 0.75
    assert data["remaining_usd"] == 1.25
    assert data["runtime"] == "minimal"
    assert len(data["entries"]) == 1
    assert data["entries"][0]["usd"] == 0.75
    assert data["by_node"]["run"]["usd"] == 0.75
