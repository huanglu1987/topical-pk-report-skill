import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pktool.evidence import fetch_fda_label, fetch_pubchem


class TestEvidence(unittest.TestCase):
    def test_pubchem_fetch_parses_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            response = Mock()
            response.status_code = 200
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": 1,
                            "MolecularWeight": 100.1,
                            "InChIKey": "TEST",
                        }
                    ]
                }
            }
            synonym_response = Mock()
            synonym_response.ok = True
            synonym_response.json.return_value = {"InformationList": {"Information": [{"Synonym": ["A", "B"]}]}}
            with patch("pktool.evidence.requests.get", side_effect=[response, synonym_response]):
                result = fetch_pubchem("demo", output_dir=Path(tmp))
            self.assertTrue(result["ok"])
            self.assertEqual(result["properties"]["InChIKey"], "TEST")
            self.assertTrue((Path(tmp) / "evidence_manifest.csv").exists())

    def test_fda_no_result_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            response = Mock()
            response.status_code = 404
            with patch("pktool.evidence.requests.get", return_value=response):
                result = fetch_fda_label("missing", output_dir=Path(tmp))
            self.assertFalse(result["ok"])
            self.assertEqual(result["labels_found"], 0)
            self.assertTrue((Path(tmp) / "evidence_manifest.csv").exists())


if __name__ == "__main__":
    unittest.main()

