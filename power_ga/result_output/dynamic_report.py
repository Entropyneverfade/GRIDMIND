"""多年度动态规划结果归档；与最终年份8760小时工作簿分开。"""

import csv
import json
from pathlib import Path

from openpyxl import Workbook


def write_dynamic_report(result, case, output: Path, load_factor: float):
    """保存阶段状态、建站位与费用，便于EXE下次直接载入画规划图。"""
    tables = Path(output) / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    headers = ("规划年", "累计状态整数", "当年新增位掩码", "当年新增电站",
               "年度费用元", "折现费用元", "最大功率平衡残差MW")
    rows = []
    for stage in result.stages:
        names = "+".join(plant.name for bit, plant in enumerate(case.candidates)
                         if stage.newly_built & (1 << bit)) or "无"
        rows.append((stage.year, stage.state, stage.newly_built, names,
                     stage.annual_cost_yuan, stage.discounted_cost_yuan,
                     stage.max_balance_residual_mw))
    with (tables / "dynamic_stages.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    book = Workbook()
    sheet = book.active
    sheet.title = "动态规划阶段"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    notes = book.create_sheet("模型口径")
    for item in (("项目", "说明"),
                 ("算法", "按年份Bellman状态递推；Gurobi 0/1状态选择模型独立核验"),
                 ("前一年负荷系数", load_factor),
                 ("曲线", "前一年复用目标年风光曲线；这是可编辑预测情景，并非历史复原"),
                 ("费用", "年化建设费用+8760小时运行变动费；次年折现"),
                 ("物理边界", "单区域确定性运行，不含网络潮流与概率可靠性")):
        notes.append(item)
    book.save(tables / "动态规划阶段汇总.xlsx")
    # 不重复写入源路径；源文件哈希由最终年运行存档清单保存。
    (Path(output) / "dynamic_audit.json").write_text(json.dumps({
        "algorithm": "dynamic_programming", "years": [s.year for s in result.stages],
        "states": [s.state for s in result.stages],
        "objective_yuan": result.objective_yuan,
        "gurobi_objective_yuan": result.gurobi_objective_yuan,
        "discount_rate": result.discount_rate, "previous_load_factor": load_factor,
        "max_balance_residual_mw": max(s.max_balance_residual_mw for s in result.stages)
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
