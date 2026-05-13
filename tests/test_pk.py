import math
import unittest

from pktool.pk import cl_v_to_ke, effective_steady_state_times, half_life_to_ke, resolve_systemic_pk, steady_state_frequency_matrix


class TestPK(unittest.TestCase):
    def test_half_life_to_ke(self):
        self.assertAlmostEqual(half_life_to_ke(12), math.log(2) / 12)

    def test_cl_v_to_ke(self):
        self.assertAlmostEqual(cl_v_to_ke(5, 100), 0.05)

    def test_resolve_systemic_pk_derives_clearance(self):
        compound = {"half_life_h": 10, "volume_l": 100, "lloq_ng_ml": 0.1}
        pk = resolve_systemic_pk(compound, {})
        self.assertAlmostEqual(pk.ke_h, math.log(2) / 10)
        self.assertAlmostEqual(pk.clearance_l_h, pk.ke_h * 100)
        self.assertGreaterEqual(len(pk.warnings), 1)

    def test_steady_state_fraction_times_and_frequency_matrix(self):
        ss = effective_steady_state_times(72)
        self.assertAlmostEqual(ss["t_ss_50_h"], 72)
        self.assertAlmostEqual(ss["t_ss_75_h"], 144)
        self.assertGreater(ss["t_ss_99_h"], ss["t_ss_95_h"])
        matrix = steady_state_frequency_matrix(ss["t_half_eff_h"])
        labels = {row["target_label"] for row in matrix}
        frequencies = {row["frequency"] for row in matrix}
        self.assertIn("50%", labels)
        self.assertIn("接近100%(99%)", labels)
        self.assertIn("daily_qd", frequencies)
        self.assertIn("weekly_qw", frequencies)


if __name__ == "__main__":
    unittest.main()
