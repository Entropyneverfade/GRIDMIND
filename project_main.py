"""GRIDMIND真实项目命令行入口；桌面窗口与脚本共用同一计算流程。"""

import argparse
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from power_ga.common.domain import GASettings
from power_ga.data_collection.project_case import load_project_case
from power_ga.genetic_iteration.project_solver import optimize_project
from power_ga.dynamic_planning import solve_stage_planning
from power_ga.operation_simulation.project_engine import simulate_project
from power_ga.result_output.project_report import write_project_report
from power_ga.result_output.dynamic_report import write_dynamic_report


ROOT = Path(__file__).resolve().parent
DEFAULT_COST = ROOT / "input" / "project_costs.csv"


def execute(source: Path, year: int, costs: Path, output: Path, *,
            plan=True, figures=True, population=12, generations=12, seed=1,
            progress=None, algorithm="ga", previous_load_factor=0.95):
    """数据采集→选择GA或双年度DP→最终年8760h模拟→表/图存档。"""
    if algorithm not in {"ga", "dp"}:
        raise ValueError("规划算法只能是ga或dp")
    case = load_project_case(source, year, costs)
    if plan and algorithm == "dp" and not case.candidates:
        raise ValueError("动态规划没有候选项目；可改选仅模拟存量系统")
    if progress:
        progress(f"已读取{len(case.existing)}座存量电站、{len(case.candidates)}个候选容量段")
    result = None
    if plan and algorithm == "dp" and case.candidates:
        if year <= case.base_year + 1:
            raise ValueError("双年度动态规划的目标年须至少比基年晚2年，避免在基年预建候选项目")
        if not 0 < previous_load_factor <= 1:
            raise ValueError("前一年负荷系数须在(0,1]内")
        # 年度资料只用于目标年；前一年是用户显式指定的负荷情景，
        # 风光与候选参数保持一致，不能当作历史年份的实测重放。
        preceding = replace(case, target_year=year - 1,
                            domestic_load_mw=tuple(previous_load_factor * value
                                                   for value in case.domestic_load_mw))
        if progress:
            progress("动态规划：正在评价双年度投运状态与全年运行")
        result = solve_stage_planning((preceding, case), progress=progress)
        state = result.stages[-1].state
        chromosome = tuple((state >> i) & 1 for i in range(len(case.candidates)))
    elif plan and case.candidates:
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
    if plan and algorithm == "dp" and case.candidates:
        # 通用最终年报告需要best字段以列出被选项目；DP另存阶段工作簿。
        report_result = type("ReportResult", (), {
            "best": result.evaluations[-1][result.stages[-1].state], "history": ()})()
        write_project_report(case, report_result, simulation, output, make_figures=figures)
        write_dynamic_report(result, case, output, previous_load_factor)
        manifest_path = Path(output) / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["planning_algorithm"] = "dynamic_programming"
        manifest["previous_load_factor"] = previous_load_factor
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    else:
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
    parser.add_argument("--algorithm", choices=("ga", "dp"), default="ga")
    parser.add_argument("--previous-load-factor", type=float, default=0.95)
    args = parser.parse_args()
    output = args.output or ROOT / "runs" / f"scenario_{args.year}_{datetime.now():%Y%m%d_%H%M%S}"
    case, result, simulation, destination = execute(args.source, args.year, args.costs, output,
                                                  plan=not args.simulate_only,
                                                  figures=not args.skip_figures,
                                                  population=args.population,
                                                  generations=args.generations,
                                                  seed=args.seed, progress=print,
                                                  algorithm=args.algorithm,
                                                  previous_load_factor=args.previous_load_factor)
    if args.algorithm == "dp" and result is not None:
        selected = result.stages[-1].state
        print("规划方案:", "".join(str((selected >> i) & 1) for i in range(len(case.candidates))))
    else:
        print("规划方案:", "".join(map(str, result.best.chromosome)) if result else "仅模拟")
    print("缺供MWh:", simulation.summary["unserved"])
    print("结果:", destination.resolve())


if __name__ == "__main__":
    main()
