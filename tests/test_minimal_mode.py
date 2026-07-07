from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from athenaeum.cli import app


runner = CliRunner()


def test_minimal_mode_writes_report_and_run_artifacts() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["--minimal", "--seed", "7", "--out", "report.md", "Should we ship?"])

        assert result.exit_code == 0, result.output
        assert Path("report.md").exists()
        run_dirs = list(Path("runs").iterdir())
        assert len(run_dirs) == 1
        assert (run_dirs[0] / "journal.jsonl").exists()
        assert (run_dirs[0] / "claims.jsonl").exists()
        assert (run_dirs[0] / "ledger.json").exists()
        for name in ["research.json", "debate.json", "draft.initial.json", "verify.json", "court.json", "revise.json", "report.revised.md", "output.json"]:
            assert (run_dirs[0] / "artifacts" / name).exists()
        assert (run_dirs[0] / "manifest.json").exists()
        journal = (run_dirs[0] / "journal.jsonl").read_text(encoding="utf-8")
        assert "node_start" in journal
        assert "node_final" in journal
        output = json.loads((run_dirs[0] / "artifacts" / "output.json").read_text(encoding="utf-8"))
        assert output["report_markdown"].startswith("# ATHENAEUM Report")
        report_text = output["report_markdown"]
        for claim in output["claims"]:
            assert f"`{claim['status']}` {claim['text']}" in report_text
            opposite_status = "unverified" if claim["status"] == "verified" else "verified"
            assert f"`{opposite_status}` {claim['text']}" not in report_text


def test_seeded_minimal_mode_is_stable_for_same_input() -> None:
    with runner.isolated_filesystem():
        first = runner.invoke(app, ["--minimal", "--seed", "7", "--out", "a.md", "Should we ship?"])
        first_text = Path("a.md").read_text(encoding="utf-8")
        second = runner.invoke(app, ["--minimal", "--seed", "7", "--out", "b.md", "Should we ship?"])
        second_text = Path("b.md").read_text(encoding="utf-8")

        assert first.exit_code == 0
        assert second.exit_code == 0
        assert first_text == second_text


def test_dry_run_does_not_create_report() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["--dry-run", "--out", "report.md", "Should we ship?"])

        assert result.exit_code == 0, result.output
        assert "research" in result.output
        assert "debate" in result.output
        assert not Path("report.md").exists()


def test_json_dry_run_emits_machine_readable_plan() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["--json", "--dry-run", "Should we ship?"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["plan"]["question"] == "Should we ship?"
        assert payload["plan"]["nodes"][0]["name"] == "research"


def test_evolve_review_science_commands_write_schema_json() -> None:
    with runner.isolated_filesystem():
        Path("draft.md").write_text("# Draft\n\nA short argument.", encoding="utf-8")

        evolve = runner.invoke(app, ["evolve", "New governance idea", "--generations", "2", "--out", "evolve.md"])
        review = runner.invoke(app, ["review", "draft.md", "--out", "review.md"])
        science = runner.invoke(app, ["science", "Better caching improves latency", "--out", "science.md"])

        assert evolve.exit_code == 0, evolve.output
        assert review.exit_code == 0, review.output
        assert science.exit_code == 0, science.output
        assert json.loads(Path("evolve.md.json").read_text(encoding="utf-8"))["kind"] == "evolve"
        assert json.loads(Path("review.md.json").read_text(encoding="utf-8"))["kind"] == "review"
        assert json.loads(Path("science.md.json").read_text(encoding="utf-8"))["kind"] == "science"
        assert list(Path("runs").glob("*/artifacts/evolve.archive.json"))
        assert list(Path("runs").glob("*/artifacts/draft.input.md"))
        assert list(Path("runs").glob("*/artifacts/experiment_plan.json"))
