"""八类机组公开演示算例的物理残差与图形范围回归。"""

import unittest

from examples.synthetic_eight_type import build_case
from power_ga.operation_simulation.project_engine import simulate_project
from power_ga.result_output.viewer import month_events, period_bounds


class SyntheticDemoTests(unittest.TestCase):
    def test_eight_technologies_and_hourly_balance(self):
        """公开演示必须完整含八类机组，且不是拼接的虚构出力表。"""
        case = build_case()
        self.assertEqual(len(case.domestic_load_mw), 8760)
        self.assertEqual(len({p.technology for p in case.existing}), 8)
        result = simulate_project(case, (), keep_hourly=True)
        self.assertEqual(len(result.hourly), 8760)
        self.assertLess(result.summary["max_balance_residual_mw"], 1e-8)
        for field in ("coal_mw", "gas_mw", "hydro_mw", "biomass_mw", "wind_mw",
                      "solar_mw", "pumped_discharge_mw", "battery_discharge_mw"):
            self.assertGreater(sum(getattr(row, field) for row in result.hourly), 0, field)
        # 相邻日的同一小时存在天气和负荷扰动，公开演示不重复一张固定日曲线。
        self.assertNotEqual(case.domestic_load_mw[12], case.domestic_load_mw[36])
        self.assertNotEqual(case.existing[6].profile[12], case.existing[6].profile[36])
        self.assertNotEqual(case.existing[7].profile[12], case.existing[7].profile[36])

    def test_predefined_ranges_cover_planning_year(self):
        """窗口边界是左闭右开，最后一天、周和月均截止于8760小时。"""
        self.assertEqual(period_bounds("日", 365), (8736, 8760))
        self.assertEqual(period_bounds("周", 53), (8736, 8760))
        self.assertEqual(period_bounds("月", 12), (8016, 8760))
        self.assertEqual(period_bounds("年", 1), (0, 8760))

    def test_month_marker_does_not_call_zero_shortage_a_shortage(self):
        """全月无缺供时，标最大净需求；实际缺供出现时才标最大缺供日。"""
        hours = [{"unserved_mw": 0.0, "reserve_shortfall_mw": 0.0,
                  "load_mw": 80.0 + (10 if t >= 24 else 0),
                  "wind_mw": 5.0, "solar_mw": 0.0,
                  "wind_curtailment_mw": 0.0, "solar_curtailment_mw": 0.0}
                 for t in range(48)]
        self.assertEqual(month_events(hours, 0, 48)[0]["label"], "净负荷峰值日")
        hours[3]["unserved_mw"] = 2.0
        event = month_events(hours, 0, 48)[0]
        self.assertEqual((event["label"], event["day_of_month"], event["value"]),
                         ("最大缺供日", 1, 2.0))


if __name__ == "__main__":
    unittest.main()
