from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .io_utils import get_range, load_compound_profile, load_reference_pk, read_yaml, to_float, write_json
from .pk import effective_steady_state_times, interval_auc, resolve_systemic_pk, trapezoid_auc


VARIABILITY_PRESETS: dict[str, tuple[float, float]] = {
    "low": (0.30, 0.25),
    "medium": (0.50, 0.40),
    "high": (0.80, 0.60),
}

KNOWN_FORMULATION_REQUIRED_FIELDS = [
    "fraction_unbound",
    "metabolism_pathway",
    "dose_proportionality",
    "linear_dose_range_mg",
    "population",
    "species",
]


def _log_uniform(rng: np.random.Generator, low: float, high: float) -> float:
    low = max(low, 1e-12)
    high = max(high, low)
    if low == high:
        return low
    return float(np.exp(rng.uniform(np.log(low), np.log(high))))


def _cv_multiplier(rng: np.random.Generator, cv: float) -> float:
    if cv <= 0:
        return 1.0
    sigma2 = math.log(1 + cv**2)
    sigma = math.sqrt(sigma2)
    mu = -0.5 * sigma2
    return float(rng.lognormal(mean=mu, sigma=sigma))


def _metric_quantiles(series: pd.Series) -> dict[str, float]:
    return {
        "p5": float(series.quantile(0.05)),
        "p50": float(series.quantile(0.50)),
        "p95": float(series.quantile(0.95)),
    }


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "启用"}


def _provided_number(value: Any) -> bool:
    return to_float(value) is not None


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except TypeError:
        pass
    return str(value).strip() not in {"", "nan", "NaN", "None", "none", "/"}


def _range_contains(range_value: Any, value: float) -> bool:
    if isinstance(range_value, (list, tuple)) and len(range_value) == 2:
        low = to_float(range_value[0])
        high = to_float(range_value[1])
    elif isinstance(range_value, str) and "," in range_value:
        low_text, high_text = range_value.split(",", 1)
        low = to_float(low_text)
        high = to_float(high_text)
    else:
        return False
    if low is None or high is None:
        return False
    if low > high:
        low, high = high, low
    return low <= value <= high


def _extract_range(value: Any) -> tuple[float, float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        low = to_float(value[0])
        high = to_float(value[1])
    elif isinstance(value, str) and "," in value:
        low_text, high_text = value.split(",", 1)
        low = to_float(low_text)
        high = to_float(high_text)
    else:
        return None
    if low is None or high is None:
        return None
    if low > high:
        low, high = high, low
    return float(low), float(high)


def _fast_absorption_auto_assessment(compound: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    gate_failures: list[str] = []
    evidence = product.get("fast_absorption_evidence", {}) or {}
    if not isinstance(evidence, dict):
        evidence = {}

    mw = to_float(compound.get("molecular_weight"))
    if mw is None:
        gate_failures.append("缺少分子量，无法确认 MW <= 600 Da 必须项。")
    elif mw > 600:
        gate_failures.append(f"分子量 {mw:g} Da > 600 Da，快速被动吸收支持不足。")

    xlogp = to_float(compound.get("xlogp"))
    if xlogp is None:
        gate_failures.append("缺少 logP/xlogP，无法确认 logP 1-5 必须项。")
    elif not 1 <= xlogp <= 5:
        gate_failures.append(f"logP/xlogP {xlogp:g} 不在 1-5 范围内。")

    barrier_disrupted = _truthy(product.get("barrier_disrupted") or product.get("microneedle") or product.get("laser_disruption"))
    if barrier_disrupted:
        gate_failures.append("输入提示角质层被显著破坏，当前 topical 被动吸收模型不适用。")

    ivpt_jss = to_float(evidence.get("ivpt_jss_ug_cm2_h") or evidence.get("jss_ug_cm2_h"))
    if ivpt_jss is not None and ivpt_jss > 0.05:
        score += 30
        reasons.append(f"IVPT Jss {ivpt_jss:g} ug/cm2/h > 0.05，支持快速吸收。")

    observed_tmax_h = to_float(evidence.get("observed_topical_tmax_h"))
    observed_cmax = to_float(evidence.get("observed_topical_cmax_ng_ml"))
    lloq = to_float(compound.get("lloq_ng_ml"), 0.0) or 0.0
    if observed_tmax_h is not None and observed_tmax_h <= 8:
        if observed_cmax is not None and (lloq <= 0 or observed_cmax > 3 * lloq):
            score += 25
            reasons.append(f"既往人体外用 Tmax {observed_tmax_h:g} h 且 Cmax > 3x LLOQ。")
        else:
            score += 10
            reasons.append(f"既往外用 Tmax {observed_tmax_h:g} h，但 Cmax/LLOQ 支持不足。")
    elif observed_tmax_h is not None and observed_tmax_h <= 24:
        score += 10
        reasons.append(f"既往/公开外用 Tmax 在 24 h 内（{observed_tmax_h:g} h）。")

    formulation = str(product.get("formulation", "")).lower()
    vehicle = str(product.get("vehicle", "") or product.get("formulation_excipients", "")).lower()
    fast_formulation = any(term in formulation for term in ["solution", "spray", "foam", "溶液", "喷雾", "泡沫"])
    enhancer = any(term in vehicle for term in ["ethanol", "alcohol", "propylene glycol", "peg", "乙醇", "丙二醇"])
    if fast_formulation and enhancer:
        score += 15
        reasons.append("剂型为溶液/喷雾/泡沫且载体含已验证促渗/快速挥发成分。")
    elif fast_formulation:
        reasons.append("目标剂型释放较快，但未记录已验证促渗载体，未加中等证据分。")

    auc_0_8_ratio = to_float(evidence.get("auc0_8_over_auc0_t") or evidence.get("auc0_8h_auc0_t_ratio"))
    if auc_0_8_ratio is not None and auc_0_8_ratio > 0.3:
        score += 15
        reasons.append(f"既往外用 AUC0-8h/AUC0-t = {auc_0_8_ratio:g} > 0.3。")

    dose_mg = to_float(product.get("dose_mg_per_application"))
    if dose_mg is not None and dose_mg >= 5:
        score += 5
        reasons.append(f"单次外用剂量较高（{dose_mg:g} mg）。")
    if mw is not None and mw <= 500:
        score += 5
        reasons.append(f"分子量 {mw:g} Da <= 500 Da。")

    day7_blq_ratio = to_float(evidence.get("day7_blq_ratio") or evidence.get("day7_blq_pct"))
    if day7_blq_ratio is not None:
        ratio = day7_blq_ratio / 100 if day7_blq_ratio > 1 else day7_blq_ratio
        if ratio > 0.5:
            score -= 20
            reasons.append(f"既往外用 Day 7 BLQ 比例 {ratio:.0%} > 50%，作为负向证据。")

    species = str(evidence.get("species") or product.get("species") or "").strip().lower()
    human_hint = str(evidence.get("source_type") or evidence.get("population") or "").strip().lower()
    if species in {"animal", "rat", "mouse", "dog", "动物"} and "human" not in human_hint and "人体" not in human_hint:
        score -= 10
        reasons.append("仅记录动物外用数据，无人体外用数据，作为负向证据。")

    score = max(score, 0)
    level = "probable" if score >= 75 else "possible" if score >= 50 else "insufficient"
    enabled = score >= 60 and not gate_failures
    if gate_failures:
        level = "insufficient"
        enabled = False
    if not reasons and not gate_failures:
        reasons.append("未见明确早期峰值、促渗剂型或高剂量证据，默认不启用早期快速吸收模块。")

    return {
        "enabled": enabled,
        "score": score,
        "level": level,
        "gate_failures": gate_failures,
        "reasons": reasons + [f"必须项未满足：{item}" for item in gate_failures],
    }


def assess_fast_absorption_need(compound: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    auto = _fast_absorption_auto_assessment(compound, product)
    explicit = product.get("enable_fast_absorption")
    if explicit is not None and str(explicit).strip().lower() not in {"auto", ""}:
        enabled = _truthy(explicit)
        return {
            "enabled": enabled,
            "score": 100 if enabled else 0,
            "level": "manual_on" if enabled else "manual_off",
            "auto_enabled": auto["enabled"],
            "auto_score": auto["score"],
            "auto_level": auto["level"],
            "manual_override": True,
            "gate_failures": auto.get("gate_failures", []),
            "reasons": [
                "用户在输入中手动启用早期快速吸收模块。" if enabled else "用户在输入中手动关闭早期快速吸收模块。",
                f"自动判定结果为 {auto['level']}，评分 {auto['score']}。",
            ],
        }
    auto["manual_override"] = False
    return auto


def assess_elimination_kinetics(compound: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    mode = str(compound.get("elimination_model") or reference.get("elimination_model") or "auto").strip().lower()
    if mode in {"first_order", "linear", "1", "一阶", "一级"}:
        return {
            "model": "first_order",
            "level": "manual_first_order",
            "reasons": ["用户/输入指定按一阶消除处理。"],
            "zero_order_supported": False,
            "nonlinear_flag": False,
        }
    if mode in {"zero_order", "0", "零阶"}:
        return {
            "model": "zero_order",
            "level": "manual_zero_order",
            "reasons": ["用户/输入指定按零阶消除处理。"],
            "zero_order_supported": True,
            "nonlinear_flag": True,
        }
    if mode in {"michaelis_menten", "capacity_limited", "nonlinear", "mm", "非线性"}:
        return {
            "model": "michaelis_menten",
            "level": "manual_capacity_limited",
            "reasons": ["用户/输入指定按容量限制/Michaelis-Menten 消除处理。"],
            "zero_order_supported": False,
            "nonlinear_flag": True,
        }

    reasons: list[str] = []
    nonlinear_flag = False
    text = " ".join(str(compound.get(key, "")) for key in ("elimination_notes", "notes", "value_source")).lower()
    if any(
        term in text
        for term in [
            "nonlinear",
            "capacity",
            "saturable",
            "concentration-dependent",
            "dose/concentration-dependent",
            "非线性",
            "饱和",
            "浓度依赖",
        ]
    ):
        nonlinear_flag = True
        reasons.append("输入/来源说明中出现非线性、容量限制、饱和或浓度依赖消除信号。")

    half_life_h = compound.get("half_life_h") or reference.get("half_life_h")
    half_life_float = to_float(half_life_h)
    if half_life_float is not None and half_life_float >= 168:
        reasons.append(f"半衰期很长（{half_life_float:g} h），需要关注蓄积和末端采样；长半衰期本身不等同于零阶消除。")

    if nonlinear_flag and _provided_number(compound.get("vmax_ng_h")) and _provided_number(compound.get("km_ng_ml")):
        model = "michaelis_menten"
        level = "capacity_limited_with_parameters"
        reasons.append("已提供 Vmax/Km，可运行容量限制消除模型。")
    elif nonlinear_flag:
        model = "first_order"
        level = "nonlinear_risk_first_order_default"
        reasons.append("未提供 Vmax/Km，当前按一阶消除运行，仅作为线性下界探索。")
    else:
        model = "first_order"
        level = "first_order_supported"
        reasons.append("未见零阶消除或容量限制参数；当前低系统暴露场景默认按一阶消除。")

    return {
        "model": model,
        "level": level,
        "reasons": reasons,
        "zero_order_supported": model == "zero_order",
        "nonlinear_flag": nonlinear_flag,
    }


def _resolve_variability(product: dict[str, Any]) -> dict[str, Any]:
    preset = str(product.get("variability_preset") or "medium").strip().lower()
    explicit_iiv = product.get("interindividual_cv")
    explicit_bav = product.get("bioavailability_cv")
    if explicit_iiv not in (None, "") or explicit_bav not in (None, ""):
        return {
            "preset": "custom",
            "interindividual_cv": float(to_float(explicit_iiv, VARIABILITY_PRESETS["medium"][0]) or 0.0),
            "bioavailability_cv": float(to_float(explicit_bav, VARIABILITY_PRESETS["medium"][1]) or 0.0),
            "source": "user_explicit_cv",
        }
    if preset not in VARIABILITY_PRESETS:
        preset = "medium"
    iiv, bav = VARIABILITY_PRESETS[preset]
    return {"preset": preset, "interindividual_cv": iiv, "bioavailability_cv": bav, "source": "preset"}


def _simulate_one(
    rng: np.random.Generator,
    times: np.ndarray,
    dose_times: np.ndarray,
    dose_mg: float,
    pk_ke: float,
    volume_l: float,
    elimination_model: str,
    vmax_ng_h: float | None,
    km_ng_ml: float | None,
    absorption_fraction_range: tuple[float, float],
    fast_absorption_fraction_range: tuple[float, float],
    ka_fast_range: tuple[float, float],
    fast_lag_time_range: tuple[float, float],
    ka_skin_range: tuple[float, float],
    depot_half_life_range: tuple[float, float],
    lag_time_range: tuple[float, float],
    interindividual_cv: float,
    bioavailability_cv: float,
    fast_absorption_enabled: bool,
) -> tuple[np.ndarray, dict[str, float]]:
    f_topical = rng.uniform(*absorption_fraction_range)
    f_topical *= _cv_multiplier(rng, bioavailability_cv)
    f_topical *= _cv_multiplier(rng, interindividual_cv)
    f_topical = min(max(f_topical, 0.0), 1.0)
    fast_fraction = min(max(rng.uniform(*fast_absorption_fraction_range), 0.0), 1.0) if fast_absorption_enabled else 0.0
    ka_fast = _log_uniform(rng, *ka_fast_range)
    fast_lag_h = rng.uniform(*fast_lag_time_range)
    ka_skin = _log_uniform(rng, *ka_skin_range)
    depot_half_life = _log_uniform(rng, *depot_half_life_range)
    k_release = math.log(2) / depot_half_life
    lag_h = rng.uniform(*lag_time_range)

    dt = float(times[1] - times[0]) if len(times) > 1 else 1.0
    dose_ng_available = dose_mg * 1_000_000.0 * f_topical
    fast_dose_ng = dose_ng_available * fast_fraction
    slow_dose_ng = dose_ng_available * (1.0 - fast_fraction)
    fast_release_times = dose_times + fast_lag_h
    slow_release_times = dose_times + lag_h
    next_fast_dose_idx = 0
    next_slow_dose_idx = 0

    a_fast_surface = 0.0
    a_slow_surface = 0.0
    a_skin = 0.0
    a_central = 0.0
    concentration = np.zeros_like(times, dtype=float)

    for idx, time_h in enumerate(times):
        concentration[idx] = max(a_central / (volume_l * 1000.0), 0.0)
        if idx == len(times) - 1:
            break

        while next_fast_dose_idx < len(fast_release_times) and fast_release_times[next_fast_dose_idx] <= time_h:
            a_fast_surface += fast_dose_ng
            next_fast_dose_idx += 1
        while next_slow_dose_idx < len(slow_release_times) and slow_release_times[next_slow_dose_idx] <= time_h:
            a_slow_surface += slow_dose_ng
            next_slow_dose_idx += 1

        fast_absorbed = a_fast_surface * (1 - math.exp(-ka_fast * dt))
        a_fast_surface -= fast_absorbed
        a_central += fast_absorbed

        released = a_slow_surface * (1 - math.exp(-k_release * dt))
        a_slow_surface -= released
        a_skin += released

        absorbed = a_skin * (1 - math.exp(-ka_skin * dt))
        a_skin -= absorbed
        a_central += absorbed

        if elimination_model == "zero_order" and vmax_ng_h:
            eliminated = min(a_central, vmax_ng_h * dt)
        elif elimination_model == "michaelis_menten" and vmax_ng_h and km_ng_ml:
            central_concentration = a_central / (volume_l * 1000.0)
            rate = vmax_ng_h * central_concentration / (km_ng_ml + central_concentration) if central_concentration > 0 else 0.0
            eliminated = min(a_central, rate * dt)
        else:
            eliminated = a_central * (1 - math.exp(-pk_ke * dt))
        a_central -= eliminated

    draw = {
        "f_topical": f_topical,
        "fast_absorption_fraction": fast_fraction,
        "ka_fast_h": ka_fast,
        "fast_lag_time_h": fast_lag_h,
        "ka_skin_h": ka_skin,
        "depot_half_life_h": depot_half_life,
        "lag_time_h": lag_h,
    }
    return concentration, draw


def _load_known_formulations(product_path: str | Path) -> pd.DataFrame:
    known_path = Path(product_path).parent / "known_formulations_pk.csv"
    if known_path.exists():
        return pd.read_csv(known_path)
    return pd.DataFrame()


def _known_formulation_gaps(known: pd.DataFrame, half_life_h: float) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if known.empty:
        return [{"record": "all", "missing_fields": ["known_formulations"], "severity": "required"}]
    for idx, row in known.iterrows():
        missing = [field for field in KNOWN_FORMULATION_REQUIRED_FIELDS if field not in known.columns or not _nonempty(row.get(field))]
        if not (_nonempty(row.get("tmax_sd_h")) or _nonempty(row.get("tmax_range_h"))):
            missing.append("tmax_sd_h_or_tmax_range_h")
        single_or_multiple = str(row.get("single_or_multiple", "")).lower()
        if "multiple" in single_or_multiple or "多次" in single_or_multiple:
            for field in ("accumulation_ratio", "time_to_ss_h"):
                if field not in known.columns or not _nonempty(row.get(field)):
                    missing.append(field)
        route = str(row.get("route", "")).lower()
        if route in {"topical", "dermal", "cutaneous", "外用", "局部外用"}:
            if not (_nonempty(row.get("formulation_excipients")) or _nonempty(row.get("vehicle"))):
                missing.append("formulation_excipients_or_vehicle")
        if half_life_h >= 168 and not (_nonempty(row.get("washout_duration_h")) or _nonempty(row.get("blq_time_h"))):
            missing.append("washout_duration_h_or_blq_time_h")
        if missing:
            gaps.append({"record": row.get("name", f"row_{idx + 1}"), "missing_fields": sorted(set(missing)), "severity": "required"})
    return gaps


def _calibration_assessment(product: dict[str, Any], absorption_fraction_range: tuple[float, float]) -> dict[str, Any]:
    ref = product.get("calibration_reference")
    if not isinstance(ref, dict) or not ref:
        return {
            "status": "missing",
            "triggers": ["calibration_anchor_missing"],
            "messages": ["未提供人体外用 calibration_reference；本次运行仍允许，但需在报告中作为 warning 展示。"],
        }
    triggers: list[str] = []
    messages: list[str] = []
    failed = False

    source_type = str(ref.get("source_type", "")).strip().lower()
    if source_type != "human_topical":
        failed = True
        triggers.append("calibration_failed")
        messages.append("calibration_reference 不是 human_topical，不能作为 V1.1 反向校准锚点。")

    vehicle_match_score = to_float(ref.get("vehicle_match_score"))
    if vehicle_match_score is not None and vehicle_match_score < 0.5:
        triggers.append("calibration_vehicle_mismatch")
        messages.append(f"vehicle_match_score={vehicle_match_score:g} < 0.5，载体相似性不足。")

    observed_tmax = to_float(ref.get("observed_tmax_h"))
    tmax_range = _extract_range(ref.get("observed_tmax_h_range"))
    if observed_tmax is not None and tmax_range and not (tmax_range[0] <= observed_tmax <= tmax_range[1]):
        failed = True
        triggers.append("calibration_failed")
        messages.append("observed_tmax_h 不在 observed_tmax_h_range 内。")

    observed_cmax = to_float(ref.get("observed_cmax_ng_ml"))
    cmax_range = _extract_range(ref.get("observed_cmax_ng_ml_range"))
    if observed_cmax is not None and cmax_range and not (cmax_range[0] <= observed_cmax <= cmax_range[1]):
        failed = True
        triggers.append("calibration_failed")
        messages.append("observed_cmax_ng_ml 不在 observed_cmax_ng_ml_range 内。")

    dose_mg = to_float(ref.get("dose_mg"))
    f_proxy = None
    if observed_cmax is not None and dose_mg and dose_mg > 0:
        f_proxy = observed_cmax / (dose_mg * 1000.0)
        low, high = absorption_fraction_range
        if not (low <= f_proxy <= high):
            messages.append(
                f"反向校准 F proxy={f_proxy:.3g} 未落入吸收比例范围 [{low:.3g}, {high:.3g}]；按定性校准处理。"
            )

    if failed:
        status = "failed"
    elif triggers:
        status = "warning"
    else:
        status = "passed"
        messages.append("calibration_reference 完整性检查通过，可作为定性反向校准锚点。")
    return {
        "status": status,
        "triggers": sorted(set(triggers)),
        "source_citation": ref.get("source_citation", ""),
        "observed_tmax_h": observed_tmax,
        "observed_cmax_ng_ml": observed_cmax,
        "f_proxy": f_proxy,
        "vehicle_match_score": vehicle_match_score,
        "messages": messages,
    }


def _dose_extrapolation_factor(product: dict[str, Any]) -> float | None:
    ref = product.get("calibration_reference")
    if not isinstance(ref, dict):
        return None
    ref_dose = to_float(ref.get("dose_mg"))
    target_dose = to_float(product.get("dose_mg_per_application"))
    if ref_dose is None or ref_dose <= 0 or target_dose is None:
        return None
    return target_dose / ref_dose


def _write_dose_sensitivity(
    output: Path,
    product: dict[str, Any],
    metrics_df: pd.DataFrame,
) -> Path:
    factor = _dose_extrapolation_factor(product) or 1.0
    cmax_q = _metric_quantiles(metrics_df["cmax_global_ng_ml"] if "cmax_global_ng_ml" in metrics_df else metrics_df["cmax_ng_ml"])
    auc_q = _metric_quantiles(metrics_df["auc_0_t_studyend_ng_h_ml"] if "auc_0_t_studyend_ng_h_ml" in metrics_df else metrics_df["auc0_t_ng_h_ml"])
    rows = []
    for exponent in (0.7, 1.0, 1.3):
        scale = factor ** (exponent - 1.0) if factor > 0 else 1.0
        rows.append(
            {
                "dose_extrapolation_exponent": exponent,
                "dose_extrapolation_factor": factor,
                "cmax_p50_ng_ml": cmax_q["p50"] * scale,
                "cmax_p95_ng_ml": cmax_q["p95"] * scale,
                "auc_p50_ng_h_ml": auc_q["p50"] * scale,
                "auc_p95_ng_h_ml": auc_q["p95"] * scale,
            }
        )
    path = output / "dose_extrapolation_sensitivity.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _write_parameter_provenance(
    output: Path,
    compound: dict[str, Any],
    reference: dict[str, Any],
    product: dict[str, Any],
    pk_values: dict[str, Any],
    variability: dict[str, Any],
) -> Path:
    rows = []
    for parameter, value in pk_values.items():
        if parameter in reference and _nonempty(reference.get(parameter)):
            provenance = "public"
            source = reference.get("source", "reference_pk")
        elif parameter in compound and _nonempty(compound.get(parameter)):
            provenance = "user"
            source = compound.get("value_source", "compound_profile")
        else:
            provenance = "default"
            source = "model_default_or_derived"
        rows.append({"parameter": parameter, "value": value, "provenance": provenance, "source": source})
    for parameter in [
        "dose_mg_per_application",
        "absorption_fraction_range",
        "fast_absorption_fraction_range",
        "ka_fast_h_range",
        "ka_skin_h_range",
        "depot_half_life_h_range",
        "lag_time_h_range",
    ]:
        rows.append(
            {
                "parameter": parameter,
                "value": product.get(parameter, ""),
                "provenance": "user" if parameter in product else "default",
                "source": "topical_product.yaml",
            }
        )
    rows.extend(
        [
            {
                "parameter": "interindividual_cv",
                "value": variability["interindividual_cv"],
                "provenance": "user" if variability["source"] == "user_explicit_cv" else "default",
                "source": variability["preset"],
            },
            {
                "parameter": "bioavailability_cv",
                "value": variability["bioavailability_cv"],
                "provenance": "user" if variability["source"] == "user_explicit_cv" else "default",
                "source": variability["preset"],
            },
        ]
    )
    path = output / "parameter_provenance.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _build_decision_gate(
    *,
    elimination_assessment: dict[str, Any],
    metric_quantiles: dict[str, dict[str, float]],
    pk_reference_cmax: float | None,
    pk_reference_auc: float | None,
    safety_cmax: float | None,
    safety_auc: float | None,
    compound: dict[str, Any],
    duration_h: float,
    last_dose_h: float,
    half_life_h: float,
    known_gaps: list[dict[str, Any]],
    calibration: dict[str, Any],
    product: dict[str, Any],
) -> dict[str, Any]:
    triggers: list[str] = []
    recommended_actions: list[str] = []
    blocked = False
    warning = False

    cmax_q = metric_quantiles.get("cmax_global_ng_ml") or metric_quantiles.get("cmax_ng_ml", {})
    auc_ratio_q = metric_quantiles.get("auc_ratio_reference", {})
    p95_cmax = cmax_q.get("p95")
    p95_auc_ratio = auc_ratio_q.get("p95")
    reference_cmax_or_css = pk_reference_cmax or safety_cmax
    reference_auc = pk_reference_auc or safety_auc

    if elimination_assessment.get("nonlinear_flag"):
        triggers.append("nonlinear_signal_present")
        warning = True

    if known_gaps:
        triggers.append("known_formulations_required_fields_missing")
        warning = True

    post_last_followup_h = max(duration_h - last_dose_h, 0.0)
    terminal_followup_x_t_half = post_last_followup_h / half_life_h if half_life_h > 0 else None
    if terminal_followup_x_t_half is not None and terminal_followup_x_t_half < 3:
        triggers.append("terminal_followup_insufficient")
        warning = True

    if safety_cmax is not None and not _nonempty(compound.get("safety_cmax_source")):
        triggers.append("safety_threshold_source_missing")
        warning = True
    if safety_auc is not None and not _nonempty(compound.get("safety_auc_source")):
        triggers.append("safety_threshold_source_missing")
        warning = True

    if calibration.get("status") == "missing":
        triggers.append("calibration_anchor_missing")
        warning = True
    if calibration.get("status") == "failed":
        triggers.append("calibration_failed")
        blocked = True

    if elimination_assessment.get("nonlinear_flag") and reference_cmax_or_css and p95_cmax and p95_cmax > reference_cmax_or_css:
        triggers.append("p95_cmax_exceeds_reference_css")
        blocked = True
    if elimination_assessment.get("nonlinear_flag") and p95_auc_ratio and p95_auc_ratio > 1.0:
        triggers.append("p95_auc_ratio_above_one")
        blocked = True

    dose_factor = _dose_extrapolation_factor(product)
    if elimination_assessment.get("nonlinear_flag") and dose_factor is not None and dose_factor > 20:
        triggers.append("high_dose_extrapolation_with_nonlinear_signal")
        blocked = True

    if blocked:
        status = "blocked_for_decision_use"
        recommended_actions.extend(
            [
                "Treat all P95 outputs as model exploration only",
                "Do not use for CRO statement of work",
                "Do not use for final MUsT sampling schedule or regulatory exposure narrative",
                "Require Vmax/Km, PopPK, PBPK, or observed clinical PK confirmation before higher-concentration extrapolation",
            ]
        )
    elif warning:
        status = "warning"
        recommended_actions.extend(
            [
                "Use outputs only for internal discussion",
                "Resolve missing evidence fields before CRO/regulatory-facing use",
                "Confirm safety threshold sources and calibration anchors",
            ]
        )
    else:
        status = "ok"
        recommended_actions.append("Use as internal exploratory input with documented assumptions")

    cmax_ratio = p95_cmax / reference_cmax_or_css if p95_cmax is not None and reference_cmax_or_css else None
    risk_light = "green"
    if status == "blocked_for_decision_use" or (reference_cmax_or_css and p95_cmax and p95_cmax > reference_cmax_or_css):
        risk_light = "red"
    elif status == "warning" or (reference_cmax_or_css and p95_cmax and p95_cmax > 0.5 * reference_cmax_or_css):
        risk_light = "yellow"

    return {
        "status": status,
        "risk_light": risk_light,
        "triggers": sorted(set(triggers)),
        "metrics": {
            "p95_cmax_ng_ml": p95_cmax,
            "reference_cmax_or_css_ng_ml": reference_cmax_or_css,
            "cmax_ratio": cmax_ratio,
            "p95_auc_ratio": p95_auc_ratio,
            "reference_auc_ng_h_ml": reference_auc,
            "terminal_followup_x_t_half": terminal_followup_x_t_half,
            "post_last_followup_h": post_last_followup_h,
            "dose_extrapolation_factor": dose_factor,
        },
        "known_formulation_gaps": known_gaps,
        "recommended_actions": recommended_actions,
    }


def run_exposure_simulation(
    compound_path: str | Path,
    reference_path: str | Path,
    product_path: str | Path,
    design_path: str | Path = "data/study_design.yaml",
    output_dir: str | Path = "outputs",
    n_simulations: int | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    compound = load_compound_profile(compound_path)
    reference = load_reference_pk(reference_path)
    product = read_yaml(product_path)
    design = read_yaml(design_path) if Path(design_path).exists() else {}
    sim_cfg = design.get("simulation", {})

    n = int(n_simulations or sim_cfg.get("n_simulations", 10000))
    seed = int(sim_cfg.get("random_seed", 20260512))
    dt = float(sim_cfg.get("time_step_h", 1.0))
    duration_h = float(sim_cfg.get("duration_h", product.get("treatment_duration_h", 336)))
    times = np.arange(0, duration_h + dt * 0.5, dt, dtype=float)

    pk = resolve_systemic_pk(compound, reference)
    elimination_assessment = assess_elimination_kinetics(compound, reference)
    elimination_model = elimination_assessment["model"]
    vmax_ng_h = to_float(compound.get("vmax_ng_h"), to_float(reference.get("vmax_ng_h")))
    km_ng_ml = to_float(compound.get("km_ng_ml"), to_float(reference.get("km_ng_ml")))
    dose_mg = float(product.get("dose_mg_per_application", 0.0))
    if dose_mg <= 0:
        raise ValueError("topical_product.yaml must define dose_mg_per_application > 0")
    tau_h = float(product.get("dosing_interval_h", 24.0))
    dosing_end_h = min(float(product.get("treatment_duration_h", duration_h)), duration_h)
    dose_times = np.arange(0, dosing_end_h, tau_h, dtype=float)
    if len(dose_times) == 0:
        dose_times = np.array([0.0])
    last_dose_h = float(dose_times[-1])
    is_multiple_dose = len(dose_times) > 1

    absorption_fraction_range = get_range(product, "absorption_fraction_range", (0.0001, 0.01))
    fast_absorption_assessment = assess_fast_absorption_need(compound, product)
    fast_absorption_enabled = bool(fast_absorption_assessment["enabled"])
    fast_absorption_fraction_range = get_range(product, "fast_absorption_fraction_range", (0.05, 0.35))
    ka_fast_range = get_range(product, "ka_fast_h_range", (0.4, 3.0))
    fast_lag_time_range = get_range(product, "fast_lag_time_h_range", (0.0, 2.0))
    deprecated: dict[str, Any] = {}
    if "early_apparent_volume_l_range" in product:
        deprecated["early_apparent_volume_l_range"] = {
            "value": product.get("early_apparent_volume_l_range"),
            "status": "unused_in_v1_1",
            "message": "V1.1 fast channel directly enters the central compartment; early apparent volume is retained only for backwards-compatible input parsing.",
        }
    if "local_to_central_half_life_h_range" in product:
        deprecated["local_to_central_half_life_h_range"] = {
            "value": product.get("local_to_central_half_life_h_range"),
            "status": "merged_into_depot_context",
        }
    ka_skin_range = get_range(product, "ka_skin_h_range", (0.02, 0.25))
    depot_half_life_range = get_range(product, "depot_half_life_h_range", (6.0, 72.0))
    lag_time_range = get_range(product, "lag_time_h_range", (0.0, 12.0))
    variability = _resolve_variability(product)
    interindividual_cv = float(variability["interindividual_cv"])
    bioavailability_cv = float(variability["bioavailability_cv"])
    calibration = _calibration_assessment(product, absorption_fraction_range)

    rng = np.random.default_rng(seed)
    conc_matrix = np.zeros((n, len(times)), dtype=float)
    draws: list[dict[str, float]] = []

    for sim_idx in range(n):
        concentration, draw = _simulate_one(
            rng,
            times,
            dose_times,
            dose_mg,
            pk.ke_h,
            pk.volume_l,
            elimination_model,
            vmax_ng_h,
            km_ng_ml,
            absorption_fraction_range,
            fast_absorption_fraction_range,
            ka_fast_range,
            fast_lag_time_range,
            ka_skin_range,
            depot_half_life_range,
            lag_time_range,
            interindividual_cv,
            bioavailability_cv,
            fast_absorption_enabled,
        )
        conc_matrix[sim_idx, :] = concentration
        draw["simulation_id"] = sim_idx + 1
        draws.append(draw)

    summary_df = pd.DataFrame(
        {
            "time_h": times,
            "concentration_p5_ng_ml": np.quantile(conc_matrix, 0.05, axis=0),
            "concentration_p50_ng_ml": np.quantile(conc_matrix, 0.50, axis=0),
            "concentration_p95_ng_ml": np.quantile(conc_matrix, 0.95, axis=0),
            "concentration_mean_ng_ml": np.mean(conc_matrix, axis=0),
            "lloq_ng_ml": pk.lloq_ng_ml,
        }
    )

    steady_state = effective_steady_state_times(
        pk.half_life_h,
        depot_half_life_h=depot_half_life_range[1],
        fast_absorption_half_life_h=(math.log(2) / ka_fast_range[0] if fast_absorption_enabled and ka_fast_range[0] > 0 else None),
    )
    fast_ss = effective_steady_state_times(math.log(2) / ka_fast_range[0]) if ka_fast_range[0] > 0 else {}
    depot_ss = effective_steady_state_times(depot_half_life_range[1]) if depot_half_life_range[1] > 0 else {}

    metrics: list[dict[str, Any]] = []
    first_interval = times <= min(tau_h, duration_h)
    ss_interval = (times >= last_dose_h) & (times <= min(last_dose_h + tau_h, duration_h))
    if not np.any(ss_interval):
        ss_interval = times >= max(0.0, duration_h - tau_h)
    predose_indices = [int(np.searchsorted(times, t)) for t in dose_times[1:] if t <= times[-1]]

    for idx in range(n):
        conc = conc_matrix[idx, :]
        cmax_global = float(np.max(conc))
        t_at_global_cmax = float(times[int(np.argmax(conc))])
        auc0t = trapezoid_auc(times, conc)
        clast = float(conc[-1])
        auc0inf = auc0t + (clast / pk.ke_h if pk.ke_h > 0 else 0.0)
        auc_extrap_pct = float(((auc0inf - auc0t) / auc0inf * 100.0) if auc0inf > 0 else 0.0)
        cavg = auc0t / duration_h if duration_h > 0 else 0.0
        ss_times = times[ss_interval]
        ss_conc = conc[ss_interval]
        cmax_ss = float(np.max(ss_conc)) if len(ss_conc) else cmax_global
        ctrough = float(np.min(ss_conc)) if len(ss_conc) else clast
        auc_tau_ss = interval_auc(times, conc, last_dose_h, min(last_dose_h + tau_h, duration_h)) if is_multiple_dose else np.nan
        auc_post_last = interval_auc(times, conc, last_dose_h, duration_h) + (clast / pk.ke_h if pk.ke_h > 0 else 0.0)
        first_cmax = float(np.max(conc[first_interval])) if np.any(first_interval) else cmax_global
        rac = cmax_ss / first_cmax if first_cmax > 0 else 1.0
        predose_positive = bool(predose_indices and pk.lloq_ng_ml > 0 and np.any(conc[predose_indices] > pk.lloq_ng_ml))
        draw = draws[idx]
        metrics.append(
            {
                "simulation_id": idx + 1,
                "cmax_ng_ml": cmax_global,
                "tmax_h": t_at_global_cmax,
                "auc0_t_ng_h_ml": auc0t,
                "auc0_inf_ng_h_ml": auc0inf,
                "auc_extrap_pct": auc_extrap_pct,
                "auc_tau_ss_ng_h_ml": auc_tau_ss,
                "auc_0_t_studyend_ng_h_ml": auc0t,
                "auc_post_last_dose_to_inf_ng_h_ml": auc_post_last,
                "cmax_ss_per_cycle_ng_ml": cmax_ss,
                "cmax_global_ng_ml": cmax_global,
                "t_at_global_cmax_h": t_at_global_cmax,
                "cavg_ng_ml": cavg,
                "ctrough_ng_ml": ctrough,
                "rac": rac,
                "terminal_concentration_ng_ml": clast,
                "time_to_90pct_steady_state_h": steady_state["t_ss_90_h"],
                "time_to_95pct_steady_state_h": steady_state["t_ss_95_h"],
                "predose_gt_lloq": predose_positive,
                "auc_ratio_reference": auc0t / pk.reference_auc_ng_h_ml if pk.reference_auc_ng_h_ml else np.nan,
                "cmax_ratio_reference": cmax_global / pk.reference_cmax_ng_ml if pk.reference_cmax_ng_ml else np.nan,
                "f_topical": draw["f_topical"],
                "fast_absorption_fraction": draw["fast_absorption_fraction"],
                "ka_fast_h": draw["ka_fast_h"],
                "fast_lag_time_h": draw["fast_lag_time_h"],
                "ka_skin_h": draw["ka_skin_h"],
                "depot_half_life_h": draw["depot_half_life_h"],
                "lag_time_h": draw["lag_time_h"],
            }
        )

    metrics_df = pd.DataFrame(metrics)
    metric_columns = [
        "cmax_ng_ml",
        "tmax_h",
        "auc0_t_ng_h_ml",
        "cavg_ng_ml",
        "ctrough_ng_ml",
        "rac",
        "terminal_concentration_ng_ml",
        "auc_ratio_reference",
        "cmax_ratio_reference",
        "f_topical",
        "fast_absorption_fraction",
        "time_to_90pct_steady_state_h",
        "time_to_95pct_steady_state_h",
        "auc_tau_ss_ng_h_ml",
        "auc_0_t_studyend_ng_h_ml",
        "auc_post_last_dose_to_inf_ng_h_ml",
        "cmax_ss_per_cycle_ng_ml",
        "cmax_global_ng_ml",
        "t_at_global_cmax_h",
    ]
    if not is_multiple_dose:
        metric_columns.extend(["auc0_inf_ng_h_ml", "auc_extrap_pct"])
    metric_quantiles = {
        column: _metric_quantiles(metrics_df[column].dropna())
        for column in metric_columns
        if column in metrics_df and not metrics_df[column].dropna().empty
    }

    risk_summary = {
        "predose_gt_lloq_probability": float(metrics_df["predose_gt_lloq"].mean()),
    }
    if not is_multiple_dose:
        risk_summary["auc_extrap_gt_20_probability"] = float((metrics_df["auc_extrap_pct"] > 20).mean())
    if pk.safety_cmax_ng_ml is not None:
        risk_summary["cmax_gt_safety_threshold_probability"] = float((metrics_df["cmax_global_ng_ml"] > pk.safety_cmax_ng_ml).mean())
    if pk.safety_auc_ng_h_ml is not None:
        risk_summary["auc_gt_safety_threshold_probability"] = float((metrics_df["auc_0_t_studyend_ng_h_ml"] > pk.safety_auc_ng_h_ml).mean())

    known = _load_known_formulations(product_path)
    known_gaps = _known_formulation_gaps(known, pk.half_life_h)
    decision_gate = _build_decision_gate(
        elimination_assessment=elimination_assessment,
        metric_quantiles=metric_quantiles,
        pk_reference_cmax=pk.reference_cmax_ng_ml,
        pk_reference_auc=pk.reference_auc_ng_h_ml,
        safety_cmax=pk.safety_cmax_ng_ml,
        safety_auc=pk.safety_auc_ng_h_ml,
        compound=compound,
        duration_h=duration_h,
        last_dose_h=last_dose_h,
        half_life_h=pk.half_life_h,
        known_gaps=known_gaps,
        calibration=calibration,
        product=product,
    )

    provenance_path = _write_parameter_provenance(
        output,
        compound,
        reference,
        product,
        {
            "half_life_h": pk.half_life_h,
            "volume_l": pk.volume_l,
            "clearance_l_h": pk.clearance_l_h,
            "reference_auc_ng_h_ml": pk.reference_auc_ng_h_ml,
            "reference_cmax_ng_ml": pk.reference_cmax_ng_ml,
            "safety_cmax_ng_ml": pk.safety_cmax_ng_ml,
            "safety_auc_ng_h_ml": pk.safety_auc_ng_h_ml,
        },
        variability,
    )
    dose_sensitivity_path = _write_dose_sensitivity(output, product, metrics_df)

    simulation_summary = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "compound": {
            "compound_id": str(compound.get("compound_id", "")),
            "compound_name": str(compound.get("compound_name", "")),
            "molecular_weight": compound.get("molecular_weight"),
            "xlogp": compound.get("xlogp"),
            "value_source": str(compound.get("value_source", "")),
            "safety_cmax_source": str(compound.get("safety_cmax_source", "")),
            "safety_auc_source": str(compound.get("safety_auc_source", "")),
            "safety_threshold_interpretation": str(compound.get("safety_threshold_interpretation", "")),
        },
        "product": {
            "product_name": str(product.get("product_name", "")),
            "formulation": str(product.get("formulation", "")),
            "concentration_percent_w_w": product.get("concentration_percent_w_w"),
            "daily_amount_g": product.get("daily_amount_g"),
            "treated_area_cm2": product.get("treated_area_cm2"),
            "skin_condition": str(product.get("skin_condition", "")),
            "max_use_condition": str(product.get("max_use_condition", "")),
            "variability": variability,
        },
        "n_simulations": n,
        "duration_h": duration_h,
        "time_step_h": dt,
        "dosing_interval_h": tau_h,
        "dose_mg_per_application": dose_mg,
        "dosing_times_h": dose_times.tolist(),
        "is_multiple_dose": is_multiple_dose,
        "systemic_pk": {
            "half_life_h": pk.half_life_h,
            "ke_h": pk.ke_h,
            "volume_l": pk.volume_l,
            "clearance_l_h": pk.clearance_l_h,
            "lloq_ng_ml": pk.lloq_ng_ml,
            "reference_auc_ng_h_ml": pk.reference_auc_ng_h_ml,
            "reference_cmax_ng_ml": pk.reference_cmax_ng_ml,
            "safety_cmax_ng_ml": pk.safety_cmax_ng_ml,
            "safety_auc_ng_h_ml": pk.safety_auc_ng_h_ml,
            "elimination_assessment": elimination_assessment,
            "steady_state_assessment": {
                **steady_state,
                "method": "t_half_eff = max(elimination half-life, slowest fast absorption half-life, depot release half-life)",
                "fast_channel": fast_ss,
                "depot_channel": depot_ss,
            },
            "warnings": list(pk.warnings),
        },
        "parameter_ranges": {
            "absorption_fraction_range": list(absorption_fraction_range),
            "fast_absorption_assessment": fast_absorption_assessment,
            "fast_absorption_fraction_range": list(fast_absorption_fraction_range),
            "ka_fast_h_range": list(ka_fast_range),
            "fast_lag_time_h_range": list(fast_lag_time_range),
            "ka_skin_h_range": list(ka_skin_range),
            "depot_half_life_h_range": list(depot_half_life_range),
            "lag_time_h_range": list(lag_time_range),
            "deprecated_fields": deprecated,
        },
        "calibration_assessment": calibration,
        "known_formulation_gaps": known_gaps,
        "metric_quantiles": metric_quantiles,
        "risk_summary": risk_summary,
        "decision_gate": decision_gate,
        "output_files": {
            "parameter_provenance": str(provenance_path),
            "dose_extrapolation_sensitivity": str(dose_sensitivity_path),
        },
        "interpretation_boundary": "本工具是早期外用制剂系统暴露与采血点设计的内部探索性沙盘工具；不替代 MUsT/max-use PK、BE、PopPK 或 PBPK。",
    }

    summary_path = output / "simulation_results.csv"
    metrics_path = output / "simulation_metrics.csv"
    json_path = output / "simulation_summary.json"
    summary_df.to_csv(summary_path, index=False)
    metrics_df.to_csv(metrics_path, index=False)
    write_json(json_path, simulation_summary)

    return {
        "simulation_results": summary_path,
        "simulation_metrics": metrics_path,
        "simulation_summary": json_path,
        "parameter_provenance": provenance_path,
        "dose_extrapolation_sensitivity": dose_sensitivity_path,
        "n_simulations": n,
        "warnings": list(pk.warnings),
        "decision_gate": decision_gate,
    }
