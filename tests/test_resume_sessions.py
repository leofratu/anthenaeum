from __future__ import annotations

import hashlib
import json
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


def test_resume_invalidates_when_plan_json_changes_after_node_final(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    original_plan = {"question": "q", "budget": 1.0}
    artifacts.write_plan(original_plan)
    original_digest = _digest(original_plan)
    for node in ("research", "debate", "draft"):
        _append_trusted_node_final(artifacts, node, config_digest=original_digest)
    artifacts.write_plan({"question": "q", "budget": 2.0})

    state = replay_run("run123", tmp_path / "runs")

    assert state.completed_nodes == ()


def test_conductor_does_not_skip_downstream_after_recomputed_predecessor(tmp_path: Path) -> None:
    artifacts = RunArtifacts("run123", tmp_path / "runs")
    effort = get_effort("low")
    plan = compile_plan("Should we ship?", effort, "minimal", effort.default_budget)
    context = RunContext(plan.question, "run123", effort.name, plan.mode, plan.audience, 0, artifacts.artifacts)
    LocalConductor(plan, artifacts, context).run()
    (artifacts.artifacts / "debate.json").unlink()

    result = LocalConductor(plan, artifacts, context).run(completed_nodes={"research", "debate", "draft", "verify", "court", "revise"})

    assert result.skipped_nodes == ("research",)


def test_resume_rejects_cached_artifact_hash_mismatch(tmp_path: Path) -> None:
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
    artifact_path.write_text('{"kind":"research","changed":true}', encoding="utf-8")

    with pytest.raises(ResumeError, match="artifact hash mismatch"):
        replay_run("run123", tmp_path / "runs")


def test_session_store_create_poke_and_consume(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    store.create(SessionRecord(id="s1", question="q", daily_budget=1.0, duration="1d"))

    assert store.get("s1") is not None
    wakes = store.due_wakes()
    assert len(wakes) == 1
    store.consume_wake(wakes[0]["id"])
    assert store.due_wakes() == []


def test_session_store_due_wakes_ignore_paused_and_stopped_sessions(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    store.create(SessionRecord(id="running", question="q1", daily_budget=1.0, duration="1d"))
    store.create(SessionRecord(id="paused", question="q2", daily_budget=1.0, duration="1d"))
    store.create(SessionRecord(id="stopped", question="q3", daily_budget=1.0, duration="1d"))
    store.set_status("paused", "paused")
    store.set_status("stopped", "stopped")

    wakes = store.due_wakes()

    assert {wake["session_id"] for wake in wakes} == {"running"}


def test_session_store_resume_makes_queued_wake_due_again(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    store.create(SessionRecord(id="s1", question="q", daily_budget=1.0, duration="1d"))
    store.set_status("s1", "paused")

    assert store.due_wakes() == []

    store.set_status("s1", "running")

    assert [wake["session_id"] for wake in store.due_wakes()] == ["s1"]


def test_citation_db_dedupes_normalized_urls(tmp_path: Path) -> None:
    db = CitationDB(tmp_path / "citations.sqlite3")
    db.upsert_citation(CitationRef(id="a", title="Example", url="HTTPS://EXAMPLE.COM/path/"))
    db.upsert_citation(CitationRef(id="b", title="Example 2", url="https://example.com/path"))

    assert len(db.list_sources()) == 1


def test_claim_ledger_versions_and_materializes_latest(tmp_path: Path) -> None:
    ledger = ClaimLedger(tmp_path / "claims.jsonl")
    ledger.append(ClaimRef(id="c1", text="claim", status="unverified"), "draft")
    ledger.append(ClaimRef(id="c1", text="claim", status="verified"), "verify")

    latest = ledger.materialize()
    assert latest["c1"]["version"] == 2
    assert latest["c1"]["claim"]["status"] == "verified"


def _append_trusted_node_final(artifacts: RunArtifacts, node: str, config_digest: str = "config") -> None:
    artifact_path = artifacts.artifacts / f"{node}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps({"kind": node}), encoding="utf-8")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    artifacts.append_journal(
        "node_final",
        {
            "node": node,
            "input_digest": f"input-{node}",
            "config_digest": config_digest,
            "output_digest": f"output-{node}",
            "schema_name": node,
            "artifact_path": str(artifact_path.relative_to(artifacts.root)),
            "artifact_sha256": digest,
        },
    )


def _digest(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
