"""对优化模式使用已知答案算例，核对成本和滚动窗口SOC衔接。"""

import importlib.util
import unittest

from power_ga.common.domain import Hour, Plant, Problem, StorageSpec
from power_ga.operation_simulation.gurobi_engine import simulate


@unittest.skipUnless(importlib.util.find_spec("gurobipy"), "未安装可选gurobipy")
class GurobiTests(unittest.TestCase):
    """检查优化引擎与手算成本及跨窗口库存方程一致。"""

    def test_merit_dispatch_known_cost(self):
        """每小时400×250+100×320=132000元，24小时等于该值乘24。"""
        plants = (Plant("便宜机组", "thermal", 400, 400, 250),
                  Plant("昂贵机组", "thermal", 500, 500, 320))
        problem = Problem(plants, (), tuple(Hour(500, 0, 0) for _ in range(24)), 0, 0,
                          operating_reserve_ratio=0, dispatch_mode="gurobi")
        result = simulate(problem, (), True)
        self.assertAlmostEqual(result.variable_cost_yuan, 132000 * 24, places=3)
        self.assertAlmostEqual(result.unserved_mwh, 0)

    def test_rolling_storage_state(self):
        """第23小时充入80MWh库容，下一窗口按ηdis=0.9放72MWh。"""
        storage = Plant("储能", "storage", 100, 0, 0, storage=StorageSpec(100, 80, 0.9, 0.9))
        hours = tuple(Hour(100, 1 if h == 23 else 0, 0) for h in range(26))
        problem = Problem((storage, Plant("风电", "wind", 200, 0, 0)), (), hours, 0, 0,
                          operating_reserve_ratio=0, dispatch_mode="gurobi",
                          terminal_storage_value_yuan_per_mwh=0)
        result = simulate(problem, (), True)
        self.assertAlmostEqual(result.hourly[23].storage_energy_end_mwh,
                               result.hourly[24].storage_energy_start_mwh, places=6)
        self.assertAlmostEqual(sum(h.storage_discharge_mw for h in result.hourly[24:]), 72, places=5)
        self.assertLess(result.max_balance_residual_mw, 1e-6)
        self.assertLess(result.max_storage_residual_mwh, 1e-6)
        self.assertTrue(all(h.charge_mw * h.discharge_mw < 1e-6 for h in result.storage_hourly))
        self.assertEqual(len(result.solver_log), 2)


if __name__ == "__main__":
    unittest.main()
