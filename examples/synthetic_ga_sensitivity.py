"""固定同一张三年度合成费用表，量化多阶段GA的搜索预算敏感性。"""

import argparse
import csv
import hashlib
import json
from math import isclose
from pathlib import Path

from examples.synthetic_dynamic_case import build_stages
from power_ga.common.domain import GASettings
from power_ga.dynamic_planning import compare_ga_on_stages, solve_stage_planning
from power_ga.operation_simulation.project_engine import simulate_project


# 只改变种群和最多代数；精英、交叉、变异及停滞参数在所有组保持一致。
BUDGETS = ((8, 4), (10, 6), (12, 12), (64, 80))
SEEDS = tuple(range(1, 21))


def _table_fingerprint(cases, tables):
    """按固定状态顺序哈希原始阶段费用/可行性，证明各组共用同一物理评价表。"""
    digest = hashlib.sha256()
    for case, table in zip(cases, tables):
        for state, item in sorted(table.items()):
            record = (case.target_year, state, item.feasible,
                      item.annual_fixed_cost_yuan, item.variable_cost_yuan,
                      item.total_cost_yuan, item.violation)
            digest.update((json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
    return digest.hexdigest()


def _physical_replay(cases, tables, visited):
    """对80次GA最终路径用到的不同年度状态独立复算8760小时与储能守恒。"""
    max_balance = max_storage = 0.0
    count = len(cases[0].candidates)
    for stage, state in sorted(visited):
        bits = tuple((state >> bit) & 1 for bit in range(count))
        simulation = simulate_project(cases[stage], bits, keep_hourly=True)
        item = tables[stage][state]
        if not item.feasible or len(simulation.hourly) != 8760:
            raise AssertionError("选中状态必须可行且完整保留8760小时")
        balance = max(abs(hour.balance_residual_mw) for hour in simulation.hourly)
        storage = max((abs(row[-1]) for row in simulation.storage_hourly), default=0.0)
        if balance > 1e-8 or storage > 1e-8:
            raise AssertionError(f"阶段{stage}状态{state}功率或储能不守恒")
        max_balance = max(max_balance, balance)
        max_storage = max(max_storage, storage)
    return len(visited), max_balance, max_storage


def execute(destination: Path):
    """先以Bellman/Gurobi建立同一参考最优，再输出20种随机种子的预算比较。"""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    cases = build_stages(full_horizon=True)
    # c_t(s)由每年8760小时评价一次；后续80次GA只查此表，不重复调度。
    dp = solve_stage_planning(cases, 0.07)
    fingerprint = _table_fingerprint(cases, dp.evaluations)
    rows, visited, summary = [], set(), []
    for population, generations in BUDGETS:
        group = []
        for seed in SEEDS:
            settings = GASettings(population, generations, 1, 5, 2, 0.85, 0.045, seed)
            ga, path = compare_ga_on_stages(cases, dp.evaluations, 0.07, settings)
            if not ga.best.feasible:
                raise AssertionError(f"预算{population}/{generations}种子{seed}没有可行路径")
            previous = 0
            ledger = 0.0
            for stage, state in enumerate(path):
                if state & previous != previous or not dp.evaluations[stage][state].feasible:
                    raise AssertionError("GA累计状态退出或阶段不满足硬约束")
                # C(path)=Σ_t c_t(s_t)/(1+r)^t；直接对选中状态重新求和。
                ledger += dp.evaluations[stage][state].total_cost_yuan / 1.07 ** stage
                visited.add((stage, state))
                previous = state
            if not isclose(ledger, ga.best.total_cost_yuan, rel_tol=1e-10, abs_tol=0.01):
                raise AssertionError("GA评价对象与阶段费用账本不一致")
            gap = (ledger - dp.objective_yuan) / dp.objective_yuan
            if gap < -1e-10:
                raise AssertionError("GA费用低于Bellman/Gurobi同表最优费用")
            group.append(gap)
            rows.append((population, generations, seed, ga.evaluations,
                         len(ga.history) - 1, int(gap <= 1e-10),
                         ledger, gap, *path))
        # 成功率只指这20个固定种子，在这个教学算例和此初代策略下成立。
        summary.append((population, generations, len(SEEDS),
                        sum(gap <= 1e-10 for gap in group),
                        sum(group) / len(group), max(group)))
    replayed, max_balance, max_storage = _physical_replay(cases, dp.evaluations, visited)
    with (destination / "seed_sweep.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("种群数", "最多代数", "随机种子", "不同GA染色体评价数", "实际终止代数",
                         "是否达到DP最优", "GA折现总费用元", "相对DP差距", "2026状态", "2027状态", "2028状态"))
        writer.writerows(rows)
    with (destination / "budget_summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("种群数", "最多代数", "种子数", "达到DP最优的种子数",
                         "平均相对差距", "最大相对差距"))
        writer.writerows(summary)
    audit = {"synthetic": True, "status": "PASS", "years": [case.target_year for case in cases],
             "hours_per_year": 8760, "annual_states_evaluated": dp.evaluated_states,
             "table_sha256": fingerprint, "dp_objective_yuan": dp.objective_yuan,
             "gurobi_objective_yuan": dp.gurobi_objective_yuan,
             "dp_path": [stage.state for stage in dp.stages], "seeds": list(SEEDS),
             "budgets": [list(budget) for budget in BUDGETS],
             "ga_settings_fixed": {"min_generations": 1, "stall_generations": 5,
                                   "elite_count": 2, "crossover_rate": 0.85,
                                   "mutation_rate": 0.045},
             "initial_population_policy": "两个基准方案+按末年到首年的单项目建设种子，余位随机；种群容量截断种子列表",
             "selected_unique_annual_states_replayed": replayed,
             "max_balance_residual_mw": max_balance,
             "max_storage_residual_mwh": max_storage,
             "summary": [dict(zip(("population", "max_generations", "seeds", "hits",
                                   "mean_gap", "max_gap"), group)) for group in summary]}
    (destination / "sensitivity_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main():
    """公开可复现入口：结果只写到显式指定的合成输出目录。"""
    parser = argparse.ArgumentParser(description="合成三年度GA预算与随机种子敏感性")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
