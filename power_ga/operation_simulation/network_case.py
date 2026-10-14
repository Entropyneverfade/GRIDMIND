"""分区CSV算例的统一入口：读取、逐时电力流、属性追踪与表格存档。"""

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from .attributes import PowerAttribute, trace_power_attributes
from .network import (Generator, Link, Zone, solve_network_hour,
                      solve_network_hour_heuristic)


STATIC_COLUMNS = {
    "zones.csv": ("zone",),
    "generators.csv": ("name", "zone", "technology", "minimum_mw", "maximum_mw",
                       "cost_yuan_per_mwh", "carbon_t_per_mwh",
                       "sulfur_kg_per_mwh", "renewable_fraction"),
    "links.csv": ("name", "source", "target", "limit_mw", "kind",
                  "susceptance_mw_per_rad"),
}
TECHNOLOGIES = ("coal", "gas", "hydro", "biomass", "nuclear", "csp",
                "oil", "geothermal")
HOUR_COLUMNS = ("hour", "zone", "demand_mw", "wind_available_mw",
                "solar_available_mw", "pumped_charge_mw", "pumped_discharge_mw",
                "battery_charge_mw", "battery_discharge_mw",
                "pumped_carbon_t_per_mwh", "pumped_sulfur_kg_per_mwh",
                "pumped_renewable_fraction", "battery_carbon_t_per_mwh",
                "battery_sulfur_kg_per_mwh", "battery_renewable_fraction")


def _rows(path, required):
    """检查列名与空表；UTF-8-BOM兼容Excel另存的CSV。"""
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}缺列：{','.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name}不能为空")
    return rows


def _number(row, field, *, nonnegative=True):
    """任何数值缺失或NaN都立即拒绝，避免静默流入优化。"""
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"数值字段错误：{field}") from error
    if not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError(f"数值字段越界：{field}={value}")
    return value


def _write_csv(path, headers, rows):
    """所有机读表独立进入tables目录，保留1小时步长原值。"""
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)


def run_network_case(source: Path, destination: Path, *, solver="heuristic",
                     expected_hours=8760, progress=None):
    """运行用户提供的分区CSV；固定储能充放电由输入给定，不在此优化库存。

    分区平衡按MW逐小时核对；属性满足 Mq=e，终端负荷及充电/溢出
    都计入源用守恒。交流边须选Gurobi LP；启发式只接受可控通道。
    """
    source, destination = Path(source), Path(destination)
    if solver not in {"heuristic", "gurobi"}:
        raise ValueError("分区求解模式应为heuristic或gurobi")
    if not isinstance(expected_hours, int) or expected_hours < 1:
        raise ValueError("预期小时数必须为正整数")
    files = {name: source / name for name in (*STATIC_COLUMNS, "hourly.csv")}
    if any(not path.is_file() for path in files.values()):
        raise FileNotFoundError("分区输入需要zones/generators/links/hourly四个CSV")
    zone_rows = _rows(files["zones.csv"], STATIC_COLUMNS["zones.csv"])
    names = tuple(row["zone"].strip() for row in zone_rows)
    if any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("分区名称必须非空且唯一")
    generator_rows = _rows(files["generators.csv"], STATIC_COLUMNS["generators.csv"])
    generators, factors = [], {}
    for row in generator_rows:
        name, zone = row["name"].strip(), row["zone"].strip()
        if not name or name in factors or zone not in names:
            raise ValueError("机组名称重复、空白或所属区域未知")
        technology = row["technology"].strip().lower()
        if technology not in TECHNOLOGIES:
            raise ValueError(f"机组类型须单列映射，不能合并或静默忽略：{technology}")
        generators.append(Generator(name, zone, _number(row, "minimum_mw"),
                                    _number(row, "maximum_mw"),
                                    _number(row, "cost_yuan_per_mwh"), technology))
        factor = PowerAttribute(_number(row, "carbon_t_per_mwh"),
                                _number(row, "sulfur_kg_per_mwh"),
                                _number(row, "renewable_fraction"))
        if factor.renewable_fraction > 1:
            raise ValueError("机组新能源属性份额不得超过1")
        factors[name] = factor
    links = []
    for row in _rows(files["links.csv"], STATIC_COLUMNS["links.csv"]):
        kind = row["kind"].strip().lower()
        b = (_number(row, "susceptance_mw_per_rad") if kind == "ac" else None)
        links.append(Link(row["name"].strip(), row["source"].strip(),
                          row["target"].strip(), _number(row, "limit_mw"), kind, b))
    if solver == "heuristic" and any(link.kind != "dc" for link in links):
        raise ValueError("含交流线路时必须使用Gurobi LP相角模型")
    input_rows = _rows(files["hourly.csv"], HOUR_COLUMNS)
    if len(input_rows) != expected_hours * len(names):
        raise ValueError("逐时行数必须等于小时数×分区数")
    # 先完整验证逐时覆盖，再创建结果目录；失败不会留下貌似完成的报告。
    indexed = {}
    for row in input_rows:
        try:
            hour = int(row["hour"])
        except (TypeError, ValueError) as error:
            raise ValueError("hour必须为整数") from error
        zone = row["zone"].strip()
        key = (hour, zone)
        if not 0 <= hour < expected_hours or zone not in names or key in indexed:
            raise ValueError("逐时数据小时越界、区域未知或键重复")
        indexed[key] = row
    if len(indexed) != expected_hours * len(names):
        raise ValueError("逐时数据不完整")
    # 每次运行使用全新存档，防止失败重试与旧版工作簿混在一个目录。
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"结果目录非空，请另选新目录：{destination}")
    destination.mkdir(parents=True, exist_ok=True)
    tables = destination / "tables"
    tables.mkdir(exist_ok=True)
    hourly_output, zone_totals = [], defaultdict(lambda: defaultdict(float))
    line_totals = defaultdict(lambda: {"absolute_mwh": 0.0, "signed_mwh": 0.0,
                                       "congested_hours": 0})
    max_power_gap = max_carbon_gap = max_sulfur_gap = max_re_gap = 0.0
    for hour in range(expected_hours):
        zones, storage_factors = [], {}
        storage_by_zone = {}
        for name in names:
            row = indexed[hour, name]
            pumped_charge, pumped_discharge = (_number(row, "pumped_charge_mw"),
                                                 _number(row, "pumped_discharge_mw"))
            battery_charge, battery_discharge = (_number(row, "battery_charge_mw"),
                                                   _number(row, "battery_discharge_mw"))
            zone = Zone(name, _number(row, "demand_mw"),
                        _number(row, "wind_available_mw"),
                        _number(row, "solar_available_mw"),
                        pumped_discharge + battery_discharge,
                        pumped_charge + battery_charge)
            zones.append(zone)
            storage_by_zone[name] = (pumped_charge, pumped_discharge,
                                     battery_charge, battery_discharge)
            if zone.fixed_discharge_mw > 0:
                # 抽蓄与电池各有独立输入因子，才按放电MWh加权得到区内混合放电属性。
                mix = [0.0, 0.0, 0.0]
                for technology, amount in (("pumped", pumped_discharge),
                                            ("battery", battery_discharge)):
                    if amount <= 0:
                        continue
                    factor = tuple(_number(row, f"{technology}_{field}") for field in
                                   ("carbon_t_per_mwh", "sulfur_kg_per_mwh",
                                    "renewable_fraction"))
                    if factor[2] > 1:
                        raise ValueError("储能放电新能源属性份额不得超过1")
                    for index, value in enumerate(factor):
                        mix[index] += amount * value
                storage_factors[name] = PowerAttribute(
                    *(value / zone.fixed_discharge_mw for value in mix))
        dispatch = (solve_network_hour(zones, generators, links) if solver == "gurobi" else
                    solve_network_hour_heuristic(zones, generators, links))
        traced = trace_power_attributes(zones, generators, links, dispatch,
                                        factors, storage_factors)
        max_power_gap = max(max_power_gap, dispatch.max_balance_residual_mw)
        max_carbon_gap = max(max_carbon_gap, abs(traced.carbon_balance_t))
        max_sulfur_gap = max(max_sulfur_gap, abs(traced.sulfur_balance_kg))
        max_re_gap = max(max_re_gap, abs(traced.renewable_balance_mwh))
        if max(max_power_gap, max_carbon_gap, max_sulfur_gap, max_re_gap) > 1e-6:
            raise AssertionError(f"第{hour}小时电力或属性守恒不通过")
        for zone in zones:
            values, attr = dispatch.zones[zone.name], traced.zones[zone.name]
            generation_by_type = defaultdict(float)
            for unit in generators:
                if unit.zone == zone.name:
                    generation_by_type[unit.technology] += dispatch.generation_mw[unit.name]
            incoming = sum(max(0.0, dispatch.flows_mw[link.name])
                           if link.target == zone.name else max(0.0, -dispatch.flows_mw[link.name])
                           for link in links if zone.name in (link.source, link.target))
            outgoing = sum(max(0.0, dispatch.flows_mw[link.name])
                           if link.source == zone.name else max(0.0, -dispatch.flows_mw[link.name])
                           for link in links if zone.name in (link.source, link.target))
            pumped_charge, pumped_discharge, battery_charge, battery_discharge = (
                storage_by_zone[zone.name])
            row_out = {"hour": hour, "zone": zone.name, "demand_mw": zone.demand_mw,
                       **{f"{technology}_mw": generation_by_type[technology]
                          for technology in TECHNOLOGIES},
                       "wind_mw": values["wind_mw"], "solar_mw": values["solar_mw"],
                       "pumped_charge_mw": pumped_charge,
                       "pumped_discharge_mw": pumped_discharge,
                       "battery_charge_mw": battery_charge,
                       "battery_discharge_mw": battery_discharge,
                       "imports_mw": incoming, "exports_mw": outgoing,
                       "wind_curtailment_mw": values["wind_curtailment_mw"],
                       "solar_curtailment_mw": values["solar_curtailment_mw"],
                       "unserved_mw": values["unserved_mw"], "spill_mw": values["spill_mw"],
                       "carbon_t_per_mwh": attr.carbon_t_per_mwh,
                       "sulfur_kg_per_mwh": attr.sulfur_kg_per_mwh,
                       "renewable_fraction": attr.renewable_fraction,
                       "consumed_carbon_t": attr.consumed_carbon_t,
                       "consumed_sulfur_kg": attr.consumed_sulfur_kg,
                       "consumed_renewable_mwh": attr.consumed_renewable_mwh,
                       "balance_residual_mw": values["balance_residual_mw"]}
            record = tuple(row_out[field] for field in HOURLY_OUTPUT)
            hourly_output.append(record)
            total = zone_totals[zone.name]
            # 逐时功率按1h积分；强度/份额和残差不求和。
            for field in ZONE_SUMMARY[1:]:
                total[field] += row_out[field]
        for link in links:
            flow = dispatch.flows_mw[link.name]
            line_totals[link.name]["absolute_mwh"] += abs(flow)
            line_totals[link.name]["signed_mwh"] += flow
            line_totals[link.name]["congested_hours"] += int(abs(flow) >= link.limit_mw - 1e-7)
        if progress and (hour + 1) % max(1, expected_hours // 20) == 0:
            progress(f"分区运行 {hour + 1}/{expected_hours} 小时")
    _write_csv(tables / "hourly_network.csv", HOURLY_OUTPUT, hourly_output)
    zone_summary = [(name, *[zone_totals[name][field] for field in ZONE_SUMMARY[1:]])
                    for name in names]
    _write_csv(tables / "zone_summary.csv", ZONE_SUMMARY, zone_summary)
    technology_summary = [(name, technology,
                           zone_totals[name][f"{technology}_mw"]) for name in names
                          for technology in (*TECHNOLOGIES, "wind", "solar",
                                             "pumped_discharge", "battery_discharge")]
    _write_csv(tables / "technology_summary.csv",
               ("zone", "technology", "generation_mwh"), technology_summary)
    link_summary = [(link.name, link.source, link.target, link.kind, link.limit_mw,
                     line_totals[link.name]["signed_mwh"],
                     line_totals[link.name]["absolute_mwh"],
                     line_totals[link.name]["congested_hours"])
                    for link in links]
    _write_csv(tables / "link_summary.csv", LINK_SUMMARY, link_summary)
    # 写入逐时表时使用流式工作簿：内存不随 8760×分区数×字段数线性累积。
    workbook = Workbook(write_only=True)
    for index, (title, headers, records) in enumerate((
            ("分区年度汇总", ZONE_SUMMARY, zone_summary),
            ("机组类型汇总", ("zone", "technology", "generation_mwh"),
             technology_summary),
            ("联络线汇总", LINK_SUMMARY, link_summary),
            ("分区逐时与属性", HOURLY_OUTPUT, hourly_output))):
        sheet = workbook.create_sheet(title)
        sheet.freeze_panes = "C2" if title == "分区逐时与属性" else "A2"
        sheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(records) + 1}"
        sheet.append(headers)
        for record in records:
            sheet.append(record)
    workbook.save(tables / "跨区运行和碳硫属性汇总.xlsx")
    audit = {"model": "electricity_sector_proportional_attributes",
             "solver": solver, "hours": expected_hours, "zones": len(names),
             "max_power_balance_residual_mw": max_power_gap,
             "max_carbon_balance_residual_t": max_carbon_gap,
             "max_sulfur_balance_residual_kg": max_sulfur_gap,
             "max_renewable_balance_residual_mwh": max_re_gap,
             "input_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest()
                              for name, path in files.items()},
             "limitations": ["固定储能计划及放电属性由输入提供，未优化或审核储能库存",
                             "交流为无损线性有功潮流，无电压无功和N-1",
                             "物理属性分摊不是绿证所有权或经济全产业链MRIO"]}
    (destination / "run_manifest.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


HOURLY_OUTPUT = ("hour", "zone", "demand_mw",
                 *(f"{technology}_mw" for technology in TECHNOLOGIES),
                 "wind_mw", "solar_mw", "pumped_charge_mw", "pumped_discharge_mw",
                 "battery_charge_mw", "battery_discharge_mw",
                 "imports_mw", "exports_mw", "wind_curtailment_mw",
                 "solar_curtailment_mw", "unserved_mw", "spill_mw",
                 "carbon_t_per_mwh", "sulfur_kg_per_mwh", "renewable_fraction",
                 "consumed_carbon_t", "consumed_sulfur_kg", "consumed_renewable_mwh",
                 "balance_residual_mw")
ZONE_SUMMARY = ("zone", "demand_mw",
                *(f"{technology}_mw" for technology in TECHNOLOGIES),
                "wind_mw", "solar_mw", "pumped_charge_mw", "pumped_discharge_mw",
                "battery_charge_mw", "battery_discharge_mw", "imports_mw", "exports_mw",
                "wind_curtailment_mw", "solar_curtailment_mw", "unserved_mw",
                "spill_mw", "consumed_carbon_t", "consumed_sulfur_kg",
                "consumed_renewable_mwh")
LINK_SUMMARY = ("name", "source", "target", "kind", "limit_mw",
                "signed_mwh", "absolute_mwh", "congested_hours")
