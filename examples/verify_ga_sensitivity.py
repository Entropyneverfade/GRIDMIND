"""从公开的完整阶段状态费用CSV，独立核对GA预算试验账本。"""

import argparse
import csv
import json
from collections import defaultdict
from math import isclose
from pathlib import Path


def _csv_rows(path):
    """以完整浮点文本读表；不使用图片或工作簿中的展示舍入值。"""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _result_path(directory, run_name, published_name):
    """同一验收器兼容脚本原生文件名和公开归档时的说明性文件名。"""
    native = directory / run_name
    public = directory / published_name
    if native.is_file():
        return native
    if public.is_file():
        return public
    raise FileNotFoundError(f"缺少预算试验结果：{native} 或 {public}")


def verify(destination: Path, reference_states: Path):
    """核算80条路径的建设单调性、硬约束、贴现费用和预算汇总。"""
    destination = Path(destination)
    audit_path = _result_path(destination, "sensitivity_audit.json", "ga_sensitivity_audit.json")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("synthetic") is not True or audit.get("status") != "PASS":
        raise AssertionError("只验收已标记合成且完成物理核验的试验")
    costs = {}
    for row in _csv_rows(reference_states):
        key = (int(row["规划年"]), int(row["状态整数"]))
        if key in costs:
            raise AssertionError("完整阶段费用表有重复状态")
        costs[key] = (int(row["可行"]), float(row["年总费用元"]))
    years = tuple(audit["years"])
    if len(years) != 3 or len(costs) != 3 * 256:
        raise AssertionError("参考费用表须覆盖三个合成年份各256个状态")
    rate = 0.07
    dp_path = tuple(audit["dp_path"])
    dp_from_table = sum(costs[(year, state)][1] / (1 + rate) ** t
                        for t, (year, state) in enumerate(zip(years, dp_path)))
    if not isclose(dp_from_table, audit["dp_objective_yuan"], abs_tol=0.01) or not isclose(
            dp_from_table, audit["gurobi_objective_yuan"], abs_tol=0.01):
        raise AssertionError("Bellman/Gurobi基准目标与公开阶段费用表不一致")
    rows = _csv_rows(_result_path(destination, "seed_sweep.csv", "ga_sensitivity_seeds.csv"))
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        budget = (int(row["种群数"]), int(row["最多代数"]))
        seed = int(row["随机种子"])
        if budget not in [tuple(item) for item in audit["budgets"]] or (budget, seed) in seen:
            raise AssertionError("预算/种子重复或未声明")
        seen.add((budget, seed))
        path = tuple(int(row[f"{year}状态"]) for year in years)
        previous = 0
        objective = 0.0
        for t, (year, state) in enumerate(zip(years, path)):
            if state & previous != previous or costs[(year, state)][0] != 1:
                raise AssertionError("GA路径退出项目或含不可行年度状态")
            # 逐行重算 J=Σ_t c_t(s_t)/(1+0.07)^t，与GA源码相互独立。
            objective += costs[(year, state)][1] / (1 + rate) ** t
            previous = state
        gap = (objective - dp_from_table) / dp_from_table
        if gap < -1e-10 or not isclose(objective, float(row["GA折现总费用元"]), abs_tol=0.01):
            raise AssertionError("GA目标值不等于同表阶段成本之和")
        if not isclose(gap, float(row["相对DP差距"]), abs_tol=1e-10):
            raise AssertionError("相对差距计算不一致")
        if int(row["是否达到DP最优"]) != int(gap <= 1e-10):
            raise AssertionError("达到最优的判别标记错误")
        groups[budget].append((seed, gap))
    if len(rows) != 80 or len(groups) != 4:
        raise AssertionError("预算试验应含4组×20种子=80条路径")
    summary_path = _result_path(destination, "budget_summary.csv", "ga_sensitivity_summary.csv")
    for item in _csv_rows(summary_path):
        budget = (int(item["种群数"]), int(item["最多代数"]))
        outcomes = groups[budget]
        if sorted(seed for seed, _ in outcomes) != audit["seeds"]:
            raise AssertionError("每组随机种子集合不完整")
        gaps = [gap for _, gap in outcomes]
        if int(item["种子数"]) != len(gaps) or int(item["达到DP最优的种子数"]) != sum(
                gap <= 1e-10 for gap in gaps):
            raise AssertionError("预算组命中数不一致")
        if not isclose(float(item["平均相对差距"]), sum(gaps) / len(gaps), abs_tol=1e-10):
            raise AssertionError("平均差距不一致")
        if not isclose(float(item["最大相对差距"]), max(gaps), abs_tol=1e-10):
            raise AssertionError("最大差距不一致")
    if audit["selected_unique_annual_states_replayed"] < 3 or audit["max_balance_residual_mw"] > 1e-8 or audit[
            "max_storage_residual_mwh"] > 1e-8:
        raise AssertionError("物理复算证据不足或残差超限")
    return {"status": "PASS", "synthetic": True, "paths_checked": len(rows),
            "reference_annual_states": len(costs), "budget_groups": len(groups),
            "dp_gurobi_gap_yuan": audit["dp_objective_yuan"] - audit["gurobi_objective_yuan"]}


def main():
    """显式传入合成结果目录及公开阶段费用表，避免读取其他算例。"""
    parser = argparse.ArgumentParser(description="独立核对三年度合成GA预算试验")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-states", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output, args.reference_states), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
