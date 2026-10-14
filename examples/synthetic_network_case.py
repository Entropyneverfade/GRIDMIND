"""公开连接方向启发的四区合成8760小时潮流试验；所有数值均为虚构。"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

from power_ga.operation_simulation.network import (
    Generator, Link, Zone, solve_network_timeseries)


# 公开资料仅证实山西向华北、华中、江苏有外送互联，且晋北—南京直流存在。
# 下列“区域”是聚合节点而非真实母线；限额、电纳、需求与机组参数均为教学假设。
SOURCES = (
    "https://zfxxgk.nea.gov.cn/2024-06/11/c_1212388601.htm",
    "https://jsb.nea.gov.cn/dtyw/jgdt/202309/t20230910_28887.html",
)
LINKS = (
    Link("晋华北_示意交流", "山西", "华北", 22.0, "ac", 120.0),
    Link("晋华中_示意交流", "山西", "华中", 16.0, "ac", 100.0),
    Link("晋苏_示意直流", "山西", "江苏", 12.0, "dc"),
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
        shanxi_load = 72 + 7 * daily + 6 * season + rng.uniform(-4, 4)
        north_load = 43 + 5 * daily + rng.uniform(-3, 3)
        central_load = 31 + 4 * daily + rng.uniform(-3, 3)
        jiangsu_load = 27 + 3 * daily + rng.uniform(-2, 2)
        hourly_zones.append((Zone("山西", shanxi_load, wind, solar),
                             Zone("华北", north_load), Zone("华中", central_load),
                             Zone("江苏", jiangsu_load)))
        hourly_generators.append((
            Generator("晋煤_合成", "山西", 30, 90, 240),
            Generator("华北气_合成", "华北", 0, 55, 460),
            Generator("华中水_合成", "华中", 0, 37, 55),
            Generator("江苏气_合成", "江苏", 0, 33, 470),
        ))
    return hourly_zones, hourly_generators


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
    print(json.dumps(run(parser.parse_args().output), ensure_ascii=False, indent=2))
