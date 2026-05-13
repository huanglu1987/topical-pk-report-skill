#!/usr/bin/env python3
"""Check that the companion topical-pk-tool package is installed and reachable."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


REPO_NAME = "topical-pk-report-skill"
REPO_URL = "https://github.com/huanglu1987/topical-pk-report-skill.git"


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def pktool_available() -> bool:
    result = run([sys.executable, "-m", "pktool.cli", "--help"])
    return result.returncode == 0


def candidate_roots(skill_dir: Path) -> list[Path]:
    roots: list[Path] = []
    env_root = os.environ.get("TOPICAL_PK_TOOL_ROOT")
    if env_root:
        roots.append(Path(env_root).expanduser())

    marker = skill_dir / ".pktool_root"
    if marker.exists():
        text = marker.read_text(encoding="utf-8").strip()
        if text:
            roots.append(Path(text).expanduser())

    cwd = Path.cwd()
    roots.extend([cwd, *cwd.parents])
    home = Path.home()
    roots.extend(
        [
            home / "Projects" / REPO_NAME,
            home / "Desktop" / REPO_NAME,
            home / "Downloads" / REPO_NAME,
            home / ".codex" / "tools" / REPO_NAME,
        ]
    )
    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.expanduser()
        if resolved not in seen:
            unique.append(resolved)
            seen.add(resolved)
    return unique


def is_repo_root(path: Path) -> bool:
    return (path / "pyproject.toml").exists() and (path / "pktool" / "cli.py").exists()


def locate_repo(skill_dir: Path) -> Path | None:
    for root in candidate_roots(skill_dir):
        if is_repo_root(root):
            return root
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check topical-pk-tool installation.")
    parser.add_argument("--install", action="store_true", help="Install the local repo in editable mode if it is found.")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    if pktool_available():
        print("OK: pktool is available via python3 -m pktool.cli")
        return 0

    repo_root = locate_repo(skill_dir)
    if repo_root and args.install:
        print(f"Found companion repo: {repo_root}")
        result = run([sys.executable, "-m", "pip", "install", "-e", str(repo_root)])
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            return result.returncode
        marker = skill_dir / ".pktool_root"
        marker.write_text(str(repo_root), encoding="utf-8")
        if pktool_available():
            print("OK: pktool installed and verified.")
            return 0
        print("ERROR: install completed, but pktool is still not importable.", file=sys.stderr)
        return 2

    if repo_root:
        print(f"FOUND_REPO_NOT_INSTALLED: {repo_root}")
        print("Run:")
        print(f"  python3 {Path(__file__).resolve()} --install")
        return 1

    print("ERROR: pktool is not installed and the companion repository was not found.")
    print("Install the full repository, not only the Skill folder:")
    print(f"  git clone {REPO_URL}")
    print(f"  cd {REPO_NAME}")
    print("  chmod +x install.sh")
    print("  ./install.sh")
    print("")
    print("If the repository is already cloned elsewhere, set:")
    print("  export TOPICAL_PK_TOOL_ROOT=/absolute/path/to/topical-pk-report-skill")
    print(f"  python3 {Path(__file__).resolve()} --install")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
