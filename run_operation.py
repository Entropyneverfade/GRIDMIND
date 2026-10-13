"""固定规划方案的运行模式比较入口；读取GA结果，不重新执行遗传搜索。"""

import argparse
import csv
from dataclasses import replace
from pathlib import Path

from power_ga.data_collection.reader import load_problem
from power_ga.operation_simulation import simulate
from power_ga.fitness_and_convergence.evaluation import evaluate
from power_ga.genetic_iteration.solver import GAResult
from power_ga.result_output.tables import write_results


def main():
    """固定GA已选建设方案，只比较两种逐时调度，不重新搜索染色体。"""
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rules", "gurobi"], default="gurobi")
    parser.add_argument("--plan", type=Path, default=root / "output" / "tables" / "projects.csv")
    parser.add_argument("--skip-figures", action="store_true")
    args = parser.parse_args()
    problem, _ = load_problem(root / "input" / "config.json", root / "input" / "hourly_profiles.csv")
    problem = replace(problem, dispatch_mode=args.mode)
    with args.plan.open(encoding="utf-8-sig", newline="") as stream:
        decisions = {row["电站"]: int(row["是否建设"]) for row in csv.DictReader(stream)}
    # 染色体第i位必须对应候选电站第i个项目，不能按CSV出现顺序猜测。
    chromosome = tuple(decisions[p.name] for p in problem.candidates)
    simulation = simulate(problem, chromosome, keep_hourly=True)
    assessment = evaluate(problem, chromosome, simulation)
    result = GAResult(assessment, (), "固定规划方案运行模拟", 1)
    output = root / ("output_" + args.mode)
    write_results(problem, result, output, not args.skip_figures, simulation)
    print(f"{args.mode}: 年运行费 {simulation.variable_cost_yuan / 1e4:.2f}万元，ENS={simulation.unserved_mwh:.6f}MWh")
    print(f"输出: {output}")


if __name__ == "__main__":
    main()
