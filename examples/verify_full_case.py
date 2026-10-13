"""八位合成案例的256种建设组合穷举，用作遗传规划独立对照。"""

import argparse
import itertools
import json
from pathlib import Path

from examples.synthetic_eight_type import build_case
from power_ga.genetic_iteration.project_solver import evaluate_project


def verify(output: Path):
    """对每个0/1向量调用同一物理评价器，但不使用GA选择过程。"""
    case = build_case(with_candidates=True)
    best, feasible_count = None, 0
    for chromosome in itertools.product((0, 1), repeat=len(case.candidates)):
        result = evaluate_project(case, chromosome)
        feasible_count += int(result.feasible)
        if best is None or result.sort_key() < best.sort_key():
            best = result
    report = {"synthetic": True, "enumerated": 2 ** len(case.candidates),
              "feasible_count": feasible_count, "best_chromosome": list(best.chromosome),
              "best_feasible": best.feasible, "best_cost_yuan": best.total_cost_yuan}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    """保存不含项目路径的合成穷举结果，供阶段报告核对GA最优值。"""
    parser = argparse.ArgumentParser(description="穷举验证八位合成遗传规划")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
