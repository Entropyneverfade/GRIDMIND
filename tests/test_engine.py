"""小算例校验，重点检查功率守恒、出力边界和 GA 流程。"""

import itertools
import unittest
from pathlib import Path

from power_ga.data_collection.reader import load_problem
from power_ga.common.domain import Hour, Plant, Problem, StorageSpec
from power_ga.fitness_and_convergence.evaluation import evaluate, ppt_fitness
from power_ga.genetic_iteration.solver import optimize
from power_ga.operation_simulation.engine import simulate, dispatch_renewables, dispatch_thermal, StorageState


ROOT = Path(__file__).resolve().parents[1]


class EngineTests(unittest.TestCase):
    """用手算基准核对各物理守恒式，再核对完整GA是否选中枚举最优。"""

    def test_storage_efficiency_known_answer(self):
        """ηch=ηdis=0.9，两次充100MWh得180，再各放81MWh后归零。"""
        plant = Plant("储能", "storage", 100, 0, 0, storage=StorageSpec(100, 200, 0.9, 0.9))
        state = StorageState(plant, 0)
        state.charge(100); state.charge(100)
        self.assertAlmostEqual(state.energy_mwh, 180)
        state.discharge(81); state.discharge(81)
        self.assertAlmostEqual(state.energy_mwh, 0)

    def test_storage_cross_day_balance(self):
        """第23小时的库存必须成为第24小时初态，不能在日界归零。"""
        storage = Plant("储能", "storage", 100, 0, 0, storage=StorageSpec(100, 80, 0.9, 0.9))
        hours = tuple(Hour(100, 1 if h == 23 else 0, 0) for h in range(26))
        problem = Problem((storage, Plant("风电", "wind", 200, 0, 0)), (), hours, 0, 0)
        result = simulate(problem, (), keep_hourly=True)
        self.assertGreater(result.hourly[23].storage_energy_end_mwh, 0)
        self.assertAlmostEqual(result.hourly[24].storage_energy_start_mwh,
                               result.hourly[23].storage_energy_end_mwh)
        self.assertAlmostEqual(result.hourly[24].storage_discharge_mw, 72)
        self.assertLess(result.max_storage_residual_mwh, 1e-7)
        self.assertLess(result.max_balance_residual_mw, 1e-7)
        self.assertTrue(all(h.charge_mw * h.discharge_mw == 0 for h in result.storage_hourly))

    def test_minimum_thermal_causes_curtailment(self):
        """最小火电160MW时，输入的风光过剩应形成110MWh弃光。"""
        plants = (Plant("火电", "thermal", 400, 400, 250, min_output_mw=160),
                  Plant("风电", "wind", 150, 0, 0), Plant("光伏", "solar", 300, 0, 0))
        result = simulate(Problem(plants, (), (Hour(500, 1, 1),), 0, 0), (), keep_hourly=True)
        self.assertAlmostEqual(result.solar_curtailment_mwh, 110)
        self.assertAlmostEqual(result.thermal_mwh, 160)

    def test_thermal_merit_order(self):
        """按250、320、450元/MWh排序，500MW净负荷对应400+100+0。"""
        plants = (
            Plant("A", "thermal", 400, 400, 250),
            Plant("B", "thermal", 500, 500, 320),
            Plant("C", "thermal", 300, 300, 450),
        )
        result = dispatch_thermal(500, plants)
        self.assertEqual(result.generation_by_plant_mw, (400, 100, 0))
        self.assertEqual(result.cost_yuan, 132000)
        self.assertEqual(result.remaining_mw, 0)

    def test_renewable_curtailment(self):
        """余下可消纳功率340MW时，光伏先弃110MW。"""
        # 若其他必须运行电源已承担 160 MW，500 MW 负荷的剩余可消纳空间为 340 MW。
        # 本函数只负责风光层，不代表已实现必须运行火电模型。
        result = dispatch_renewables(340, 150, 300, 1, 1)
        self.assertEqual(result.wind_mw, 150)
        self.assertEqual(result.solar_mw, 190)
        self.assertEqual(result.solar_curtailment_mw, 110)

    def test_manual_curtailment_priorities(self):
        """先弃风和风光比例弃都应总弃110MW，但分配不同。"""
        # 同一过剩量在三种序位下必须守恒，但电源间分配不同。
        wind_first = dispatch_renewables(340, 150, 300, 1, 1, "wind_first")
        proportional = dispatch_renewables(340, 150, 300, 1, 1, "proportional")
        self.assertAlmostEqual(wind_first.wind_curtailment_mw, 110)
        self.assertAlmostEqual(wind_first.solar_curtailment_mw, 0)
        self.assertAlmostEqual(proportional.wind_curtailment_mw, 110 / 3)
        self.assertAlmostEqual(proportional.solar_curtailment_mw, 220 / 3)
        self.assertAlmostEqual(proportional.wind_mw + proportional.solar_mw, 340)

    def test_hourly_balance_and_shortage(self):
        """短缺显式计ENS，同时每小时供给加缺供等于负荷。"""
        problem = Problem(
            (Plant("旧火电", "thermal", 50, 50, 300),),
            (Plant("候选风电", "wind", 20, 0, 20, 1000),),
            (Hour(60, 1, 0), Hour(80, 0, 0)),
            0.1, 0,
        )
        result = simulate(problem, (1,), keep_hourly=True)
        self.assertAlmostEqual(result.unserved_mwh, 30)
        self.assertEqual(result.shortage_hours, 1)
        self.assertLess(result.max_balance_residual_mw, 1e-7)
        for hour in result.hourly:
            self.assertAlmostEqual(hour.wind_mw + hour.solar_mw +
                                   hour.thermal_mw + hour.unserved_mw,
                                   hour.load_mw)

    def test_ppt_fitness(self):
        """PPT成本适应度AF_i求和为1，并随费用增加而下降。"""
        weights = ppt_fitness([10, 20, 30])
        self.assertAlmostEqual(sum(weights), 1)
        self.assertGreater(weights[0], weights[1])
        self.assertGreater(weights[1], weights[2])

    def test_demo_ga_matches_small_enumeration(self):
        """6个候选项目只需64组合，可直接枚举验证GA所选结果。"""
        problem, settings = load_problem(ROOT / "input" / "config.json",
                                         ROOT / "input" / "hourly_profiles.csv")
        result = optimize(problem, settings)
        exact = min((evaluate(problem, bits) for bits in
                     itertools.product((0, 1), repeat=len(problem.candidates))),
                    key=lambda item: item.sort_key())
        self.assertTrue(result.best.feasible)
        self.assertEqual(result.best.chromosome, exact.chromosome)
        self.assertAlmostEqual(result.best.total_cost_yuan, exact.total_cost_yuan)


if __name__ == "__main__":
    unittest.main()
