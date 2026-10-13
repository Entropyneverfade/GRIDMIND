"""公开可复现的完整案例：八位遗传规划 + 八类机组8760小时运行。"""

import argparse
import json
from pathlib import Path

from examples.synthetic_eight_type import build_case
from power_ga.common.domain import GASettings
from power_ga.genetic_iteration.project_solver import optimize_project
from power_ga.operation_simulation.project_engine import simulate_project
from power_ga.result_output.project_report import write_project_report


def execute(destination: Path, population=24, generations=20, seed=19,
            origin_figures=False):
    """执行Gen=0至收敛，再对最优染色体重算完整8760行并归档。"""
    case = build_case(with_candidates=True)
    settings = GASettings(population, generations, 4, 4, 2, 0.85, 0.04, seed)
    result = optimize_project(case, settings)
    # GA内评价可省去逐时存储；最终方案必须重算含站级储能残差的完整时序。
    simulation = simulate_project(case, result.best.chromosome, keep_hourly=True)
    destination = Path(destination)
    write_project_report(case, result, simulation, destination,
                         make_figures=origin_figures, synthetic=True)
    # 对外给出与工作簿一致的机器可读验收摘要，不包含本机路径。
    audit = {"synthetic": True, "candidate_bits": len(case.candidates),
             "selected_chromosome": list(result.best.chromosome),
             "feasible": result.best.feasible, "stop_reason": result.stop_reason,
             "generations_recorded": len(result.history),
             "unique_evaluations": result.evaluations,
             "total_cost_yuan": result.best.total_cost_yuan,
             "unserved_mwh": simulation.summary["unserved"],
             "online_reserve_shortfall_mwh": simulation.summary["reserve_shortfall"],
             "max_balance_residual_mw": simulation.summary["max_balance_residual_mw"],
             "storage_asset_hours": len(simulation.storage_hourly)}
    (destination / "synthetic_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main():
    """CLI只接收输出目录和随机种子；私有数据库不是本脚本输入。"""
    parser = argparse.ArgumentParser(description="完整合成遗传规划与全年运行案例")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--population", type=int, default=24)
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--seed", type=int, default=19)
    parser.add_argument("--origin-figures", action="store_true")
    args = parser.parse_args()
    print(json.dumps(execute(args.output, args.population, args.generations,
                             args.seed, args.origin_figures), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
