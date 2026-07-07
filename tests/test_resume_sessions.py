from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from athenaeum.artifacts import RunArtifacts
from athenaeum.conductor import LocalConductor
from athenaeum.effort import get_effort
from athenaeum.loops.context import RunContext
from athenaeum.resume import ResumeError, replay_run
from athenaeum.schemas import CitationRef, ClaimRef, SessionRecord
from athenaeum.store import CitationDB, ClaimLedger, SessionStore
from athenaeum.workflow import compile_plan


def test_resume_replays_complete_hash_chained_run(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    artifacts.append_journal("run_start", {"question": "q"})
    artifacts.append_journal("run_complete", {"out": "report.md"})
    artifacts.write_ledger("minimal", 1.0, 0.0)

    state = replay_run("run123", tmp_path / "runs")

    assert state.complete is True
    assert state.events == 2


def test_write_ledger_preserves_existing_entries_and_totals(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    artifacts.write_json(
        artifacts.root / "ledger.json",
        {
            "budget_usd": 1.0,
            "spent_usd": 0.2,
            "remaining_usd": 0.8,
            "entries": [
                {
                    "token_id": "t1",
                    "node_id": "draft",
                    "provider": "openai",
                    "model": "gpt-test",
                    "tokens_in": 10,
                    "tokens_out": 5,
                    "usd": 0.2,
                    "reason": "completion",
                }
            ],
            "degradations": ["fallback"],
        },
    )

    artifacts.write_ledger("api", 1.0, 0.2)

    data = json.loads((artifacts.root / "ledger.json").read_text(encoding="utf-8"))
    assert len(data["entries"]) == 1
    assert data["spent_usd"] == 0.2
    assert data["by_node"]["draft"] == {"tokens_in": 10, "tokens_out": 5, "usd": 0.2}
    assert data["by_model"]["openai/gpt-test"] == {"tokens_in": 10, "tokens_out": 5, "usd": 0.2}
    assert data["degradations"] == ["fallback"]


def test_resume_rejects_corrupt_hash_chain(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    artifacts.append_journal("run_start", {"question": "q"})
    journal = tmp_path / "runs" / "run123" / "journal.jsonl"
    row = json.loads(journal.read_text(encoding="utf-8"))
    row["payload"]["question"] = "tampered"
    journal.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ResumeError):
        replay_run("run123", tmp_path / "runs")


def test_resume_trusts_only_node_finals_with_artifact_metadata(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    artifact_path = artifacts.artifacts / "research.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text('{"kind":"research"}', encoding="utf-8")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    artifacts.append_journal(
        "node_final",
        {
            "node": "research",
            "input_digest": "input",
            "config_digest": "config",
            "output_digest": "output",
            "schema_name": "research",
            "artifact_path": "artifacts/research.json",
            "artifact_sha256": digest,
        },
    )
    artifacts.append_journal("node_final", {"node": "draft", "output_digest": "legacy"})

    state = replay_run("run123", tmp_path / "runs")

    assert state.completed_nodes == ("research",)


def test_resume_invalidates_suffix_after_untrusted_middle_node(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    _append_trusted_node_final(artifacts, "research")
    artifacts.append_journal("node_final", {"node": "debate", "output_digest": "legacy"})
    _append_trusted_node_final(artifacts, "draft")

    state = replay_run("run123", tmp_path / "runs")

    assert state.completed_nodes == ("research",)


def test_resume_invalidates_suffix_after_config_digest_mismatch(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    plan = {"question": "q", "budget": 1.0}
    artifacts.write_plan(plan)
    current_digest = _digest(plan)
    _append_trusted_node_final(artifacts, "research", config_digest=current_digest)
    _append_trusted_node_final(artifacts, "debate", config_digest="stale")
    _append_trusted_node_final(artifacts, "draft", config_digest=current_digest)

    state = replay_run("run123", tmp_path / "runs")

    assert state.completed_nodes == ("research",)


