from __future__ import annotations

from pathlib import Path

import pytest

from athenaeum.schemas import CitationRef, ClaimRef, SessionRecord
from athenaeum.store import CitationDB, ClaimLedger, SessionStore


def test_session_store_create_list_get_and_status(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    store.create(SessionRecord(id="s1", question="first", daily_budget=1.5, duration="2d"))
    store.create(SessionRecord(id="s2", question="second", daily_budget=2.0, duration="1d"))

    listed = store.list()
    assert [row["id"] for row in listed] == ["s1", "s2"]
    assert listed[0]["question"] == "first"
    assert listed[0]["status"] == "running"
    assert listed[0]["daily_budget"] == 1.5

    row = store.get("s1")
    assert row is not None
    assert row["id"] == "s1"
    assert row["duration"] == "2d"
    assert store.get("missing") is None

    store.set_status("s1", "paused")
    assert store.get("s1")["status"] == "paused"
    with pytest.raises(KeyError):
        store.set_status("missing", "stopped")


def test_session_store_enqueue_wake_returns_id(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    store.create(SessionRecord(id="s1", question="q", daily_budget=1.0, duration="1d"))
    wake_id = store.enqueue_wake("s1", "timer", {"tick": 1})

    assert wake_id.startswith("wake-s1-")
    wakes = store.due_wakes()
    assert any(wake["id"] == wake_id for wake in wakes)
    assert any(wake["reason"] == "timer" for wake in wakes)


def test_citation_db_link_run_and_list_sources(tmp_path: Path) -> None:
    db = CitationDB(tmp_path / "citations.sqlite3")
    citation = CitationRef(id="c1", title="Spec", url="https://example.com/docs")
    source_id = db.upsert_citation(citation)
    db.link_run("run-1", citation, claim_id="claim-1", node_id="research")

    sources = db.list_sources()
    assert len(sources) == 1
    assert sources[0]["id"] == source_id
    assert sources[0]["title"] == "Spec"
    assert sources[0]["url"] == "https://example.com/docs"


def test_citation_db_canonicalizes_title_only_sources(tmp_path: Path) -> None:
    db = CitationDB(tmp_path / "citations.sqlite3")
    db.upsert_citation(CitationRef(id="a", title="Internal Note", source_type="file"))
    db.upsert_citation(CitationRef(id="b", title=" internal note ", source_type="file"))

    assert len(db.list_sources()) == 1


def test_claim_ledger_write_current(tmp_path: Path) -> None:
    path = tmp_path / "claims.jsonl"
    ledger = ClaimLedger(path)
    ledger.append(ClaimRef(id="c1", text="one", status="unverified"), "draft")
    ledger.append(ClaimRef(id="c1", text="one", status="verified"), "verify", verdict_reason="checked")

    out = tmp_path / "current.json"
    ledger.write_current(out)
    data = __import__("json").loads(out.read_text(encoding="utf-8"))
    assert data["c1"]["version"] == 2
    assert data["c1"]["claim"]["status"] == "verified"
    assert data["c1"]["verdict_reason"] == "checked"


def test_claim_ledger_materialize_empty(tmp_path: Path) -> None:
    ledger = ClaimLedger(tmp_path / "missing.jsonl")
    assert ledger.materialize() == {}
