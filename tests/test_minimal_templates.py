import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class TestMinimalTemplates(unittest.TestCase):
    def test_minimal_template_files_do_not_override_duration(self):
        for path in [
            ROOT / "data/minimal_input_template.yaml",
            ROOT / ".codex/skills/topical-pk-report/templates/minimal_input_template.yaml",
        ]:
            with self.subTest(path=str(path)):
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                study = data["study_design"]
                self.assertNotIn("duration_h", study)
                self.assertNotIn("dosing_duration_h", study)
                self.assertEqual(study["random_seed"], 20260515)

    def test_minimal_copyable_doc_yaml_blocks_parse(self):
        text = (ROOT / "docs/MINIMAL_COPYABLE_INPUT.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```yaml\n(.*?)\n```", text, flags=re.S)
        self.assertEqual(len(blocks), 2)
        parsed = [yaml.safe_load(block) for block in blocks]
        self.assertEqual(parsed[0]["study_design"]["dosing_scenario"], "single")
        self.assertEqual(parsed[1]["study_design"]["dosing_scenario"], "multiple")
        self.assertEqual(parsed[1]["study_design"]["dosing_frequency"], "daily_qd")
        self.assertNotIn("duration_h", parsed[1]["study_design"])
        self.assertNotIn("dosing_duration_h", parsed[1]["study_design"])
        self.assertNotIn("treatment_duration_h", parsed[1]["product"])


if __name__ == "__main__":
    unittest.main()
