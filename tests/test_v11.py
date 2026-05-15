import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import yaml

from pktool.one_click import run_from_basic_input
from pktool.sampling import recommend_sampling
from pktool.simulation import assess_fast_absorption_need


ROOT = Path(__file__).resolve().parents[1]


def _load_input(name: str) -> dict:
    return yaml.safe_load((ROOT / "data" / name).read_text(encoding="utf-8"))


def _run_input(data: dict, tmp: str) -> dict:
    data.setdefault("study_design", {})["n_simulations"] = 80
    input_path = Path(tmp) / "input.yaml"
    input_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return run_from_basic_input(input_path, output_root=Path(tmp) / "runs", fetch_evidence=False)


class TestV11Revision(unittest.TestCase):
    def test_gate_schema_shape(self):
        schema = json.loads((ROOT / "pktool/schemas/decision_gate.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["status"]["enum"], ["ok", "warning", "blocked_for_decision_use"])
        self.assertIn("metrics", schema["required"])

    def test_dutasteride_2pct_multiple_blocks_and_steady_state_is_formula_based(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_2pct_solution_multiple_input.yaml"), tmp)
            summary = json.loads(Path(result["simulation"]["simulation_summary"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["decision_gate"]["status"], "blocked_for_decision_use")
            self.assertIn("high_dose_extrapolation_with_nonlinear_signal", summary["decision_gate"]["triggers"])
            t90 = summary["systemic_pk"]["steady_state_assessment"]["t_ss_90_h"]
            self.assertGreaterEqual(t90, 2700)
            self.assertLessEqual(t90, 3300)
            report = Path(result["reports"][0]).read_text(encoding="utf-8")
            self.assertIn("DECISION GATE: BLOCKED FOR DECISION USE", report)

    def test_auc_naming_in_multiple_dose_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_1pct_solution_multiple_input.yaml"), tmp)
            summary = json.loads(Path(result["simulation"]["simulation_summary"]).read_text(encoding="utf-8"))
            metrics = summary["metric_quantiles"]
            self.assertIn("auc_tau_ss_ng_h_ml", metrics)
            self.assertIn("auc_0_t_studyend_ng_h_ml", metrics)
            self.assertNotIn("auc0_inf_ng_h_ml", metrics)

    def test_report_steady_state_sections_only_for_multiple_dose(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_1pct_solution_single_input.yaml"), tmp)
            report = Path(result["reports"][0]).read_text(encoding="utf-8")
            self.assertIn("## 3. 系统暴露预测", report)
            self.assertIn("### 3.1 暴露指标预测", report)
            self.assertNotIn("稳态时间口径", report)
            self.assertNotIn("不同给药频率下的稳态时间", report)
            self.assertNotIn("## 3.5", report)
            self.assertNotIn("## 3.6", report)

        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_1pct_solution_multiple_input.yaml"), tmp)
            report = Path(result["reports"][0]).read_text(encoding="utf-8")
            self.assertIn("## 3. 系统暴露预测", report)
            self.assertIn("### 3.1 暴露指标预测", report)
            self.assertIn("### 3.2 稳态时间口径", report)
            self.assertIn("### 3.3 不同给药频率下的稳态时间", report)
            exposure_table = report.split("### 3.2 稳态时间口径", 1)[0]
            self.assertNotIn("达到90%稳态时间", exposure_table)
            self.assertNotIn("## 3.5", report)
            self.assertNotIn("## 3.6", report)

    def test_fast_absorption_v2_threshold_and_gate(self):
        compound = {"molecular_weight": 528.5, "xlogp": 4.5, "lloq_ng_ml": 0.025}
        product = {
            "dose_mg_per_application": 1,
            "formulation": "cream",
            "enable_fast_absorption": "auto",
            "fast_absorption_evidence": {"observed_topical_tmax_h": 5, "observed_topical_cmax_ng_ml": 0.2},
        }
        assessment = assess_fast_absorption_need(compound, product)
        self.assertEqual(assessment["score"], 25)
        self.assertFalse(assessment["enabled"])
        self.assertEqual(assessment["level"], "insufficient")

        gated = assess_fast_absorption_need({**compound, "molecular_weight": 700}, {**product, "dose_mg_per_application": 20})
        self.assertFalse(gated["enabled"])
        self.assertIn("insufficient", gated["level"])

    def test_calibration_fail_triggers_gate(self):
        data = _load_input("dutasteride_1pct_solution_single_input.yaml")
        data["calibration_reference"]["observed_tmax_h"] = 0.5
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(data, tmp)
            summary = json.loads(Path(result["simulation"]["simulation_summary"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["calibration_assessment"]["status"], "failed")
            self.assertIn("calibration_failed", summary["decision_gate"]["triggers"])
            self.assertEqual(summary["decision_gate"]["status"], "blocked_for_decision_use")

    def test_sampling_purpose_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_2pct_solution_multiple_input.yaml"), tmp)
            sampling = pd.read_csv(result["sampling"])
            self.assertIn("must_max_use", set(sampling["purpose"]))
            self.assertIn("be_bridging", set(sampling["purpose"]))
            self.assertTrue(sampling["sample_intent"].str.contains("Day 28 last-dose dense profile").any())
            self.assertTrue(sampling["note"].fillna("").str.contains("PopPK").any())

    def test_provenance_sensitivity_extended_fields_and_deprecated_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_1pct_solution_single_input.yaml"), tmp)
            provenance = pd.read_csv(Path(result["run_dir"]) / "outputs/parameter_provenance.csv")
            sensitivity = pd.read_csv(Path(result["run_dir"]) / "outputs/dose_extrapolation_sensitivity.csv")
            known = pd.read_csv(result["input_files"]["known_formulations"])
            summary = json.loads(Path(result["simulation"]["simulation_summary"]).read_text(encoding="utf-8"))
            self.assertIn("provenance", provenance.columns)
            self.assertEqual(set(sensitivity["dose_extrapolation_exponent"]), {0.7, 1.0, 1.3})
            self.assertIn("fraction_unbound", known.columns)
            self.assertIn("early_apparent_volume_l_range", summary["parameter_ranges"]["deprecated_fields"])

    def test_variability_preset_and_custom_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(_load_input("dutasteride_1pct_solution_single_input.yaml"), tmp)
            summary = json.loads(Path(result["simulation"]["simulation_summary"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["product"]["variability"]["preset"], "medium")

        data = _load_input("dutasteride_1pct_solution_single_input.yaml")
        data["product"]["interindividual_cv"] = 0.9
        data["product"]["bioavailability_cv"] = 0.7
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_input(data, tmp)
            summary = json.loads(Path(result["simulation"]["simulation_summary"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["product"]["variability"]["preset"], "custom")
            self.assertAlmostEqual(summary["product"]["variability"]["interindividual_cv"], 0.9)


if __name__ == "__main__":
    unittest.main()
