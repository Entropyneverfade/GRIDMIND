"""四分区合成8760小时潮流试验；所有数值均为虚构。"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

from power_ga.operation_simulation.network import (
    Generator, Link, Zone, solve_network_timeseries)
from power_ga.operation_simulation.network_case import run_network_case


# 分区与联络仅定义合成教学算例；不映射真实地理拓扑。
SOURCES = ()
LINKS = (
    Link("通道_AB", "分区A", "分区B", 22.0, "ac", 120.0),
    Link("通道_AC", "分区A", "分区C", 16.0, "ac", 100.0),
    Link("通道_AD", "分区A", "分区D", 12.0, "dc"),
)


def build_hours():
    """固定种子生成不规则负荷、风速代理与日照；绝不读取实际项目曲线。"""
    rng = random.Random(20261014)
    hourly_zones, hourly_generators = [], []
    for hour in range(8760):
        day, hod = divmod(hour, 24)
        season = math.sin(2 * math.pi * day / 365)
        daily = math.sin(2 * math.pi * (hod - 7) / 24)
        solar_cf = max(0.0, math.sin(math.pi * (hod - 6) / 12))
        # 负荷、风、光分别叠加有界随机扰动，避免机械重复的日形状。
        wind = 60 * max(0.02, min(0.95, 0.45 + 0.25 * season + rng.uniform(-0.25, 0.25)))
        solar = 68 * solar_cf * (0.55 + 0.45 * rng.random())
        zone_a_load = 72 + 7 * daily + 6 * season + rng.uniform(-4, 4)
        zone_b_load = 43 + 5 * daily + rng.uniform(-3, 3)
        zone_c_load = 31 + 4 * daily + rng.uniform(-3, 3)
        zone_d_load = 27 + 3 * daily + rng.uniform(-2, 2)
        hourly_zones.append((Zone("分区A", zone_a_load, wind, solar),
                             Zone("分区B", zone_b_load), Zone("分区C", zone_c_load),
                             Zone("分区D", zone_d_load)))
        hourly_generators.append((
            Generator("机组A_煤电", "分区A", 30, 90, 240),
            Generator("机组B_燃气", "分区B", 0, 55, 460),
            Generator("机组C_水电", "分区C", 0, 37, 55),
            Generator("机组D_燃气", "分区D", 0, 33, 470),
        ))
    return hourly_zones, hourly_generators


def write_case_input(destination: Path):
    """生成可由正式EXE读取的四个CSV；数值和排放因子均为教学假设。"""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    zones, generator_hours = build_hours()
    with (destination / "zones.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("zone",))
        writer.writerows((zone.name,) for zone in zones[0])
    # tCO₂/MWh与kgSO₂/MWh只用于演示守恒，不作为任何地区实测排放因子。
    factors = {"机组A_煤电": ("coal", 0.82, 0.30, 0),
               "机组B_燃气": ("gas", 0.39, 0.03, 0),
               "机组C_水电": ("hydro", 0, 0, 1),
               "机组D_燃气": ("gas", 0.39, 0.03, 0),
               "机组A_生物质": ("biomass", 0.08, 0.05, 1)}
    units = (*generator_hours[0], Generator("机组A_生物质", "分区A", 0, 5, 180))
    with (destination / "generators.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("name", "zone", "technology", "minimum_mw", "maximum_mw",
                         "cost_yuan_per_mwh", "carbon_t_per_mwh",
                         "sulfur_kg_per_mwh", "renewable_fraction"))
        writer.writerows((unit.name, unit.zone, factors[unit.name][0],
                          unit.minimum_mw, unit.maximum_mw,
                          unit.cost_yuan_per_mwh, *factors[unit.name][1:])
                         for unit in units)
    with (destination / "links.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("name", "source", "target", "limit_mw", "kind",
                         "susceptance_mw_per_rad"))
        writer.writerows((link.name, link.source, link.target, link.limit_mw,
                          link.kind, link.susceptance_mw_per_rad or "") for link in LINKS)
    with (destination / "hourly.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("hour", "zone", "demand_mw", "wind_available_mw",
                         "solar_available_mw", "pumped_charge_mw", "pumped_discharge_mw",
                         "battery_charge_mw", "battery_discharge_mw",
                         "pumped_carbon_t_per_mwh", "pumped_sulfur_kg_per_mwh",
                         "pumped_renewable_fraction", "battery_carbon_t_per_mwh",
                         "battery_sulfur_kg_per_mwh", "battery_renewable_fraction"))
        for hour, hourly in enumerate(zones):
            hod = hour % 24
            for zone in hourly:
                # 每日先充4小时、傍晚放4小时；8MWh充电→6.4MWh放电相当于80%往返效率。
                battery_charge = 2.0 if zone.name == "分区A" and hod < 4 else 0.0
                battery_discharge = 1.6 if zone.name == "分区A" and 18 <= hod < 22 else 0.0
                pumped_charge = 3.0 if zone.name == "分区B" and hod < 4 else 0.0
                pumped_discharge = 2.4 if zone.name == "分区B" and 18 <= hod < 22 else 0.0
                writer.writerow((hour, zone.name, zone.demand_mw,
                                 zone.wind_available_mw, zone.solar_available_mw,
                                 pumped_charge, pumped_discharge,
                                 battery_charge, battery_discharge,
                                 *((0.40, 0.10, 0.35) if pumped_discharge else ("", "", "")),
                                 *((0.35, 0.08, 0.45) if battery_discharge else ("", "", ""))))
    (destination / "INPUT_NOTE.md").write_text(
        "# 公开合成分区输入\n\n分区与联络为合成算例定义；节点、需求、装机、线路限额、"
        "电纳、成本与排放因子均由固定种子或人工教学假设生成。抽蓄/电池的固定日计划"
        "按80%往返效率形成每日能量闭环，放电属性是额外明示的教学假设。\n\n"
        "交流边请选择Gurobi LP；启发式模式必须把所有边显式设为可控通道，"
        "不能把交流线路直接改名为直流。\n", encoding="utf-8")
    return destination


def run_csv_case(destination: Path):
    """在同一固定种子输入上运行完整8760小时分区潮流和属性追踪。"""
    destination = Path(destination)
    input_dir = write_case_input(destination / "input")
    return run_network_case(input_dir, destination / "result", solver="gurobi")


def run(destination: Path):
    """8760次分区LP，输出逐时功率、年度汇总与可核查的假设清单。"""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    zones, generators = build_hours()
    solution = solve_network_timeseries(zones, generators, LINKS)
    if solution.max_balance_residual_mw > 1e-7:
        raise AssertionError("合成网架逐区功率不守恒")
    with (destination / "hourly_network.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("小时", "区域", "需求MW", "风电MW", "光伏MW", "弃风MW", "弃光MW",
                         "缺供MW", "溢出MW", "区域残差MW", *[f"{link.name}MW" for link in LINKS]))
        for hour, (inputs, result) in enumerate(zip(zones, solution.hourly)):
            for zone in inputs:
                values = result.zones[zone.name]
                writer.writerow((hour, zone.name, zone.demand_mw, values["wind_mw"],
                                 values["solar_mw"], values["wind_curtailment_mw"],
                                 values["solar_curtailment_mw"], values["unserved_mw"],
                                 values["spill_mw"], values["balance_residual_mw"],
                                 *(result.flows_mw[link.name] for link in LINKS)))
    summary = {"synthetic": True, "hours": len(solution.hourly),
               "max_balance_residual_mw": solution.max_balance_residual_mw,
               "unserved_mwh": solution.total_unserved_mwh,
               "wind_curtailment_mwh": solution.total_wind_curtailment_mwh,
               "solar_curtailment_mwh": solution.total_solar_curtailment_mwh,
               "links": [{"name": link.name, "kind": link.kind,
                          "assumed_limit_mw": link.limit_mw,
                          "assumed_susceptance_mw_per_rad": link.susceptance_mw_per_rad}
                         for link in LINKS],
               "public_connectivity_sources": SOURCES,
               "warning": "只有连接方向来自公开资料；所有数值与区域聚合均为合成假设，不能代表真实线路潮流"}
    (destination / "audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--csv-platform-case", action="store_true",
                        help="生成EXE可读输入，并运行碳硫属性追踪")
    args = parser.parse_args()
    result = run_csv_case(args.output) if args.csv_platform_case else run(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
