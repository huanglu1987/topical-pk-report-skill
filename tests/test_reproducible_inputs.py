import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "reproducible_inputs"


LOCKED_INPUTS = [
    "dutasteride_2pct_20mg_single_locked.yaml",
    "dutasteride_2pct_20mg_multiple_daily_qd_steady_state_locked.yaml",
    "dutasteride_2pct_20mg_multiple_weekly_qw_steady_state_locked.yaml",
]


class TestReproducibleInputs(unittest.TestCase):
    def _load(self, name: str) -> dict:
        return yaml.safe_load((INPUT_DIR / name).read_text(encoding="utf-8"))

    def test_locked_files_exist_and_parse(self):
        for name in LOCKED_INPUTS:
            with self.subTest(name=name):
                data = self._load(name)
                self.assertEqual(data["compound"]["compound_name"], "dutasteride")
                self.assertEqual(data["product"]["dose_mg_per_application"], 20)
                self.assertEqual(data["study_design"]["n_simulations"], 3000)
                self.assertEqual(data["study_design"]["random_seed"], 20260515)

    def test_locked_topical_assumptions_match_reference_reports(self):
        forbidden_values = {
            "wrong_absorption": [0.0005, 0.05],
            "wrong_depot": [12, 168],
            "wrong_variability": "high",
        }
        for name in LOCKED_INPUTS:
            with self.subTest(name=name):
                data = self._load(name)
                product = data["product"]
                self.assertEqual(product["absorption_fraction_range"], [0.000005, 0.001])
                self.assertNotEqual(product["absorption_fraction_range"], forbidden_values["wrong_absorption"])
                self.assertEqual(product["depot_half_life_h_range"], [2, 72])
                self.assertNotEqual(product["depot_half_life_h_range"], forbidden_values["wrong_depot"])
                self.assertEqual(product["variability_preset"], "medium")
                self.assertNotEqual(product["variability_preset"], forbidden_values["wrong_variability"])

    def test_single_dose_reference_anchor_is_locked(self):
        data = self._load("dutasteride_2pct_20mg_single_locked.yaml")
        primary = next(item for item in data["known_formulations"] if item.get("primary_comparator"))
        self.assertEqual(primary["cmax_ng_ml"], 3.067)
        self.assertEqual(primary["auc_ng_h_ml"], 48.048)
        self.assertNotEqual(primary["cmax_ng_ml"], 3.29)
        self.assertNotEqual(primary["auc_ng_h_ml"], 52.32)

    def test_multiple_dose_inputs_lock_steady_state_window(self):
        for name in LOCKED_INPUTS:
            data = self._load(name)
            if data["study_design"]["dosing_scenario"] != "multiple":
                continue
            with self.subTest(name=name):
                self.assertEqual(data["product"]["treatment_duration_h"], 6048)
                self.assertEqual(data["study_design"]["dosing_duration_h"], 6048)
                self.assertEqual(data["study_design"]["duration_h"], 8568)
                self.assertGreater(data["study_design"]["duration_h"], 672)


if __name__ == "__main__":
    unittest.main()
