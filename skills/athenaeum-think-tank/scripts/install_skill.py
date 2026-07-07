from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL_NAME = "athenaeum-think-tank"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the ATHENAEUM skill for Codex or Claude Code.")
    parser.add_argument(
        "--target",
        action="append",
        choices=("codex", "codex-project", "codex-user", "claude-project", "claude-user"),
        required=True,
        help="Install target. codex is an alias for codex-project. Repeat to install to multiple targets.",
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root for project-level installs.")
    parser.add_argument("--symlink", action="store_true", help="Create a symlink instead of copying files.")
    parser.add_argument("--force", action="store_true", help="Replace an existing install at the destination.")
    args = parser.parse_args()

    source = Path(__file__).resolve().parents[1]
    if source.name != SKILL_NAME or not (source / "SKILL.md").exists():
        raise SystemExit(f"expected to run from {SKILL_NAME}/scripts/install_skill.py")

    for target in args.target:
        destination = _destination(target, args.project_root)
        _install(source, destination, symlink=args.symlink, force=args.force)
        print(f"{target}: {destination}")


def _destination(target: str, project_root: Path) -> Path:
    if target in {"codex", "codex-project"}:
        return project_root.resolve() / ".agents" / "skills" / SKILL_NAME
    if target == "codex-user":
        agents_home = Path(os.environ.get("AGENTS_HOME", Path.home() / ".agents"))
        return agents_home / "skills" / SKILL_NAME
    if target == "claude-project":
        return project_root.resolve() / ".claude" / "skills" / SKILL_NAME
    if target == "claude-user":
        return Path.home() / ".claude" / "skills" / SKILL_NAME
    raise ValueError(f"unknown target {target!r}")


def _install(source: Path, destination: Path, *, symlink: bool, force: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if not force:
            raise SystemExit(f"{destination} already exists; pass --force to replace it")
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    if symlink:
        destination.symlink_to(source, target_is_directory=True)
    else:
        shutil.copytree(source, destination, ignore=IGNORE)


if __name__ == "__main__":
    main()
