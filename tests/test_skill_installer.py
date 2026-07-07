from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "athenaeum-think-tank" / "scripts" / "install_skill.py"
SKILL_NAME = "athenaeum-think-tank"


def test_install_skill_copies_to_codex_project(tmp_path: Path) -> None:
    project_root = tmp_path / "project"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--target", "codex", "--project-root", str(project_root)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    destination = project_root / ".agents" / "skills" / SKILL_NAME
    assert not destination.is_symlink()
    assert (destination / "SKILL.md").exists()
    assert (destination / "references" / "iq-effort.md").exists()
    assert (destination / "scripts" / "install_skill.py").exists()


def test_install_skill_copies_to_codex_user_home(tmp_path: Path) -> None:
    env = {**os.environ, "AGENTS_HOME": str(tmp_path / "agents-home")}

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--target", "codex-user"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    destination = tmp_path / "agents-home" / "skills" / SKILL_NAME
    assert (destination / "SKILL.md").exists()


def test_install_skill_symlinks_claude_project_skill(tmp_path: Path) -> None:
    project_root = tmp_path / "project"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--target",
            "claude-project",
            "--project-root",
            str(project_root),
            "--symlink",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    destination = project_root / ".claude" / "skills" / SKILL_NAME
    assert destination.is_symlink()
    assert (destination / "SKILL.md").exists()
