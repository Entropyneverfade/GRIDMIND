"""已知答案核验跨区碳、硫、新能源属性及系统守恒。"""

import unittest

from power_ga.operation_simulation.attributes import PowerAttribute, trace_power_attributes
from power_ga.operation_simulation.network import (
    Generator, Link, Zone, solve_network_hour_heuristic)


class AttributeTests(unittest.TestCase):
    def test_two_zone_mixed_power_exports_half_attributes(self):
        # A区10 MW煤+10 MW风，服务本区10、外送B区10；两端各继承50%风属性。
        zones = (Zone("A", 10, wind_available_mw=10), Zone("B", 10))
        units = (Generator("煤", "A", 10, 10, 200),)
        links = (Link("AB", "A", "B", 10),)
        dispatch = solve_network_hour_heuristic(zones, units, links)
        traced = trace_power_attributes(zones, units, links, dispatch,
                                        {"煤": PowerAttribute(1.0, 2.0, 0.0)})
        for name in ("A", "B"):
            item = traced.zones[name]
            self.assertAlmostEqual(item.carbon_t_per_mwh, 0.5)
            self.assertAlmostEqual(item.sulfur_kg_per_mwh, 1.0)
            self.assertAlmostEqual(item.renewable_fraction, 0.5)
            self.assertAlmostEqual(item.consumed_carbon_t, 5)
            self.assertAlmostEqual(item.consumed_sulfur_kg, 10)
            self.assertAlmostEqual(item.consumed_renewable_mwh, 5)
        self.assertLess(abs(traced.carbon_balance_t), 1e-9)
        self.assertLess(abs(traced.sulfur_balance_kg), 1e-9)
        self.assertLess(abs(traced.renewable_balance_mwh), 1e-9)

    def test_storage_attribute_required(self):
        # 放电属性不明时拒绝把这1 MWh直接记为零碳或绿电。
        zones = (Zone("A", 1, fixed_discharge_mw=1),)
        dispatch = solve_network_hour_heuristic(zones, (), ())
        with self.assertRaises(ValueError):
            trace_power_attributes(zones, (), (), dispatch, {})
        result = trace_power_attributes(zones, (), (), dispatch, {},
                                        {"A": PowerAttribute(0.4, 0.5, 0.3)})
        self.assertAlmostEqual(result.zones["A"].consumed_carbon_t, 0.4)
        self.assertAlmostEqual(result.zones["A"].consumed_sulfur_kg, 0.5)
        self.assertAlmostEqual(result.zones["A"].consumed_renewable_mwh, 0.3)


if __name__ == "__main__":
    unittest.main()
