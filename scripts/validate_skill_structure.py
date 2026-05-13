#!/usr/bin/env python3
"""Validate the distributable Codex skill and companion PK tool layout."""

from __future__ import annotations

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".codex" / "skills" / "topical-pk-report"
SKILL_MD = SKILL_DIR / "SKILL.md"
TEMPLATE = SKILL_DIR / "templates" / "basic_input_template.yaml"
MINIMAL_TEMPLATE = SKILL_DIR / "templates" / "minimal_input_template.yaml"
DATA_MINIMAL_TEMPLATE = ROOT / "data" / "minimal_input_template.yaml"


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing required path: {path.relative_to(ROOT)}")


def main() -> int:
    for path in [
        SKILL_MD,
        TEMPLATE,
        MINIMAL_TEMPLATE,
        DATA_MINIMAL_TEMPLATE,
        ROOT / "pktool" / "simulation.py",
        ROOT / "pktool" / "sampling.py",
        ROOT / "pktool" / "report.py",
        ROOT / "pktool" / "schemas" / "decision_gate.schema.json",
        ROOT / "tests" / "test_v11.py",
    ]:
        require(path)

    skill_text = SKILL_MD.read_text(encoding="utf-8")
    if "name: topical-pk-report" not in skill_text:
        raise SystemExit("SKILL.md front matter must define name: topical-pk-report")
    for token in [
        "decision_gate",
        "blocked_for_decision_use",
        "must_max_use",
        "be_bridging",
        "parameter_provenance.csv",
        "dose_extrapolation_sensitivity.csv",
        "Minimum Runnable Input",
        "minimal_input_template.yaml",
    ]:
        if token not in skill_text:
            raise SystemExit(f"SKILL.md is missing V1.1 token: {token}")

    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    checks = [
        ("compound", "safety_cmax_source"),
        ("compound", "safety_auc_source"),
        ("product", "variability_preset"),
        ("study_design", "purpose"),
        ("study_design", "sampling_purposes"),
    ]
    for section, key in checks:
        if key not in data.get(section, {}):
            raise SystemExit(f"Template is missing {section}.{key}")
    if "calibration_reference" not in data:
        raise SystemExit("Template is missing calibration_reference")

    minimal = yaml.safe_load(MINIMAL_TEMPLATE.read_text(encoding="utf-8"))
    minimal_checks = [
        ("compound", "compound_name"),
        ("product", "formulation"),
        ("product", "concentration_percent_w_w"),
        ("product", "daily_amount_g"),
    ]
    for section, key in minimal_checks:
        if key not in minimal.get(section, {}):
            raise SystemExit(f"Minimal template is missing {section}.{key}")

    print("Skill package validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
