"""公开合成三年度演示的年度输入与逐时物理量回归。"""

import unittest

from examples.synthetic_dynamic_case import build_stages
from power_ga.common.domain import PLANNING_MONTH_HOURS
from power_ga.genetic_iteration.project_solver import evaluate_project
from power_ga.operation_simulation.project_engine import simulate_project


class SyntheticDynamicCaseTests(unittest.TestCase):
    def test_three_year_eight_type_input_and_physical_residual(self):
        """先独立证明三年度输入和全建状态可行，再允许昂贵的全状态DP枚举。"""
        cases = build_stages(full_horizon=True)
        self.assertEqual(tuple(case.target_year for case in cases), (2026, 2027, 2028))
        self.assertEqual(tuple(len(case.domestic_load_mw) for case in cases), (8760,) * 3)
        self.assertEqual(len({p.technology for p in cases[0].existing}), 8)
        self.assertEqual(len(cases[0].candidates), 8)
        self.assertEqual(
            tuple((p.station_id, p.technology, p.capacity_mw) for p in cases[0].candidates),
            tuple((p.station_id, p.technology, p.capacity_mw) for p in cases[-1].candidates))
        for case, factor in zip(cases, (0.82, 1.0, 1.08)):
            # 每年负荷与同一固定种子基准曲线按声明的倍率对应，风光输入完全一致。
            self.assertAlmostEqual(case.domestic_load_mw[137],
                                   cases[1].domestic_load_mw[137] * factor)
            self.assertEqual(case.existing[-2].profile, cases[1].existing[-2].profile)
            self.assertEqual(case.existing[-1].profile, cases[1].existing[-1].profile)
            bits = (1,) * len(case.candidates)
            self.assertTrue(evaluate_project(case, bits).feasible)
            operation = simulate_project(case, bits, keep_hourly=True)
            self.assertEqual(len(operation.hourly), 8760)
            self.assertLess(operation.summary["max_balance_residual_mw"], 1e-8)
            self.assertLess(max(abs(row[-1]) for row in operation.storage_hourly), 1e-8)
            # 水电月能量不能超过P_h×H_m×0.42×f_m；调度可少用水。
            hydros = [p for p in case.existing + case.candidates if p.technology == "hydro"]
            offset = 0
            for month, hours in enumerate(PLANNING_MONTH_HOURS):
                generation = sum(row.hydro_mw for row in operation.hourly[offset:offset + hours])
                budget = sum(p.capacity_mw * hours * 0.42 * p.hydro_monthly_factor[month]
                             for p in hydros)
                self.assertLessEqual(generation, budget + 1e-6)
                offset += hours


if __name__ == "__main__":
    unittest.main()
