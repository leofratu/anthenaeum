from __future__ import annotations

from pathlib import Path

import pytest

from athenaeum.schemas import SessionRecord
from athenaeum.store import SessionStore


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
