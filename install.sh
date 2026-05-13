#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_SOURCE="$REPO_ROOT/.codex/skills/topical-pk-report"
SKILL_TARGET="$CODEX_HOME/skills/topical-pk-report"

python3 -m pip install -e "$REPO_ROOT"

mkdir -p "$CODEX_HOME/skills"
rm -rf "$SKILL_TARGET"
cp -R "$SKILL_SOURCE" "$SKILL_TARGET"

python3 "$REPO_ROOT/scripts/validate_skill_structure.py"

echo "Installed topical-pk-report skill to: $SKILL_TARGET"
echo "Installed topical-pk-tool Python package from: $REPO_ROOT"
