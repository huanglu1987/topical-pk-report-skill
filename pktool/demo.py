from __future__ import annotations

from pathlib import Path

from .io_utils import ensure_dir, write_csv_rows, write_yaml


def _write_if_allowed(path: Path, writer, force: bool) -> bool:
    if path.exists() and not force:
        return False
    writer(path)
    return True


def init_demo(base_dir: str | Path = ".", force: bool = False) -> list[Path]:
    root = Path(base_dir)
    data_dir = ensure_dir(root / "data")
    ensure_dir(data_dir / "evidence_cache")
    ensure_dir(root / "outputs")

    created: list[Path] = []

    compound_path = data_dir / "compound_profile.csv"

    def write_compound(path: Path) -> None:
        write_csv_rows(
            path,
            [
                {
                    "compound_id": "DEMO-001",
                    "compound_name": "Demo topical small molecule",
                    "molecular_weight": 875.1,
                    "xlogp": 5.8,
                    "tpsa": 170.0,
                    "hbd": 3,
                    "hba": 14,
                    "half_life_h": 36,
                    "clearance_l_h": "",
                    "volume_l": 250,
                    "lloq_ng_ml": 0.05,
                    "safety_cmax_ng_ml": 5,
                    "safety_auc_ng_h_ml": 400,
                    "value_source": "illustrative_default",
                    "notes": "示例参数，仅用于工具演示，不可直接用于申报或真实研究决策。",
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
                "value_source",
                "notes",
            ],
        )

    if _write_if_allowed(compound_path, write_compound, force):
        created.append(compound_path)

    reference_path = data_dir / "reference_pk.csv"

    def write_reference(path: Path) -> None:
        write_csv_rows(
            path,
            [
                {"parameter": "reference_dose_mg", "value": 12, "unit": "mg", "source": "illustrative", "used_for_model": "no"},
                {"parameter": "reference_auc_ng_h_ml", "value": 120, "unit": "ng*h/mL", "source": "illustrative", "used_for_model": "comparison_only"},
                {"parameter": "reference_cmax_ng_ml", "value": 3.5, "unit": "ng/mL", "source": "illustrative", "used_for_model": "comparison_only"},
                {"parameter": "half_life_h", "value": 36, "unit": "h", "source": "compound_profile", "used_for_model": "yes"},
                {"parameter": "volume_l", "value": 250, "unit": "L", "source": "compound_profile", "used_for_model": "yes"},
                {"parameter": "clearance_l_h", "value": "", "unit": "L/h", "source": "missing", "used_for_model": "no"},
            ],
            ["parameter", "value", "unit", "source", "used_for_model"],
        )

    if _write_if_allowed(reference_path, write_reference, force):
        created.append(reference_path)

    product_path = data_dir / "topical_product.yaml"

    def write_product(path: Path) -> None:
        write_yaml(
            path,
            {
                "product_name": "Demo 1% topical cream",
                "formulation": "cream",
                "concentration_percent_w_w": 1.0,
                "daily_amount_g": 1.0,
                "dose_mg_per_application": 10.0,
                "applications_per_day": 1,
                "dosing_interval_h": 24,
                "treatment_duration_h": 336,
                "treated_area_cm2": 600,
                "max_use_condition": "illustrative maximum-use assumption",
                "occlusion": False,
                "skin_condition": "affected skin",
                "absorption_fraction_range": [0.0001, 0.02],
                "ka_skin_h_range": [0.02, 0.35],
                "depot_half_life_h_range": [6, 96],
                "lag_time_h_range": [0, 12],
                "interindividual_cv": 0.6,
                "bioavailability_cv": 0.5,
                "notes": "外用吸收区间为示例假设；真实项目需由 IVRT/IVPT、探索 PK 或同类案例校准。",
            },
        )

    if _write_if_allowed(product_path, write_product, force):
        created.append(product_path)

    design_path = data_dir / "study_design.yaml"

    def write_design(path: Path) -> None:
        write_yaml(
            path,
            {
                "simulation": {
                    "n_simulations": 1000,
                    "random_seed": 20260512,
                    "time_step_h": 1,
                    "duration_h": 336,
                },
                "candidate_sampling_hours": [
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
                ],
                "sampling": {
                    "max_recommended_points": 14,
                    "notes": "候选采血点可按中心操作可行性调整。",
                },
            },
        )

    if _write_if_allowed(design_path, write_design, force):
        created.append(design_path)

    return created

