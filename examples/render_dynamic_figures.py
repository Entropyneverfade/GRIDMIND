"""从公开合成GA/DP结果表重建两张Origin原生算法图。"""

import argparse
import csv
from pathlib import Path

from power_ga.result_output.origin_plot import (
    plot_dynamic_stage_costs, plot_stage_ga_history)


def render(result: Path):
    """图与源表同源，避免报告图片沿用上一版数值。"""
    result = Path(result)
    tables = result / "tables"
    with (tables / "stage_comparison.csv").open(encoding="utf-8-sig", newline="") as stream:
        stages = list(csv.DictReader(stream))
    with (tables / "ga_history.csv").open(encoding="utf-8-sig", newline="") as stream:
        history = list(csv.DictReader(stream))
    plot_dynamic_stage_costs(
        [int(row["规划年"]) for row in stages],
        [float(row["DP阶段年费用元"]) for row in stages],
        [float(row["DP折现费用元"]) for row in stages],
        result / "figures")
    plot_stage_ga_history(
        [(int(row["代数"]), float(row["历代最优折现费用元"]),
          float(row["本代最优折现费用元"]), int(row["可行个体数"]),
          int(row["不同染色体数"])) for row in history],
        result / "figures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", required=True, type=Path)
    render(parser.parse_args().result)
