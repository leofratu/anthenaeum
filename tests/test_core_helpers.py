from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from athenaeum.conductor import jsonable_payload
from athenaeum.config import _string_list, _toml_bool, _toml_string, _unique
from athenaeum.effort import get_effort
from athenaeum.resume import (
    ResumeError,
    load_journal_rows,
    node_final_trusted,
    read_spent_usd,
    stored_plan_digest,
)
from athenaeum.sanity import SanityChecker
from athenaeum.workflow import compile_plan, estimated_cost_basis


def test_estimated_cost_basis_rejects_bool_and_nonpositive() -> None:
    effort = get_effort("low")
    assert estimated_cost_basis(effort, None) == effort.default_budget
    assert estimated_cost_basis(effort, {"suggested_budget": True}) == effort.default_budget
    assert estimated_cost_basis(effort, {"suggested_budget": 0}) == effort.default_budget
    assert estimated_cost_basis(effort, {"suggested_budget": -2.5}) == effort.default_budget
    assert estimated_cost_basis(effort, {"suggested_budget": 3.5}) == 3.5


def test_sanity_detects_duplicate_node_ids() -> None:
    base = compile_plan("Should we ship?", get_effort("low"), "minimal", 1.0)
    duplicate = base.nodes[0]
    plan = type(base)(
        question=base.question,
        effort=base.effort,
        runtime=base.runtime,
        budget=base.budget,
        nodes=base.nodes + (duplicate,),
        edges=base.edges,
    )
    report = SanityChecker().check(plan)
    assert any(finding.rule == "S1" and "duplicate" in finding.message for finding in report.errors)


def test_resume_helpers_parse_ledger_and_reject_bad_journal(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    ledger.write_text('{"spent_usd": 1.25}', encoding="utf-8")
    assert read_spent_usd(ledger) == 1.25
    assert read_spent_usd(tmp_path / "missing.json") == 0.0

    bad_ledger = tmp_path / "bad-ledger.json"
    bad_ledger.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ResumeError, match="ledger JSON"):
        read_spent_usd(bad_ledger)

    journal = tmp_path / "journal.jsonl"
    journal.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(ResumeError, match="JSON decode"):
        load_journal_rows(journal)

    plan_path = tmp_path / "artifacts" / "plan.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text('{"q":1}', encoding="utf-8")
    digest = stored_plan_digest(tmp_path)
    assert isinstance(digest, str) and len(digest) == 64

    artifact = tmp_path / "artifacts" / "research.json"
    artifact.write_text('{"ok":true}', encoding="utf-8")
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert node_final_trusted(
        tmp_path,
        {
            "input_digest": "i",
            "config_digest": digest,
            "output_digest": "o",
            "artifact_path": "artifacts/research.json",
            "artifact_sha256": sha,
        },
        expected_config_digest=digest,
    )
    assert not node_final_trusted(tmp_path, {"node": "research"}, expected_config_digest=digest)


def test_config_helpers_escape_and_dedupe() -> None:
    assert _toml_string('a"b\\c') == '"a\\"b\\\\c"'
    assert _toml_bool(True) == "true"
    assert _toml_bool(False) == "false"
    assert _string_list(["a", 1, "b"]) == ["a", "b"]
    assert _string_list("nope") == []
    assert _unique(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_jsonable_payload_prefers_model_dump() -> None:
    class Model:
        def model_dump(self, *, mode: str = "python"):
            return {"mode": mode, "ok": True}

    assert jsonable_payload(Model()) == {"mode": "json", "ok": True}
    assert jsonable_payload({"raw": 1}) == {"raw": 1}
