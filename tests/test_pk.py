import math
import unittest

from pktool.pk import cl_v_to_ke, half_life_to_ke, resolve_systemic_pk


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


if __name__ == "__main__":
    unittest.main()

