"""GRIDMIND项目算例输出：图表分目录、同一工作簿、逐时原值和存档清单。"""

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from openpyxl import Workbook

from ..common.domain import PLANNING_MONTH_HOURS
from ..data_collection.project_case import TECH_LABELS
from .origin_plot import plot_project_results
from .tables import _add_sheet, _write_csv


HOUR_LABELS = ["小时", "本地负荷MW", "外送MW", "总需求MW", "煤电MW", "燃气MW",
               "常规水电MW", "生物质MW", "风电可用MW", "光伏可用MW", "风电实际MW",
               "光伏实际MW", "弃风MW", "弃光MW", "抽蓄充电MW", "抽蓄放电MW",
               "电池充电MW", "电池放电MW", "储能总充电MW", "储能总放电MW",
               "储能期末库存MWh", "火电合计MW", "缺供MW", "备用需求MW",
               "可用备用MW", "备用缺口MW", "过剩MW", "平衡残差MW"]


def _hash_file(path):
    """输入快照哈希使同名结果可追溯到当时数据库版本。"""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _periods(hourly, lengths):
    """逐时功率按1h积分；本地负荷、外送和八类资源分别汇总。"""
    fields = ("domestic_load_mw", "export_mw", "load_mw", "coal_mw", "gas_mw",
              "hydro_mw", "biomass_mw", "wind_mw", "solar_mw", "pumped_charge_mw",
              "pumped_discharge_mw", "battery_charge_mw", "battery_discharge_mw",
              "wind_curtailment_mw", "solar_curtailment_mw", "unserved_mw",
              "reserve_shortfall_mw")
    labels = ["本地负荷MWh", "外送MWh", "总需求MWh", "煤电MWh", "燃气MWh",
              "常规水电MWh", "生物质MWh", "风电MWh", "光伏MWh", "抽蓄充电MWh",
              "抽蓄放电MWh", "电池充电MWh", "电池放电MWh", "弃风MWh", "弃光MWh",
              "缺供MWh", "备用不足MW·h"]
    rows, start = [], 0
    for index, size in enumerate(lengths, 1):
        part = hourly[start:start + size]
        rows.append([index, start, start + size - 1, max(h.load_mw for h in part)] +
                    [sum(getattr(h, field) for h in part) for field in fields])
        start += size
    if start != 8760:
        raise ValueError("日/月分段未覆盖完整8760小时")
    return ["序号", "开始小时", "结束小时", "最大总需求MW"] + labels, rows


def write_project_report(case, result, simulation, output_dir: Path, make_figures=True,
                         synthetic=False):
    """所有表格合入一个XLSX，图片和工程进入独立figures目录。"""
    if len(simulation.hourly) != 8760:
        raise ValueError("归档需要完整8760小时结果")
    tables = output_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    hourly = simulation.hourly
    selected = result.best.chromosome if result else (0,) * len(case.candidates)
    _write_csv(tables / "hourly_dispatch.csv", list(asdict(hourly[0])),
               (list(asdict(h).values()) for h in hourly))
    if simulation.storage_hourly:
        _write_csv(tables / "storage_hourly.csv",
                   ["hour", "station", "technology", "charge_mw", "discharge_mw",
                    "energy_start_mwh", "energy_end_mwh", "soc_end", "state_residual_mwh"],
                   simulation.storage_hourly)
    project_rows = (["存量含外生计划" if p.annual_cost_yuan > 0 else "存量",
                     p.station_id, p.name, TECH_LABELS[p.technology], p.capacity_mw,
                     1, p.annual_cost_yuan]
                    for p in case.existing)
    project_rows = list(project_rows) + [
        ["候选", p.station_id, p.name, TECH_LABELS[p.technology], p.capacity_mw, bit, p.annual_cost_yuan]
        for p, bit in zip(case.candidates, selected)]
    _write_csv(tables / "projects.csv", ["类别", "电站ID", "电站", "技术", "容量MW", "入选", "年化资本费元"],
               project_rows)
    history_rows = []
    if result:
        history_rows = [[h.generation, h.best_cost_yuan, h.generation_best_cost_yuan,
                         h.mean_cost_yuan, h.median_cost_yuan, h.feasible_count,
                         h.unique_count, h.best_violation, "".join(map(str, h.best_chromosome))]
                        for h in result.history]
        _write_csv(tables / "history.csv",
                   ["代数", "历代最优元", "本代最优元", "可行种群均值元", "可行种群中位数元",
                    "可行个体数", "不同染色体数", "最优违约程度", "历代最优染色体"], history_rows)
    summary = simulation.summary
    overview = [["基年", case.base_year, "年"], ["目标年", case.target_year, "年"],
                ["规划状态", "可行" if result and result.best.feasible else "仅模拟" if result is None else "不可行", ""],
                ["规划年化资本费", result.best.annual_fixed_cost_yuan if result else 0, "元/年"],
                ["运行变动费用", summary["variable_cost"], "元/年"],
                ["年总成本", (result.best.total_cost_yuan if result else summary["variable_cost"]), "元/年"],
                ["本地负荷", summary["domestic_load"], "MWh"],
                ["固定外送", summary["export"], "MWh"],
                ["缺供电量", summary["unserved"], "MWh"],
                ["缺供小时数", summary["shortage_hours"], "h"],
                ["在线备用不足积分", summary["reserve_shortfall"], "MW·h"],
                ["最大功率平衡残差", summary["max_balance_residual_mw"], "MW"],
                ["水电未用月预算", summary["hydro_unused_budget_mwh"], "MWh"]]
    for kind in ("coal", "gas", "hydro", "biomass", "wind", "solar"):
        overview.append([TECH_LABELS[kind] + "实际发电量", summary[kind], "MWh"])
    for kind in ("pumped", "battery"):
        overview.append([TECH_LABELS[kind] + "充电量", summary[kind + "_charge"], "MWh"])
        overview.append([TECH_LABELS[kind] + "放电量", summary[kind + "_discharge"], "MWh"])
    overview += [["弃风", summary["wind_curtailment"], "MWh"],
                 ["弃光", summary["solar_curtailment"], "MWh"],
                 ["储能年末内部库存", summary["storage_final_mwh"], "MWh"]]
    _write_csv(tables / "summary.csv", ["指标", "数值", "单位"], overview)
    book = Workbook()
    book.remove(book.active)
    _add_sheet(book, "年度总览", ["指标", "数值", "单位"], overview, 6)
    _add_sheet(book, "电站装机", ["类别", "电站ID", "电站", "技术", "容量MW", "入选", "年化资本费元"], project_rows)
    _add_sheet(book, "8760小时平衡", HOUR_LABELS, (list(asdict(h).values()) for h in hourly), 6)
    if simulation.storage_hourly:
        _add_sheet(book, "储能逐时", ["小时", "电站", "技术", "充电MW", "放电MW", "期初MWh",
                                  "期末MWh", "期末SOC", "状态残差MWh"], simulation.storage_hourly, 6)
    day_header, day_rows = _periods(hourly, [24] * 365)
    _add_sheet(book, "逐日统计", day_header, day_rows, 4)
    # 闰年输入也固定省略2月29日；报表与水电月预算采用同一8760小时边界。
    month_header, month_rows = _periods(hourly, PLANNING_MONTH_HOURS)
    _add_sheet(book, "逐月统计", month_header, month_rows, 4)
    if history_rows:
        _add_sheet(book, "遗传迭代", ["代数", "历代最优元", "本代最优元", "可行均值元",
                                  "可行中位元", "可行个体数", "不同染色体数", "最优违约程度",
                                  "历代最优染色体"], history_rows, 6)
    _add_sheet(book, "资料校核", ["序号", "校核结果"],
               [[i, warning] for i, warning in enumerate(case.warnings, 1)])
    _add_sheet(book, "口径说明", ["项目", "说明"], [
        ["数据来源", "公开合成脚本" if synthetic else case.source_folder],
        ["费用来源", "公开合成参数表 examples/synthetic_case_costs.csv" if synthetic else case.cost_file],
        ["基年/目标", f"{case.base_year}有效存量；{case.target_year}增量为候选项目"],
        ["外送", "联络线外送功率=额定MW×逐时外送系数，计入固定需求"],
        ["网架", "单区域合成模型，不含线路潮流" if synthetic else
         "库内电站均挂在节点1；本版不宣称完成省内交流潮流约束"],
        ["水电", "M1–M12水文相对系数×0.42试算利用率×容量×月小时数；月间不借用"],
        ["储能", "库容=额定MW×储能时长h；往返效率按平方根分解，年初SOC=0"],
        ["成本", "随算例公开的合成试算成本，不是项目报价" if synthetic else
         "官方美国技术基准经7.0试算汇率及7%贴现率换算；燃料费为可编辑情景假设"],
        ["可靠性", "风光/储能规划可信容量保守取0；不等于ELCC或概率可靠性认证"],
        ["时间", "365日规划年共8760小时；闰年省略2月29日；逐时功率和库存保留原始值"],
    ])
    book.save(tables / "全年规划运行结果汇总.xlsx")
    # 运行清单存哈希及文件路径；费用参数拷贝到当次tables供以后复算。
    shutil.copy2(case.cost_file, tables / "技术经济参数快照.csv")
    source = Path(case.source_folder)
    # 合成发布不假造外部数据库文件哈希；真实项目仍逐年记录源工作簿哈希。
    source_hashes = ({} if synthetic else {
        str(year): _hash_file(source / str(year) / f"{year}.xlsx")
        for year in {case.base_year, case.target_year}})
    manifest = {"app": "GRIDMIND", "base_year": case.base_year,
                "target_year": case.target_year,
                "source_folder": "synthetic" if synthetic else case.source_folder,
                "synthetic": bool(synthetic), "source_workbook_sha256": source_hashes,
                "cost_sha256": _hash_file(Path(case.cost_file)),
                "selected_chromosome": list(selected), "warnings": list(case.warnings),
                "figures_created": bool(make_figures)}
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if make_figures:
        plot_project_results(case, result, simulation, output_dir)
    return output_dir
