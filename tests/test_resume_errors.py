from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from athenaeum.artifacts import RunArtifacts
from athenaeum.resume import ResumeError, replay_run


def test_resume_missing_journal_raises(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    (runs / "ghost").mkdir(parents=True)

    with pytest.raises(ResumeError, match="has no journal"):
        replay_run("ghost", runs)


def test_resume_missing_run_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(ResumeError, match="has no journal"):
        replay_run("missing", tmp_path / "runs")


def test_resume_rejects_sequence_mismatch(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run1", tmp_path / "runs")
    artifacts.append_journal("run_start", {"question": "q"})
    journal = artifacts.root / "journal.jsonl"
    row = json.loads(journal.read_text(encoding="utf-8"))
    row["seq"] = 3
    payload = dict(row)
    payload.pop("event_hash", None)
    row["event_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    journal.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ResumeError, match="sequence mismatch"):
        replay_run("run1", tmp_path / "runs")


def test_resume_rejects_prev_hash_mismatch(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run2", tmp_path / "runs")
    artifacts.append_journal("run_start", {"question": "q"})
    artifacts.append_journal("node_final", {"node": "research"})
    journal = artifacts.root / "journal.jsonl"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    rows[1]["prev_hash"] = "f" * 64
    payload = dict(rows[1])
    payload.pop("event_hash", None)
    rows[1]["event_hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    journal.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    with pytest.raises(ResumeError, match="prev_hash mismatch"):
        replay_run("run2", tmp_path / "runs")


def test_resume_rejects_missing_node_artifact(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run3", tmp_path / "runs")
    artifacts.append_journal(
        "node_final",
        {
            "node": "research",
            "artifact_path": "artifacts/research.json",
            "artifact_sha256": "a" * 64,
        },
    )

    with pytest.raises(ResumeError, match="artifact missing"):
        replay_run("run3", tmp_path / "runs")


def test_resume_incomplete_run_reports_next_action(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run4", tmp_path / "runs")
    artifacts.append_journal("run_start", {"question": "q"})
    artifacts.write_ledger("minimal", 1.0, 0.25)

    state = replay_run("run4", tmp_path / "runs")

    assert state.complete is False
    assert state.events == 1
    assert state.spent_usd == 0.25
    assert state.next_action == "resume from first incomplete node"
    assert state.completed_nodes == ()
