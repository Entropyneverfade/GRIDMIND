"""动态规划的阶段转移、折现与Gurobi独立最优性校验。"""

import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from power_ga.data_collection.project_case import CasePlant, ProjectCase, align_stage_case
from power_ga.dynamic_planning.solver import _dp_tables, _gurobi_path, _validate_cases
from power_ga.operation_simulation.project_engine import simulate_project
from power_ga.result_output.dynamic_report import write_dynamic_report


class DynamicPlanningTests(unittest.TestCase):
    def test_annual_existing_capacity_changes_hourly_feasibility(self):
        """前一年仅有50MW存量时不能偷用终期100MW；逐时缺口仍要守恒。"""
        def make(year, capacity):
            plant = CasePlant(1, "合成燃气", "gas", capacity, 0, 400, 0)
            return ProjectCase(2025, year, (plant,), (), (75,) * 8760,
                               (0,) * 8760, 0, 657, (), "synthetic", "synthetic")
        previous, terminal = make(2026, 50), make(2027, 100)
        stage = align_stage_case(terminal, previous)
        prior_run = simulate_project(stage, (), reserve_ratio=0)
        terminal_run = simulate_project(terminal, (), reserve_ratio=0)
        self.assertEqual(50, stage.existing[0].capacity_mw)
        self.assertEqual(25 * 8760, prior_run.summary["unserved"])
        self.assertEqual(0, terminal_run.summary["unserved"])
        self.assertLess(prior_run.summary["max_balance_residual_mw"], 1e-6)

    def test_stage_report_records_comparable_ga_path(self):
        """同一费用表的GA路径和差距必须写入阶段汇总，且不可行时不能报假差距。"""
        stage = lambda year, state, new, cost: SimpleNamespace(
            year=year, state=state, newly_built=new, annual_cost_yuan=cost,
            discounted_cost_yuan=cost, max_balance_residual_mw=0.0)
        result = SimpleNamespace(stages=(stage(2026, 0, 0, 10),
                                         stage(2027, 1, 1, 10)),
                                 objective_yuan=20.0, gurobi_objective_yuan=20.0,
                                 discount_rate=0.0)
        ga = SimpleNamespace(best=SimpleNamespace(feasible=True, total_cost_yuan=21.0),
                             evaluations=9, stop_reason="达到最大代数",
                             history=(SimpleNamespace(generation=0, best_cost_yuan=21.0,
                                      best_feasible=True, feasible_count=2,
                                      unique_count=3),))
        case = SimpleNamespace(candidates=(SimpleNamespace(name="合成燃气"),))
        with tempfile.TemporaryDirectory() as folder:
            write_dynamic_report(result, case, Path(folder), .95, "source", (ga, (0, 1)))
            audit = json.loads((Path(folder) / "dynamic_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(.05, round(audit["ga_comparison"]["relative_gap"], 8))
            self.assertEqual("source", audit["stage_input_mode"])
            self.assertTrue((Path(folder) / "tables" / "ga_dp_comparison.csv").is_file())
        with tempfile.TemporaryDirectory() as folder:
            # 零费用最优与不可行候选都不能触发除零或产生虚假百分比。
            zero_result = SimpleNamespace(stages=result.stages, objective_yuan=0.0,
                                          gurobi_objective_yuan=0.0, discount_rate=0.0)
            infeasible_ga = SimpleNamespace(best=SimpleNamespace(feasible=False,
                                                total_cost_yuan=0.0),
                                            evaluations=1, stop_reason="达到最大代数",
                                            history=ga.history)
            write_dynamic_report(zero_result, case, Path(folder), .95,
                                 "source", (infeasible_ga, (0, 0)))
            audit = json.loads((Path(folder) / "dynamic_audit.json").read_text(encoding="utf-8"))
            self.assertIsNone(audit["ga_comparison"]["relative_gap"])

    def test_source_stage_curves_keep_terminal_candidate_encoding(self):
        """年度负荷/风光必须来自该年，建设容量仍按终期同一状态位解释。"""
        wind_final = CasePlant(10, "风电", "wind", 20, 0, 0, 0,
                               (.2,) * 8760)
        wind_year = CasePlant(10, "风电", "wind", 10, 0, 0, 0,
                              (.6,) * 8760)
        hydro_final = CasePlant(11, "水电", "hydro", 30, 0, 0, 0,
                                hydro_monthly_factor=(1.0,) * 12)
        hydro_year = CasePlant(11, "水电", "hydro", 25, 0, 0, 0,
                               hydro_monthly_factor=(0.3,) * 12)
        gas_final = CasePlant(20, "燃气", "gas", 15, 0.2, 400, 1000)
        final = ProjectCase(2025, 2027, (hydro_final,), (wind_final, gas_final),
                            (100,) * 8760, (5,) * 8760, .15, 800,
                            (), "source", "cost")
        annual = ProjectCase(2025, 2026, (hydro_year,), (wind_year,),
                             (70,) * 8760, (3,) * 8760, .12, 600,
                             (), "source", "cost")
        stage = align_stage_case(final, annual)
        self.assertEqual((70, 3, .6, 20), (stage.domestic_load_mw[0],
                                            stage.export_mw[0],
                                            stage.candidates[0].profile[0],
                                            stage.candidates[0].capacity_mw))
        self.assertEqual((15, 1000), (stage.candidates[1].capacity_mw,
                                       stage.candidates[1].annual_cost_yuan))
        self.assertEqual((25, .3), (stage.existing[0].capacity_mw,
                                   stage.existing[0].hydro_monthly_factor[0]))
        self.assertEqual(2026, stage.target_year)
        self.assertIn("未列电站20", " ".join(stage.warnings))

    def test_missing_annual_renewable_curve_is_rejected(self):
        """缺少该年可再生曲线时不能偷偷复用终期天气。"""
        wind = CasePlant(10, "风电", "wind", 20, 0, 0, 0,
                         (.2,) * 8760)
        final = ProjectCase(2025, 2027, (), (wind,), (1,) * 8760,
                            (0,) * 8760, .1, 1, (), "source", "cost")
        annual = ProjectCase(2025, 2026, (), (), (1,) * 8760,
                             (0,) * 8760, .1, 1, (), "source", "cost")
        with self.assertRaisesRegex(ValueError, "年度曲线"):
            align_stage_case(final, annual)

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
