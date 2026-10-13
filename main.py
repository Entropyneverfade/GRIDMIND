"""入口：读取输入 -> Gen=0 -> 运行模拟/评价 -> 遗传迭代 -> 输出。"""

import argparse
from dataclasses import replace
from pathlib import Path

from power_ga.data_collection.reader import load_problem
from power_ga.initial_population.encoding import decode
from power_ga.genetic_iteration.solver import optimize
from power_ga.result_output.tables import write_results


def main():
    """按框图编排数据、Gen=0、运行评价、GA迭代、工作簿和图形输出。"""
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="简化电源规划遗传算法")
    parser.add_argument("--config", type=Path, default=root / "input" / "config.json")
    parser.add_argument("--profiles", type=Path, default=root / "input" / "hourly_profiles.csv")
    parser.add_argument("--output", type=Path, default=root / "output")
    parser.add_argument("--skip-figures", action="store_true",
                        help="只运行计算和保存表格；不启动Origin")
    parser.add_argument("--dispatch-mode", choices=["rules", "gurobi"])
    args = parser.parse_args()
    # 第1步：读取并验证外部数据，形成所有模块共用的只读数据对象。
    problem, settings = load_problem(args.config, args.profiles)
    if args.dispatch_mode:
        # replace生成新只读问题对象；不修改输入文件中的模式配置。
        problem = replace(problem, dispatch_mode=args.dispatch_mode)
    # 第2步：GA内部生成Gen=0，循环执行运行模拟、评价和遗传迭代。
    result = optimize(problem, settings)
    # 第3步：对最终方案保存逐时表，并使用Origin生成可编辑工程和图片。
    write_results(problem, result, args.output, make_figures=not args.skip_figures)
    print("所选电站:", "、".join(decode(problem, result.best.chromosome)) or "无")
    print("年总成本: {:.2f} 万元".format(result.best.total_cost_yuan / 1e4))
    print("可行:", "是" if result.best.feasible else "否")
    print("终止原因:", result.stop_reason)
    print("结果目录:", args.output.resolve())


if __name__ == "__main__":
    main()
