"""动态规划的阶段转移、折现与Gurobi独立最优性校验。"""

import unittest
from types import SimpleNamespace

from power_ga.dynamic_planning.solver import _dp_tables, _gurobi_path, _validate_cases


class DynamicPlanningTests(unittest.TestCase):
    def test_two_stage_known_path(self):
        """只允许0→1的建设转移；折现后应选择首年项目A、次年加B。"""
        def item(cost, feasible=True):
            return SimpleNamespace(total_cost_yuan=cost, feasible=feasible)
        # 两个候选项目按bit 0/1编码；状态3表示两者都投运。
        tables = ({0: item(20), 1: item(8), 2: item(14), 3: item(19)},
                  {0: item(30), 1: item(17), 2: item(16), 3: item(4)})
        path, cost = _dp_tables(tables, 0.10)
        gurobi_path, gurobi_cost = _gurobi_path(tables, 0.10, 2)
        self.assertEqual((1, 3), path)
        self.assertEqual(path, gurobi_path)
        self.assertAlmostEqual(8 + 4 / 1.1, cost)
        self.assertAlmostEqual(cost, gurobi_cost, places=6)

    def test_infeasible_initial_state_cannot_be_used(self):
        """不可行阶段状态应同时被Bellman和Gurobi排除。"""
        def item(cost, feasible=True):
            return SimpleNamespace(total_cost_yuan=cost, feasible=feasible)
        tables = ({0: item(1, False), 1: item(6)},
                  {0: item(1, False), 1: item(5)})
        self.assertEqual((1, 1), _dp_tables(tables, 0.07)[0])
        self.assertEqual((1, 1), _gurobi_path(tables, 0.07, 1)[0])

    def test_candidate_identity_cannot_shift_between_years(self):
        """同一状态位若在下一年换了技术或容量，必须在运行前拒绝。"""
        first = SimpleNamespace(target_year=2026, candidates=(
            SimpleNamespace(station_id=1, technology="gas", capacity_mw=10),))
        second = SimpleNamespace(target_year=2027, candidates=(
            SimpleNamespace(station_id=1, technology="gas", capacity_mw=12),))
        with self.assertRaisesRegex(ValueError, "容量"):
            _validate_cases((first, second), 0.07, 8)


if __name__ == "__main__":
    unittest.main()
