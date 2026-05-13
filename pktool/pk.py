from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from .io_utils import get_numeric


@dataclass(frozen=True)
class SystemicPK:
    half_life_h: float
    ke_h: float
    volume_l: float
    clearance_l_h: float
    lloq_ng_ml: float
    reference_auc_ng_h_ml: float | None
    reference_cmax_ng_ml: float | None
    safety_cmax_ng_ml: float | None
    safety_auc_ng_h_ml: float | None
    warnings: tuple[str, ...]


def half_life_to_ke(half_life_h: float) -> float:
    if half_life_h <= 0:
        raise ValueError("half_life_h must be > 0")
    return math.log(2) / half_life_h


def cl_v_to_ke(clearance_l_h: float, volume_l: float) -> float:
    if clearance_l_h <= 0:
        raise ValueError("clearance_l_h must be > 0")
    if volume_l <= 0:
        raise ValueError("volume_l must be > 0")
    return clearance_l_h / volume_l


def trapezoid_auc(time_h: np.ndarray, concentration: np.ndarray) -> float:
    if len(time_h) != len(concentration):
        raise ValueError("time and concentration arrays must have the same length")
    if len(time_h) < 2:
        return 0.0
    return float(np.trapezoid(concentration, time_h))


def interval_auc(time_h: np.ndarray, concentration: np.ndarray, start_h: float, end_h: float) -> float:
    if end_h <= start_h:
        return 0.0
    mask = (time_h >= start_h) & (time_h <= end_h)
    interval_time = time_h[mask]
    interval_conc = concentration[mask]
    if len(interval_time) == 0 or interval_time[0] > start_h:
        interval_conc = np.insert(interval_conc, 0, float(np.interp(start_h, time_h, concentration)))
        interval_time = np.insert(interval_time, 0, start_h)
    if interval_time[-1] < end_h:
        interval_conc = np.append(interval_conc, float(np.interp(end_h, time_h, concentration)))
        interval_time = np.append(interval_time, end_h)
    return trapezoid_auc(interval_time, interval_conc)


def effective_steady_state_times(
    elimination_half_life_h: float,
    depot_half_life_h: float | None = None,
    fast_absorption_half_life_h: float | None = None,
) -> dict[str, float]:
    candidates = [float(elimination_half_life_h)]
    if depot_half_life_h and depot_half_life_h > 0:
        candidates.append(float(depot_half_life_h))
    if fast_absorption_half_life_h and fast_absorption_half_life_h > 0:
        candidates.append(float(fast_absorption_half_life_h))
    t_half_eff = max(candidates)
    return {
        "t_half_eff_h": t_half_eff,
        "t_ss_90_h": math.log(10) / math.log(2) * t_half_eff,
        "t_ss_95_h": math.log(20) / math.log(2) * t_half_eff,
    }


def resolve_systemic_pk(compound: dict[str, Any], reference: dict[str, Any]) -> SystemicPK:
    warnings: list[str] = []

    half_life = get_numeric(compound, ["half_life_h", "t_half_h", "t1_2_h"])
    if half_life is None:
        half_life = get_numeric(reference, ["half_life_h", "t_half_h", "t1_2_h"])

    volume_l = get_numeric(compound, ["volume_l", "v_l", "vd_l", "v_f_l"])
    if volume_l is None:
        volume_l = get_numeric(reference, ["volume_l", "v_l", "vd_l", "v_f_l"])

    clearance_l_h = get_numeric(compound, ["clearance_l_h", "cl_l_h", "cl_f_l_h"])
    if clearance_l_h is None:
        clearance_l_h = get_numeric(reference, ["clearance_l_h", "cl_l_h", "cl_f_l_h"])

    if half_life is None and clearance_l_h is not None and volume_l is not None:
        ke = cl_v_to_ke(clearance_l_h, volume_l)
        half_life = math.log(2) / ke
    elif half_life is not None:
        ke = half_life_to_ke(half_life)
    else:
        half_life = 12.0
        ke = half_life_to_ke(half_life)
        warnings.append("缺少 t1/2 或 CL/V，已使用示例默认半衰期 12 h。")

    if volume_l is None:
        volume_l = 50.0
        warnings.append("缺少分布容积，已使用示例默认 V=50 L。")

    if clearance_l_h is None:
        clearance_l_h = ke * volume_l
        warnings.append("缺少清除率，已由 ke × V 推算。")

    lloq = get_numeric(compound, ["lloq_ng_ml", "lloq"], default=0.0) or 0.0

    return SystemicPK(
        half_life_h=float(half_life),
        ke_h=float(ke),
        volume_l=float(volume_l),
        clearance_l_h=float(clearance_l_h),
        lloq_ng_ml=float(lloq),
        reference_auc_ng_h_ml=get_numeric(reference, ["reference_auc_ng_h_ml", "auc_ng_h_ml", "auc0_t_ng_h_ml"]),
        reference_cmax_ng_ml=get_numeric(reference, ["reference_cmax_ng_ml", "cmax_ng_ml"]),
        safety_cmax_ng_ml=get_numeric(compound, ["safety_cmax_ng_ml", "safety_cmax"]),
        safety_auc_ng_h_ml=get_numeric(compound, ["safety_auc_ng_h_ml", "safety_auc"]),
        warnings=tuple(warnings),
    )
