"""GRIDMIND真实项目命令行入口；桌面窗口与脚本共用同一计算流程。"""

import argparse
from datetime import datetime
from pathlib import Path

from power_ga.common.domain import GASettings
from power_ga.data_collection.project_case import load_project_case
from power_ga.genetic_iteration.project_solver import optimize_project
from power_ga.operation_simulation.project_engine import simulate_project
from power_ga.result_output.project_report import write_project_report


ROOT = Path(__file__).resolve().parent
DEFAULT_COST = ROOT / "input" / "project_costs.csv"


def execute(source: Path, year: int, costs: Path, output: Path, *,
            plan=True, figures=True, population=12, generations=12, seed=1,
            progress=None):
    """数据采集→Gen0/GA→8760h最佳方案模拟→表/图存档。"""
    case = load_project_case(source, year, costs)
    if progress:
        progress(f"已读取{len(case.existing)}座存量电站、{len(case.candidates)}个候选容量段")
    result = None
    if plan and case.candidates:
        settings = GASettings(population_size=population, max_generations=generations,
                              min_generations=min(4, generations), stall_generations=4,
                              elite_count=1, crossover_rate=0.8, mutation_rate=0.07, seed=seed)
        def on_generation(row, maximum):
            """逐代传递费用、可行数，窗口线程通过消息队列显示。"""
            if progress:
                progress(f"遗传代 {row.generation}/{maximum}；最优成本 {row.best_cost_yuan / 1e8:.2f} 亿元/年；可行 {row.feasible_count}")
        result = optimize_project(case, settings, on_generation)
        chromosome = result.best.chromosome
    else:
        chromosome = (0,) * len(case.candidates)
    if progress:
        progress("正在保存最佳方案的完整8760小时运行轨迹")
    simulation = simulate_project(case, chromosome, keep_hourly=True)
    if progress:
        progress("正在合并工作簿和归档输入快照")
    write_project_report(case, result, simulation, output, make_figures=figures)
    if progress:
        progress("完成：" + str(output))
    return case, result, simulation, output


def main():
    """命令行参数均有显式路径；不修改用户的项目源数据库。"""
    parser = argparse.ArgumentParser(description="GRIDMIND全年电源规划与运行模拟")
    parser.add_argument("--source", type=Path, required=True, help="项目数据库目录")
    parser.add_argument("--year", type=int, default=2029, choices=range(2025, 2030))
    parser.add_argument("--costs", type=Path, default=DEFAULT_COST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--simulate-only", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--generations", type=int, default=12)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    output = args.output or ROOT / "runs" / f"scenario_{args.year}_{datetime.now():%Y%m%d_%H%M%S}"
    _, result, simulation, destination = execute(args.source, args.year, args.costs, output,
                                                  plan=not args.simulate_only,
                                                  figures=not args.skip_figures,
                                                  population=args.population,
                                                  generations=args.generations,
                                                  seed=args.seed, progress=print)
    print("规划方案:", "".join(map(str, result.best.chromosome)) if result else "仅模拟")
    print("缺供MWh:", simulation.summary["unserved"])
    print("结果:", destination.resolve())


if __name__ == "__main__":
    main()
