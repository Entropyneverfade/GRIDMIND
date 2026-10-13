"""公开合成8760小时场景：核对新项目引擎的储能连续性和能量平衡。"""

import unittest
from itertools import product

from power_ga.common.domain import GASettings
from power_ga.data_collection.project_case import CasePlant, ProjectCase
from power_ga.genetic_iteration.project_solver import evaluate_project, optimize_project
from power_ga.operation_simulation.project_engine import simulate_project


class ProjectEngineTests(unittest.TestCase):
    """使用完全合成的输入，不依赖或复制任何项目数据库。"""

    def test_eight_technologies_and_8760_balance(self):
        """八类技术可同时进入引擎，逐小时功率与储能状态残差接近零。"""
        daylight = tuple(0.7 if h % 24 in range(9, 16) else 0.0 for h in range(8760))
        wind = tuple(0.8 if h % 24 < 12 else 0.1 for h in range(8760))
        plants = (
            CasePlant(1, "Coal", "coal", 100, 0.5, 350, 0),
            CasePlant(2, "Gas", "gas", 30, 0.1, 600, 0),
            CasePlant(3, "Hydro", "hydro", 20, 0, 30, 0),
            CasePlant(4, "Biomass", "biomass", 10, 0.4, 400, 0),
            CasePlant(5, "Wind", "wind", 80, 0, 0, 0, wind),
            CasePlant(6, "PV", "solar", 50, 0, 0, 0, daylight),
            # 电池/抽蓄的内部容量分别为P×时长，往返效率按平方根分解。
            CasePlant(7, "Battery", "battery", 20, 0, 0, 0, (), 2, 1, 0.81),
            CasePlant(8, "Pumped", "pumped", 15, 0, 0, 0, (), 3, 1, 0.81),
        )
        case = ProjectCase(2025, 2029, plants, (), (100.0,) * 8760,
                           (5.0,) * 8760, 0.03, 0, (), "", "")
        run = simulate_project(case, (), keep_hourly=True)
        self.assertEqual(len(run.hourly), 8760)
        self.assertEqual(len(run.storage_hourly), 2 * 8760)
        self.assertLess(run.summary["max_balance_residual_mw"], 1e-7)
        self.assertGreater(run.summary["storage_final_mwh"], -1e-7)
        self.assertTrue(any(h.storage_charge_mw > 0 for h in run.hourly))
        self.assertTrue(any(h.storage_discharge_mw > 0 for h in run.hourly))
        # ΔE−sqrt(ηRT)Pch+Pdis/sqrt(ηRT)=0，对每站每小时成立。
        self.assertLess(max(abs(row[-1]) for row in run.storage_hourly), 1e-7)
        self.assertTrue(all(h.storage_charge_mw * h.storage_discharge_mw < 1e-9
                            for h in run.hourly))

    def test_project_ga_matches_complete_two_bit_enumeration(self):
        """2位共4方案可穷举：只有新增煤电才满足可信容量，电池不应凭额定MW代替容量信用。"""
        existing = (CasePlant(1, "ExistingCoal", "coal", 90, 0, 300, 0),)
        candidates = (CasePlant(2, "NewCoal", "coal", 20, 0, 300, 1_000_000),
                      CasePlant(3, "Battery", "battery", 10, 0, 0, 2_000_000,
                                (), 2, 1, 0.81))
        case = ProjectCase(2025, 2029, existing, candidates, (100.0,) * 8760,
                           (0.0,) * 8760, 0.05, 0, (), "", "")
        exhaustive = [evaluate_project(case, chromosome)
                      for chromosome in product((0, 1), repeat=2)]
        optimum = min(exhaustive, key=lambda item: item.sort_key())
        self.assertEqual(optimum.chromosome, (1, 0))
        self.assertFalse(next(item for item in exhaustive
                              if item.chromosome == (0, 1)).feasible)
        settings = GASettings(population_size=8, max_generations=8,
                              min_generations=2, stall_generations=3,
                              elite_count=1, crossover_rate=0.8,
                              mutation_rate=0.10, seed=7)
        result = optimize_project(case, settings)
        self.assertEqual(result.best.chromosome, optimum.chromosome)
        self.assertAlmostEqual(result.best.total_cost_yuan, optimum.total_cost_yuan)
        self.assertTrue(result.best.feasible)


if __name__ == "__main__":
    unittest.main()
