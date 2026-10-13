"""可复现的八类机组合成8760小时演示；不读取外部项目数据库。"""

import argparse
import csv
import json
import math
import random
from dataclasses import asdict
from pathlib import Path

from power_ga.data_collection.project_case import CasePlant, ProjectCase, read_costs
from power_ga.operation_simulation.project_engine import simulate_project


COST_FILE = Path(__file__).with_name("synthetic_case_costs.csv")


def build_case(with_candidates=False):
    """构造纯合成八类电站；可选八个候选增量供完整遗传规划。"""
    costs = read_costs(COST_FILE)

    def variable(kind):
        """所有技术的变动费用直接取随算例公开的合成成本表。"""
        return float(costs[kind]["variable_yuan_per_mwh"])

    def annual(kind, mw):
        """候选年化固定费用=单位年费×新增MW，单位是元/年。"""
        return float(costs[kind]["annual_capital_yuan_per_mw"]) * mw

    load, wind, solar = [], [], []
    rng = random.Random(20261014)  # 固定种子使“随机一点”的负荷仍可逐位复现。
    day_jitter = [rng.uniform(-3.5, 3.5) for _ in range(365)]
    wind_rng = random.Random(20261015)
    solar_rng = random.Random(20261016)
    # 相邻日风况有相关性；光伏云量逐日变化，均为独立生成的合成天气。
    wind_state, day_wind = 0.0, []
    for _ in range(365):
        wind_state = max(-0.22, min(0.22, 0.78 * wind_state + wind_rng.gauss(0, 0.075)))
        day_wind.append(wind_state)
    day_cloud = [solar_rng.uniform(0.72, 1.0) for _ in range(365)]
    for t in range(8760):
        hour, day = t % 24, t // 24
        season = 0.5 + 0.5 * math.sin(2 * math.pi * (day - 90) / 365)
        evening = max(0.0, 1 - abs(hour - 20) / 5)
        # 小时负荷在夏季及晚高峰上升；这些数值是人工设计，不代表实测系统。
        # 周末略低，另叠加日级和小时级扰动；所有负荷仍为正且不使用外部数据。
        weekend = -2.5 if day % 7 in (5, 6) else 0.0
        load.append(78 + 12 * season + 23 * evening + 3 * math.sin(2 * math.pi * hour / 24)
                    + weekend + day_jitter[day] + rng.uniform(-2.2, 2.2))
        wind.append(max(0.05, min(0.90, 0.47 + day_wind[day]
                                            + 0.06 * math.cos(2 * math.pi * hour / 24)
                                            + wind_rng.gauss(0, 0.035))))
        daylight = max(0.0, math.sin(math.pi * (hour - 6) / 12))
        solar.append(min(1.0, daylight * day_cloud[day] *
                         max(0.55, 1 + solar_rng.gauss(0, 0.055))))
    plants = (
        CasePlant(1, "Synthetic coal", "coal", 55, 0.78, variable("coal"), 0),
        CasePlant(2, "Synthetic gas", "gas", 40, 0.05, variable("gas"), 0),
        CasePlant(3, "Synthetic hydro", "hydro", 18, 0, variable("hydro"), 0),
        CasePlant(4, "Synthetic biomass", "biomass", 10, 0.40, variable("biomass"), 0),
        CasePlant(5, "Synthetic pumped", "pumped", 12, 0, variable("pumped"), 0,
                  (), 4, 1, 0.81),
        CasePlant(6, "Synthetic battery", "battery", 10, 0, variable("battery"), 0,
                  (), 2, 1, 0.85),
        CasePlant(7, "Synthetic wind", "wind", 28, 0, variable("wind"), 0, tuple(wind)),
        CasePlant(8, "Synthetic PV", "solar", 55, 0, variable("solar"), 0, tuple(solar)),
    )
    # 八个候选建设位体现技术选择与运行费用权衡；电量曲线继续全由固定种子合成。
    candidates = (
        CasePlant(101, "Candidate coal", "coal", 20, 0.55,
                  variable("coal"), annual("coal", 20)),
        CasePlant(102, "Candidate gas", "gas", 15, 0.05,
                  variable("gas"), annual("gas", 15)),
        CasePlant(103, "Candidate hydro", "hydro", 10, 0,
                  variable("hydro"), annual("hydro", 10)),
        CasePlant(104, "Candidate biomass", "biomass", 8, 0.25,
                  variable("biomass"), annual("biomass", 8)),
        CasePlant(105, "Candidate pumped", "pumped", 10, 0,
                  variable("pumped"), annual("pumped", 10), (), 4, 1, 0.81),
        CasePlant(106, "Candidate battery", "battery", 10, 0,
                  variable("battery"), annual("battery", 10), (), 2, 1, 0.85),
        CasePlant(107, "Candidate wind", "wind", 20, 0,
                  variable("wind"), annual("wind", 20), tuple(wind)),
        CasePlant(108, "Candidate PV", "solar", 20, 0,
                  variable("solar"), annual("solar", 20), tuple(solar)),
    ) if with_candidates else ()
    # 外送设零，仅用于演示八类技术的单区域运行；源路径字段不含外部信息。
    return ProjectCase(2025, 2026 if with_candidates else 2025, plants, candidates,
                       tuple(load), (0.0,) * 8760, 0.10, 0.0, (), "synthetic",
                       str(COST_FILE))


def write_synthetic_result(destination: Path):
    """将真实运行引擎生成的逐时输出写成EXE查看窗口可读的合成存档。"""
    case = build_case()
    simulation = simulate_project(case, (), keep_hourly=True)
    tables = destination / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    rows = [asdict(row) for row in simulation.hourly]
    with (tables / "hourly_dispatch.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # 公开演示的简短摘要只含合成标志与数值守恒；没有外部项目元数据。
    (destination / "synthetic_manifest.json").write_text(
        json.dumps({"synthetic": True, "hours": len(rows), "technologies": 8,
                    "max_balance_residual_mw": simulation.summary["max_balance_residual_mw"]},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return simulation


def main():
    """用公开脚本复现演示表；EXE再按同一表导出预定尺度的PNG。"""
    parser = argparse.ArgumentParser(description="生成八类机组合成8760小时演示数据")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    simulation = write_synthetic_result(args.output)
    print("synthetic hours:", len(simulation.hourly))
    print("synthetic max balance residual MW:", simulation.summary["max_balance_residual_mw"])


if __name__ == "__main__":
    main()
