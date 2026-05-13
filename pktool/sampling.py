from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .io_utils import read_json, read_yaml


PURPOSE_SCHEDULES: dict[str, list[tuple[float, str, str]]] = {
    "exploratory": [
        (0, "predose", "探索性 PK"),
        (2, "早期峰 + 早期下降", "探索性 PK"),
        (4, "早期峰 + 早期下降", "探索性 PK"),
        (6, "早期峰 + 早期下降", "探索性 PK"),
        (8, "早期峰 + 早期下降", "探索性 PK"),
        (12, "早期峰 + 早期下降", "探索性 PK"),
        (24, "早期下降/AUC 覆盖", "探索性 PK"),
        (72, "多次给药累积", "探索性 PK"),
        (168, "Day 7 累积/残留", "探索性 PK"),
        (336, "Day 14 累积/残留", "探索性 PK"),
        (504, "Day 21 累积/残留", "探索性 PK"),
        (672, "Day 28 累积/残留", "探索性 PK"),
        (1344, "Week 8 稳态/末端", "探索性 PK"),
        (2016, "Week 12 稳态/末端", "探索性 PK"),
        (4032, "Week 24 稳态/末端", "探索性 PK"),
    ],
    "must_max_use": [
        (-24, "Day -1 baseline / washout 基线", "MUsT/max-use PK"),
        (0, "Day 1 predose", "MUsT/max-use PK"),
        (2, "Day 1 dense profile", "MUsT/max-use PK"),
        (4, "Day 1 dense profile", "MUsT/max-use PK"),
        (6, "Day 1 dense profile", "MUsT/max-use PK"),
        (8, "Day 1 dense profile", "MUsT/max-use PK"),
        (12, "Day 1 dense profile", "MUsT/max-use PK"),
        (24, "Day 1 dense profile", "MUsT/max-use PK"),
        (168, "Day 7 predose trough", "MUsT/max-use PK"),
        (336, "Day 14 predose trough", "MUsT/max-use PK"),
        (504, "Day 21 predose trough", "MUsT/max-use PK"),
        (672, "Day 28 predose trough / last-dose baseline", "MUsT/max-use PK"),
        (674, "Day 28 last-dose dense profile", "MUsT/max-use PK"),
        (676, "Day 28 last-dose dense profile", "MUsT/max-use PK"),
        (678, "Day 28 last-dose dense profile", "MUsT/max-use PK"),
        (680, "Day 28 last-dose dense profile", "MUsT/max-use PK"),
        (684, "Day 28 last-dose dense profile", "MUsT/max-use PK"),
        (696, "Day 28 last-dose dense profile", "MUsT/max-use PK"),
        (720, "Day 28 + 48 h", "MUsT/max-use PK"),
        (744, "Day 28 + 72 h", "MUsT/max-use PK"),
        (840, "Day 28 + 168 h", "MUsT/max-use PK"),
        (1008, "Day 28 + 336 h", "MUsT/max-use PK"),
        (1176, "Day 28 + 504 h", "MUsT/max-use PK"),
        (1344, "Day 28 + 672 h", "MUsT/max-use PK"),
        (1680, "Day 28 + 1008 h 长尾随访", "MUsT/max-use PK"),
        (2688, "Day 28 + 2016 h 长尾随访", "MUsT/max-use PK"),
        (4704, "Day 28 + 4032 h 长尾随访", "MUsT/max-use PK"),
    ],
    "be_bridging": [
        (0, "单次完整 PK / predose", "BE/桥接"),
        (1, "单次完整 PK", "BE/桥接"),
        (2, "单次完整 PK", "BE/桥接"),
        (3, "单次完整 PK", "BE/桥接"),
        (4, "单次完整 PK", "BE/桥接"),
        (5, "单次完整 PK", "BE/桥接"),
        (6, "单次完整 PK", "BE/桥接"),
        (8, "单次完整 PK", "BE/桥接"),
        (10, "单次完整 PK", "BE/桥接"),
        (12, "单次完整 PK", "BE/桥接"),
        (16, "单次完整 PK", "BE/桥接"),
        (24, "单次完整 PK", "BE/桥接"),
        (36, "单次完整 PK", "BE/桥接"),
        (48, "单次完整 PK", "BE/桥接"),
        (72, "单次完整 PK", "BE/桥接"),
        (96, "单次完整 PK", "BE/桥接"),
        (168, "单次末端 / Day 7", "BE/桥接"),
        (336, "单次末端 / Day 14", "BE/桥接"),
        (504, "单次末端 / Day 21", "BE/桥接"),
        (672, "单次末端 / Day 28", "BE/桥接"),
        (168, "多次 trough / Day 7 predose", "BE/桥接"),
        (336, "多次 trough / Day 14 predose", "BE/桥接"),
        (504, "多次 trough / Day 21 predose", "BE/桥接"),
        (672, "多次 trough / Day 28 predose", "BE/桥接"),
    ],
}


def _sampling_purposes(design: dict[str, Any]) -> list[str]:
    explicit = design.get("sampling_purposes") or design.get("sampling", {}).get("sampling_purposes")
    if isinstance(explicit, list) and explicit:
        purposes = [str(item).strip() for item in explicit]
    else:
        purposes = [str(design.get("purpose") or design.get("sampling", {}).get("purpose") or "exploratory").strip()]
    normalized = [purpose for purpose in purposes if purpose in PURPOSE_SCHEDULES]
    return normalized or ["exploratory"]


def _nearest_concentration(time: np.ndarray, values: np.ndarray, candidate: float) -> float | None:
    if candidate < 0 or len(time) == 0:
        return None
    if candidate < float(time[0]) or candidate > float(time[-1]):
        return None
    return float(np.interp(candidate, time, values))


def recommend_sampling(
    simulation_path: str | Path = "outputs/simulation_results.csv",
    design_path: str | Path = "data/study_design.yaml",
    output_path: str | Path = "outputs/sampling_recommendation.csv",
) -> Path:
    simulation_path = Path(simulation_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sim = pd.read_csv(simulation_path)
    summary = read_json(simulation_path.parent / "simulation_summary.json", default={}) or {}
    design = read_yaml(design_path) if Path(design_path).exists() else {}

    time = sim["time_h"].to_numpy(dtype=float)
    p50 = sim["concentration_p50_ng_ml"].to_numpy(dtype=float)
    p95 = sim["concentration_p95_ng_ml"].to_numpy(dtype=float)
    duration = float(summary.get("duration_h", time[-1] if len(time) else 0.0))

    rows: list[dict[str, Any]] = []
    for purpose in _sampling_purposes(design):
        for candidate_time, sample_intent, stage in PURPOSE_SCHEDULES[purpose]:
            conc_p50 = _nearest_concentration(time, p50, candidate_time)
            conc_p95 = _nearest_concentration(time, p95, candidate_time)
            within_simulation = 0 <= candidate_time <= duration
            rows.append(
                {
                    "purpose": purpose,
                    "candidate_time_h": float(candidate_time),
                    "stage": stage,
                    "sample_intent": sample_intent,
                    "recommended": True,
                    "total_score": 1.0 if within_simulation else 0.6,
                    "within_simulation_window": within_simulation,
                    "concentration_p50_ng_ml": conc_p50,
                    "concentration_p95_ng_ml": conc_p95,
                    "note": "长半衰期 + 浓度依赖清除药物的 BE/桥接通常需 PopPK 复核。"
                    if purpose == "be_bridging"
                    else "",
                }
            )

    scored = pd.DataFrame(rows)
    scored = scored.sort_values(["purpose", "candidate_time_h", "sample_intent"])
    scored.to_csv(output_path, index=False)
    return output_path
