from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .evidence import fetch_cde_sources, fetch_fda_label, fetch_pubchem
from .io_utils import ensure_dir, to_float, write_csv_rows, write_json, write_yaml, read_yaml
from .report import generate_report
from .sampling import recommend_sampling
from .simulation import run_exposure_simulation


DEFAULT_CANDIDATE_SAMPLING_HOURS = [
    0,
    1,
    2,
    4,
    6,
    8,
    12,
    16,
    24,
    36,
    48,
    72,
    96,
    120,
    168,
    216,
    240,
    264,
    288,
    312,
    336,
    408,
    504,
    672,
    1008,
    1344,
    1680,
    2016,
]

KNOWN_FORMULATION_FIELDS = [
    "name",
    "route",
    "formulation",
    "dose_mg",
    "dose_description",
    "single_or_multiple",
    "cmax_ng_ml",
    "tmax_h",
    "auc_ng_h_ml",
    "auc0_t_ng_h_ml",
    "auc0_inf_ng_h_ml",
    "half_life_h",
    "clearance_l_h",
    "volume_l",
    "fraction_unbound",
    "metabolism_pathway",
    "active_metabolite",
    "dose_proportionality",
    "linear_dose_range_mg",
    "tmax_sd_h",
    "tmax_range_h",
    "cmax_cv",
    "auc_cv",
    "accumulation_ratio",
    "time_to_ss_h",
    "washout_duration_h",
    "blq_time_h",
    "lloq_method",
    "population",
    "food_effect",
    "formulation_excipients",
    "vehicle",
    "permeation_data",
    "protein_binding_concentration_dependence",
    "species",
    "accumulation_kinetics_in_skin",
    "source",
    "primary_comparator",
    "notes",
]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "_", value.strip())
    return cleaned.strip("_")[:80] or "topical_pk"


def _get(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    return mapping.get(key, default)


def _nested(source: dict[str, Any], *keys: str) -> dict[str, Any]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _known_formulations(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("known_formulations", "known_formulations_pk", "prior_formulations_pk"):
        value = input_data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _selected_reference(known: list[dict[str, Any]]) -> dict[str, Any]:
    if not known:
        return {}

    def score(item: dict[str, Any]) -> tuple[int, int, int, int]:
        route = str(item.get("route", "")).lower()
        non_topical = 0 if route in {"topical", "dermal", "cutaneous", "外用", "局部外用"} else 1
        exposure_fields = sum(
            1
            for key in ("auc_ng_h_ml", "auc0_t_ng_h_ml", "auc0_inf_ng_h_ml", "cmax_ng_ml", "half_life_h")
            if to_float(item.get(key)) is not None
        )
        primary = 1 if item.get("primary_comparator") else 0
        systemic_route = 1 if route in {"oral", "iv", "intravenous", "subcutaneous", "口服", "静脉", "皮下"} else 0
        return primary, non_topical, exposure_fields, systemic_route

    return sorted(known, key=score, reverse=True)[0]


def _fallback_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return ""


def _reference_auc(reference: dict[str, Any], selected: dict[str, Any]) -> Any:
    return _fallback_value(
        reference.get("reference_auc_ng_h_ml"),
        selected.get("auc_ng_h_ml"),
        selected.get("auc0_t_ng_h_ml"),
        selected.get("auc0_inf_ng_h_ml"),
    )


def _dose_mg_per_application(product: dict[str, Any]) -> float:
    dose = to_float(product.get("dose_mg_per_application"))
    if dose is not None and dose > 0:
        return dose

    concentration = to_float(product.get("concentration_percent_w_w"))
    if concentration is None:
        concentration = to_float(product.get("concentration_percent"))
    daily_amount_g = to_float(product.get("daily_amount_g"))
    applications_per_day = to_float(product.get("applications_per_day"), 1.0) or 1.0
    if concentration is None or daily_amount_g is None:
        raise ValueError("缺少 dose_mg_per_application，且无法由 concentration_percent_w_w + daily_amount_g 推算。")
    amount_per_application_g = daily_amount_g / applications_per_day
    return concentration * 10.0 * amount_per_application_g


def _normalize_optional_range(value: Any) -> Any:
    if isinstance(value, (list, tuple)) and len(value) == 2 and value[0] not in (None, "") and value[1] not in (None, ""):
        return [float(value[0]), float(value[1])]
    return None


def _default_absorption_range(compound: dict[str, Any], product: dict[str, Any]) -> list[float]:
    explicit = product.get("absorption_fraction_range")
    if isinstance(explicit, list) and len(explicit) == 2:
        return [float(explicit[0]), float(explicit[1])]

    mw = to_float(compound.get("molecular_weight"))
    xlogp = to_float(compound.get("xlogp"))
    if mw is not None and mw >= 700:
        return [0.00005, 0.005]
    if xlogp is not None and xlogp >= 5:
        return [0.00005, 0.01]
    return [0.0001, 0.02]


def write_input_files(
    input_data: dict[str, Any],
    run_dir: str | Path,
    purpose_override: str | None = None,
    variability_preset_override: str | None = None,
) -> dict[str, Path]:
    run_dir = Path(run_dir)
    data_dir = ensure_dir(run_dir / "data")

    project = _nested(input_data, "project")
    compound = _nested(input_data, "compound", "molecule")
    product = _nested(input_data, "product", "topical_product")
    reference = _nested(input_data, "reference_pk", "reference")
    study = _nested(input_data, "study_design", "study")
    known = _known_formulations(input_data)
    selected_reference = _selected_reference(known)

    compound_name = str(compound.get("compound_name") or compound.get("name") or project.get("compound_name") or "Unknown compound")
    product_name = str(product.get("product_name") or project.get("product_name") or f"{compound_name} topical product")

    compound_path = data_dir / "compound_profile.csv"
    write_csv_rows(
        compound_path,
        [
            {
                "compound_id": compound.get("compound_id", "AUTO-001"),
                "compound_name": compound_name,
                "molecular_weight": compound.get("molecular_weight", ""),
                "xlogp": compound.get("xlogp", ""),
                "tpsa": compound.get("tpsa", ""),
                "hbd": compound.get("hbd", ""),
                "hba": compound.get("hba", ""),
                "half_life_h": _fallback_value(compound.get("half_life_h"), reference.get("half_life_h"), selected_reference.get("half_life_h")),
                "clearance_l_h": _fallback_value(compound.get("clearance_l_h"), reference.get("clearance_l_h"), selected_reference.get("clearance_l_h")),
                "volume_l": _fallback_value(compound.get("volume_l"), reference.get("volume_l"), selected_reference.get("volume_l")),
                "lloq_ng_ml": compound.get("lloq_ng_ml", study.get("lloq_ng_ml", 0)),
                "safety_cmax_ng_ml": compound.get("safety_cmax_ng_ml", study.get("safety_cmax_ng_ml", "")),
                "safety_auc_ng_h_ml": compound.get("safety_auc_ng_h_ml", study.get("safety_auc_ng_h_ml", "")),
                "safety_cmax_source": compound.get("safety_cmax_source", study.get("safety_cmax_source", "")),
                "safety_auc_source": compound.get("safety_auc_source", study.get("safety_auc_source", "")),
                "safety_threshold_interpretation": compound.get("safety_threshold_interpretation", study.get("safety_threshold_interpretation", "")),
                "elimination_model": compound.get("elimination_model", "auto"),
                "vmax_ng_h": compound.get("vmax_ng_h", ""),
                "km_ng_ml": compound.get("km_ng_ml", ""),
                "elimination_notes": compound.get("elimination_notes", ""),
                "value_source": compound.get("value_source", "user_basic_input"),
                "notes": compound.get("notes", "由一键输入模板生成；真实 PK 参数需人工确认。"),
            }
        ],
        [
            "compound_id",
            "compound_name",
            "molecular_weight",
            "xlogp",
            "tpsa",
            "hbd",
            "hba",
            "half_life_h",
            "clearance_l_h",
            "volume_l",
            "lloq_ng_ml",
            "safety_cmax_ng_ml",
            "safety_auc_ng_h_ml",
            "safety_cmax_source",
            "safety_auc_source",
            "safety_threshold_interpretation",
            "elimination_model",
            "vmax_ng_h",
            "km_ng_ml",
            "elimination_notes",
            "value_source",
            "notes",
        ],
    )

    known_path = data_dir / "known_formulations_pk.csv"
    write_csv_rows(
        known_path,
        [{field: item.get(field, "") for field in KNOWN_FORMULATION_FIELDS} for item in known],
        KNOWN_FORMULATION_FIELDS,
    )

    reference_path = data_dir / "reference_pk.csv"
    reference_source = _fallback_value(reference.get("source"), selected_reference.get("source"), "known_formulations_or_user_input")
    reference_rows = [
        ("reference_dose_mg", _fallback_value(reference.get("reference_dose_mg"), selected_reference.get("dose_mg")), "mg", reference_source, "comparison_only"),
        ("reference_auc_ng_h_ml", _reference_auc(reference, selected_reference), "ng*h/mL", reference_source, "comparison_only"),
        ("reference_cmax_ng_ml", _fallback_value(reference.get("reference_cmax_ng_ml"), selected_reference.get("cmax_ng_ml")), "ng/mL", reference_source, "comparison_only"),
        ("half_life_h", _fallback_value(compound.get("half_life_h"), reference.get("half_life_h"), selected_reference.get("half_life_h")), "h", reference_source, "yes"),
        ("volume_l", _fallback_value(compound.get("volume_l"), reference.get("volume_l"), selected_reference.get("volume_l")), "L", reference_source, "yes"),
        ("clearance_l_h", _fallback_value(compound.get("clearance_l_h"), reference.get("clearance_l_h"), selected_reference.get("clearance_l_h")), "L/h", reference_source, "yes"),
        ("primary_reference_name", selected_reference.get("name", ""), "", reference_source, "evidence_context"),
        ("primary_reference_route", selected_reference.get("route", ""), "", reference_source, "evidence_context"),
        ("primary_reference_formulation", selected_reference.get("formulation", ""), "", reference_source, "evidence_context"),
    ]
    write_csv_rows(
        reference_path,
        [
            {"parameter": parameter, "value": value, "unit": unit, "source": source, "used_for_model": used}
            for parameter, value, unit, source, used in reference_rows
        ],
        ["parameter", "value", "unit", "source", "used_for_model"],
    )

    dose_mg = _dose_mg_per_application(product)
    applications_per_day = int(to_float(product.get("applications_per_day"), 1) or 1)
    dosing_interval_h = float(product.get("dosing_interval_h") or 24 / applications_per_day)
    simulation_duration_h = float(study.get("duration_h") or product.get("simulation_duration_h") or product.get("treatment_duration_h") or 336)
    treatment_duration_h = float(product.get("treatment_duration_h") or study.get("dosing_duration_h") or simulation_duration_h)

    product_path = data_dir / "topical_product.yaml"
    write_yaml(
        product_path,
        {
            "product_name": product_name,
            "formulation": product.get("formulation", "cream"),
            "concentration_percent_w_w": product.get("concentration_percent_w_w", product.get("concentration_percent", "")),
            "daily_amount_g": product.get("daily_amount_g", ""),
            "dose_mg_per_application": dose_mg,
            "applications_per_day": applications_per_day,
            "dosing_interval_h": dosing_interval_h,
            "treatment_duration_h": treatment_duration_h,
            "treated_area_cm2": product.get("treated_area_cm2", ""),
            "max_use_condition": product.get("max_use_condition", "用户输入的最大使用条件或常规用药条件"),
            "occlusion": bool(product.get("occlusion", False)),
            "skin_condition": product.get("skin_condition", "affected skin"),
            "vehicle": product.get("vehicle", ""),
            "formulation_excipients": product.get("formulation_excipients", ""),
            "absorption_fraction_range": _default_absorption_range(compound, product),
            "ka_skin_h_range": product.get("ka_skin_h_range", [0.02, 0.35]),
            "depot_half_life_h_range": product.get("depot_half_life_h_range", [6, 96]),
            "lag_time_h_range": product.get("lag_time_h_range", [0, 12]),
            "enable_fast_absorption": product.get("enable_fast_absorption", "auto"),
            "fast_absorption_evidence": product.get("fast_absorption_evidence", {}),
            "fast_absorption_fraction_range": _normalize_optional_range(product.get("fast_absorption_fraction_range")) or [0.05, 0.35],
            "ka_fast_h_range": _normalize_optional_range(product.get("ka_fast_h_range")) or [0.4, 3.0],
            "fast_lag_time_h_range": _normalize_optional_range(product.get("fast_lag_time_h_range")) or [0, 2],
            "early_apparent_volume_l_range": _normalize_optional_range(product.get("early_apparent_volume_l_range")) or [0.5, 20],
            "local_to_central_half_life_h_range": _normalize_optional_range(product.get("local_to_central_half_life_h_range")) or [4, 48],
            "variability_preset": variability_preset_override or product.get("variability_preset", "medium"),
            "interindividual_cv": product.get("interindividual_cv", ""),
            "bioavailability_cv": product.get("bioavailability_cv", ""),
            "calibration_reference": input_data.get("calibration_reference", product.get("calibration_reference", {})),
            "notes": product.get("notes", "由基础品种信息自动生成；吸收参数为保守默认范围，建议用 IVRT/IVPT 或探索性 PK 校准。"),
        },
    )

    design_path = data_dir / "study_design.yaml"
    write_yaml(
        design_path,
        {
            "simulation": {
                "n_simulations": int(study.get("n_simulations", 10000)),
                "random_seed": int(study.get("random_seed", 20260512)),
                "time_step_h": float(study.get("time_step_h", 1)),
                "duration_h": simulation_duration_h,
            },
            "purpose": purpose_override or study.get("purpose", "exploratory"),
            "sampling_purposes": study.get("sampling_purposes", [purpose_override] if purpose_override else ["exploratory", "must_max_use", "be_bridging"]),
            "candidate_sampling_hours": study.get("candidate_sampling_hours", DEFAULT_CANDIDATE_SAMPLING_HOURS),
            "sampling": {
                "max_recommended_points": int(study.get("max_recommended_points", 14)),
                "notes": study.get("sampling_notes", "自动生成候选采血点，可按中心操作可行性调整。"),
            },
        },
    )

    write_json(run_dir / "input_snapshot.json", input_data)
    return {
        "compound": compound_path,
        "reference": reference_path,
        "known_formulations": known_path,
        "product": product_path,
        "design": design_path,
    }


def run_from_basic_input(
    input_path: str | Path,
    output_root: str | Path = "runs",
    fetch_evidence: bool = True,
    purpose: str | None = None,
    variability_preset: str | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    input_data = read_yaml(input_path)
    project = _nested(input_data, "project")
    compound = _nested(input_data, "compound", "molecule")
    evidence_cfg = _nested(input_data, "evidence")

    compound_name = str(compound.get("compound_name") or compound.get("name") or project.get("compound_name") or input_path.stem)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ensure_dir(Path(output_root) / f"{timestamp}_{_slug(compound_name)}")
    paths = write_input_files(input_data, run_dir, purpose_override=purpose, variability_preset_override=variability_preset)

    evidence_dir = ensure_dir(run_dir / "data/evidence_cache")
    if fetch_evidence:
        if evidence_cfg.get("pubchem", True):
            fetch_pubchem(compound_name, output_dir=evidence_dir)
        if evidence_cfg.get("fda", True):
            fetch_fda_label(str(evidence_cfg.get("fda_ingredient") or compound_name), output_dir=evidence_dir)
        if evidence_cfg.get("cde", True):
            fetch_cde_sources(str(evidence_cfg.get("cde_keyword") or "药代动力学"), output_dir=evidence_dir, url=evidence_cfg.get("cde_url"))

    outputs_dir = ensure_dir(run_dir / "outputs")
    sim_result = run_exposure_simulation(
        compound_path=paths["compound"],
        reference_path=paths["reference"],
        product_path=paths["product"],
        design_path=paths["design"],
        output_dir=outputs_dir,
    )
    sampling_path = recommend_sampling(
        simulation_path=sim_result["simulation_results"],
        design_path=paths["design"],
        output_path=outputs_dir / "sampling_recommendation.csv",
    )
    reports = generate_report(
        simulation_path=sim_result["simulation_results"],
        metrics_path=sim_result["simulation_metrics"],
        sampling_path=sampling_path,
        evidence_manifest_path=evidence_dir / "evidence_manifest.csv",
        formats=str(input_data.get("report", {}).get("format", "md,xlsx")) if isinstance(input_data.get("report"), dict) else "md,xlsx",
        reports_dir=outputs_dir / "reports",
    )

    return {
        "run_dir": run_dir,
        "input_files": paths,
        "simulation": sim_result,
        "sampling": sampling_path,
        "reports": reports,
    }
