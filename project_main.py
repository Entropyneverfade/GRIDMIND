"""GRIDMIND真实项目命令行入口；桌面窗口与脚本共用同一计算流程。"""

import argparse
import hashlib
import json
import struct
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from power_ga.common.domain import GASettings
from power_ga.data_collection.project_case import align_stage_case, load_project_case
from power_ga.genetic_iteration.project_solver import optimize_project
from power_ga.dynamic_planning import compare_ga_on_stages, solve_stage_planning
from power_ga.operation_simulation.project_engine import simulate_project
from power_ga.result_output.project_report import write_project_report
from power_ga.result_output.dynamic_report import write_dynamic_report


ROOT = Path(__file__).resolve().parent
DEFAULT_COST = ROOT / "input" / "project_costs.csv"


def _stage_input_hash(case):
    """哈希真正参与该阶段运行的数值曲线；只存指纹，不复制私有逐时数据。"""
    digest = hashlib.sha256()
    for values in (case.domestic_load_mw, case.export_mw):
        for value in values:
            digest.update(struct.pack("<d", float(value)))
    digest.update(struct.pack("<d", float(case.reserve_margin)))
    for plant in case.existing + case.candidates:
        digest.update(f"{plant.station_id}:{plant.technology}".encode("utf-8"))
        for value in (plant.capacity_mw, plant.min_fraction,
                      plant.variable_cost_yuan_per_mwh, plant.annual_cost_yuan,
                      plant.storage_hours, plant.charge_ratio,
                      plant.roundtrip_efficiency):
            digest.update(struct.pack("<d", float(value)))
        for value in plant.profile + plant.hydro_monthly_factor:
            digest.update(struct.pack("<d", float(value)))
    return digest.hexdigest()


def execute(source: Path, year: int, costs: Path, output: Path, *,
            plan=True, figures=True, population=12, generations=12, seed=1,
            progress=None, algorithm="ga", previous_load_factor=0.95,
            stage_input_mode="source"):
    """数据采集→选择GA或双年度DP→最终年8760h模拟→表/图存档。"""
    if algorithm not in {"ga", "dp"}:
        raise ValueError("规划算法只能是ga或dp")
    if stage_input_mode not in {"source", "scaled"}:
        raise ValueError("动态规划阶段输入只能选择年度源库或负荷系数情景")
    case = load_project_case(source, year, costs)
    if plan and algorithm == "dp" and not case.candidates:
        raise ValueError("动态规划没有候选项目；可改选仅模拟存量系统")
    if progress:
        progress(f"已读取{len(case.existing)}座存量电站、{len(case.candidates)}个候选容量段")
    result = None
    ga_comparison = None
    exogenous_projects = ()
    if plan and algorithm == "dp" and case.candidates:
        if year <= case.base_year + 1:
            raise ValueError("双年度动态规划的目标年须至少比基年晚2年，避免在基年预建候选项目")
        if stage_input_mode == "scaled" and not 0 < previous_load_factor <= 1:
            raise ValueError("前一年负荷系数须在(0,1]内")
        if stage_input_mode == "source":
            # 逐年库提供本地负荷、外送、风光、水文及有效容量；终期候选位由规划器决定。
            # 仅当年出现而终期没有的计划增量作为外生年度投运并付等年值费用。
            annual_source = load_project_case(source, year - 1, costs)
            terminal_ids = {plant.station_id for plant in case.candidates}
            exogenous_projects = tuple(plant for plant in annual_source.candidates
                                       if plant.station_id not in terminal_ids)
            preceding = align_stage_case(case, annual_source)
        else:
            # 缺少独立年度预测时，用户可显式用目标年曲线构造负荷情景。
            preceding = replace(case, target_year=year - 1,
                                domestic_load_mw=tuple(previous_load_factor * value
                                                       for value in case.domestic_load_mw))
        if progress:
            progress("动态规划：正在评价双年度投运状态与全年运行")
        result = solve_stage_planning((preceding, case), progress=progress)
        # GA在已经审计的同一年度状态费用表上搜索，不重算或替换8760小时模型。
        comparison_settings = GASettings(population_size=population,
                                         max_generations=generations,
                                         min_generations=min(4, generations),
                                         stall_generations=4, elite_count=1,
                                         crossover_rate=0.8, mutation_rate=0.07,
                                         seed=seed)
        ga_comparison = compare_ga_on_stages((preceding, case), result.evaluations,
                                             result.discount_rate, comparison_settings)
        if progress:
            progress("已完成同口径双年度GA与DP对照")
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
        write_dynamic_report(result, case, output, previous_load_factor,
                             stage_input_mode=stage_input_mode,
                             ga_comparison=ga_comparison,
                             exogenous_projects=exogenous_projects)
        manifest_path = Path(output) / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["planning_algorithm"] = "dynamic_programming"
        manifest["stage_input_mode"] = stage_input_mode
        manifest["stage_input_sha256"] = {
            str(preceding.target_year): _stage_input_hash(preceding),
            str(case.target_year): _stage_input_hash(case)}
        if stage_input_mode == "source":
            # 终期清单原有基年/目标年哈希；补入前一年源工作簿以支持阶段复算。
            workbook = Path(source) / str(year - 1) / f"{year - 1}.xlsx"
            manifest["source_workbook_sha256"][str(year - 1)] = hashlib.sha256(
                workbook.read_bytes()).hexdigest()
            manifest["stage_source_warnings"] = list(preceding.warnings)
        if stage_input_mode == "scaled":
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
    parser.add_argument("--stage-input-mode", choices=("source", "scaled"), default="source")
    args = parser.parse_args()
    output = args.output or ROOT / "runs" / f"scenario_{args.year}_{datetime.now():%Y%m%d_%H%M%S}"
    case, result, simulation, destination = execute(args.source, args.year, args.costs, output,
                                                  plan=not args.simulate_only,
                                                  figures=not args.skip_figures,
                                                  population=args.population,
                                                  generations=args.generations,
                                                  seed=args.seed, progress=print,
                                                  algorithm=args.algorithm,
                                                  previous_load_factor=args.previous_load_factor,
                                                  stage_input_mode=args.stage_input_mode)
    if args.algorithm == "dp" and result is not None:
        selected = result.stages[-1].state
        print("规划方案:", "".join(str((selected >> i) & 1) for i in range(len(case.candidates))))
    else:
        print("规划方案:", "".join(map(str, result.best.chromosome)) if result else "仅模拟")
    print("缺供MWh:", simulation.summary["unserved"])
    print("结果:", destination.resolve())


if __name__ == "__main__":
    main()
