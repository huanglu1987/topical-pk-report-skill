import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

from pktool.demo import init_demo
from pktool.one_click import run_from_basic_input
from pktool.sampling import recommend_sampling
from pktool.simulation import assess_elimination_kinetics, run_exposure_simulation


class TestSimulation(unittest.TestCase):
    def test_demo_simulation_outputs_non_negative_quantiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_demo(root)
            result = run_exposure_simulation(
                root / "data/compound_profile.csv",
                root / "data/reference_pk.csv",
                root / "data/topical_product.yaml",
                design_path=root / "data/study_design.yaml",
                output_dir=root / "outputs",
                n_simulations=30,
            )
            sim = pd.read_csv(result["simulation_results"])
            self.assertIn("concentration_p50_ng_ml", sim.columns)
            self.assertTrue((sim["concentration_p5_ng_ml"] >= 0).all())
            self.assertTrue((sim["concentration_p95_ng_ml"] >= sim["concentration_p5_ng_ml"]).all())

    def test_sampling_recommendation_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_demo(root)
            run_exposure_simulation(
                root / "data/compound_profile.csv",
                root / "data/reference_pk.csv",
                root / "data/topical_product.yaml",
                design_path=root / "data/study_design.yaml",
                output_dir=root / "outputs",
                n_simulations=20,
            )
            output = recommend_sampling(
                root / "outputs/simulation_results.csv",
                design_path=root / "data/study_design.yaml",
                output_path=root / "outputs/sampling_recommendation.csv",
            )
            rec = pd.read_csv(output)
            self.assertIn("recommended", rec.columns)
            self.assertGreater(rec["recommended"].sum(), 0)

    def test_one_click_uses_known_formulation_as_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "basic.yaml"
            input_path.write_text(
                yaml.safe_dump(
                    {
                        "project": {"compound_name": "demo", "product_name": "demo cream"},
                        "compound": {"compound_name": "demo", "molecular_weight": 300, "lloq_ng_ml": 0.1},
                        "known_formulations": [
                            {
                                "name": "oral anchor",
                                "route": "oral",
                                "formulation": "tablet",
                                "dose_mg": 10,
                                "cmax_ng_ml": 2,
                                "auc_ng_h_ml": 80,
                                "half_life_h": 8,
                                "volume_l": 100,
                                "source": "test",
                                "primary_comparator": True,
                            }
                        ],
                        "product": {
                            "formulation": "cream",
                            "concentration_percent_w_w": 1,
                            "daily_amount_g": 1,
                            "applications_per_day": 1,
                        },
                        "study_design": {"n_simulations": 10, "duration_h": 48},
                        "evidence": {"pubchem": False, "fda": False, "cde": False},
                    },
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            result = run_from_basic_input(input_path, output_root=root / "runs", fetch_evidence=False)
            reference = pd.read_csv(result["input_files"]["reference"])
            self.assertIn("primary_reference_name", set(reference["parameter"]))
            auc_row = reference[reference["parameter"] == "reference_auc_ng_h_ml"].iloc[0]
            self.assertEqual(float(auc_row["value"]), 80)

    def test_elimination_nonlinear_note_without_vmax_defaults_first_order(self):
        assessment = assess_elimination_kinetics(
            {"half_life_h": 840, "elimination_notes": "dose/concentration-dependent elimination", "vmax_ng_h": float("nan"), "km_ng_ml": float("nan")},
            {},
        )
        self.assertEqual(assessment["model"], "first_order")
        self.assertTrue(assessment["nonlinear_flag"])

    def test_minimal_dosing_scenario_sets_default_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "single.yaml"
            base = {
                "compound": {"compound_name": "demo", "molecular_weight": 300},
                "product": {
                    "formulation": "spray",
                    "concentration_percent_w_w": 0.25,
                    "daily_amount_g": 1,
                    "applications_per_day": 1,
                },
                "study_design": {"dosing_scenario": "single", "n_simulations": 10},
                "evidence": {"pubchem": False, "fda": False, "cde": False},
            }
            input_path.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
            result = run_from_basic_input(input_path, output_root=root / "runs", fetch_evidence=False)
            product = yaml.safe_load(Path(result["input_files"]["product"]).read_text(encoding="utf-8"))
            self.assertEqual(product["dosing_scenario"], "single")
            self.assertEqual(product["treatment_duration_h"], 24.0)

            input_path = root / "multiple.yaml"
            base["study_design"] = {"dosing_scenario": "multiple", "n_simulations": 10}
            input_path.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
            result = run_from_basic_input(input_path, output_root=root / "runs2", fetch_evidence=False)
            product = yaml.safe_load(Path(result["input_files"]["product"]).read_text(encoding="utf-8"))
            design = yaml.safe_load(Path(result["input_files"]["design"]).read_text(encoding="utf-8"))
            self.assertEqual(product["dosing_scenario"], "multiple")
            self.assertEqual(product["treatment_duration_h"], 672.0)
            self.assertEqual(design["simulation"]["duration_h"], 840.0)


if __name__ == "__main__":
    unittest.main()
