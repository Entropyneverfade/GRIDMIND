"""数据采集：从 JSON 和逐时 CSV 读取、校验输入。"""

import csv
import json
import math
from pathlib import Path
from typing import Tuple

from ..common.domain import GASettings, Hour, Plant, Problem, StorageSpec


def _plant(raw: dict, candidate: bool) -> Plant:
    """把外部字典变成只读电站对象，先核对功率、费用和储能效率边界。"""
    technology = str(raw["technology"])
    if technology not in {"thermal", "wind", "solar", "storage"}:
        raise ValueError(f"未知技术类型: {technology}")
    capacity = float(raw["capacity_mw"])
    firm = float(raw["firm_capacity_mw"])
    variable = float(raw["variable_cost_yuan_per_mwh"])
    fixed = float(raw.get("annual_fixed_cost_yuan", 0.0))
    if capacity <= 0 or not 0 <= firm <= capacity or variable < 0 or fixed < 0:
        raise ValueError(f"电站参数越界: {raw['name']}")
    if not candidate and fixed:
        # 规划目标只计候选项目新增年化固定成本，已有电站建设费是沉没成本。
        raise ValueError("已有电站的沉没建设成本不应计入新增规划目标")
    minimum = float(raw.get("min_output_mw", 0.0))
    if not 0 <= minimum <= capacity or (technology != "thermal" and minimum):
        raise ValueError("最小技术出力仅适用于火电，且应位于0与容量之间")
    storage = None
    if technology == "storage":
        data = raw["storage"]
        # 单个效率字段解释为往返效率；显式按平方根对称分解充、放电效率。
        if "roundtrip_efficiency" in data:
            if "eta_charge" in data or "eta_discharge" in data:
                raise ValueError("储能效率请仅选往返效率或分别给出充放效率")
            # 对称拆分：η_roundtrip=η_charge×η_discharge，因此各取平方根。
            eta_charge = eta_discharge = math.sqrt(float(data["roundtrip_efficiency"]))
        else:
            eta_charge, eta_discharge = float(data["eta_charge"]), float(data["eta_discharge"])
        storage = StorageSpec(float(data["charge_power_mw"]),
                              float(data["energy_capacity_mwh"]), eta_charge, eta_discharge,
                              float(data.get("initial_energy_mwh", 0)))
        if (storage.charge_power_mw <= 0 or storage.energy_capacity_mwh <= 0 or
                not 0 < eta_charge <= 1 or not 0 < eta_discharge <= 1 or
                not 0 <= storage.initial_energy_mwh <= storage.energy_capacity_mwh):
            raise ValueError(f"储能参数越界: {raw['name']}")
    elif "storage" in raw:
        raise ValueError("非储能电站不能填写storage参数")
    return Plant(str(raw["name"]), technology, capacity, firm, variable, fixed, minimum, storage)


def load_problem(config_path: Path, profile_path: Path) -> Tuple[Problem, GASettings]:
    """当前示例要求连续的 8760 个 1 小时点，避免把样本误当全年。"""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    existing = tuple(_plant(item, False) for item in config["existing_plants"])
    candidates = tuple(_plant(item, True) for item in config["candidate_plants"])
    names = [p.name for p in existing + candidates]
    if len(names) != len(set(names)) or not candidates:
        raise ValueError("电站名称必须唯一，且至少有一个候选项目")

    hours = []
    # 逐行检查0..8759索引及容量因子范围，杜绝缺小时或重复小时。
    with profile_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"hour", "load_mw", "wind_cf", "solar_cf"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"逐时 CSV 缺少列: {sorted(required)}")
        for expected_hour, row in enumerate(reader):
            if int(row["hour"]) != expected_hour:
                raise ValueError(f"小时序号应连续从 0 开始；第 {expected_hour} 行不符")
            hour = Hour(float(row["load_mw"]), float(row["wind_cf"]),
                        float(row["solar_cf"]))
            if hour.load_mw <= 0 or not 0 <= hour.wind_cf <= 1 or not 0 <= hour.solar_cf <= 1:
                raise ValueError(f"第 {expected_hour} 小时的数据越界")
            hours.append(hour)
    if len(hours) != 8760:
        raise ValueError(f"需要 8760 个逐时数据点，实际 {len(hours)} 个")

    reserve_margin = float(config["reserve_margin"])
    max_unserved = float(config["max_unserved_mwh"])
    if reserve_margin < 0 or max_unserved < 0:
        raise ValueError("备用率与允许缺供电量不能为负")
    priority = config.get("curtailment_priority", "solar_first")
    if priority not in {"solar_first", "wind_first", "proportional"}:
        raise ValueError("弃电序位必须为 solar_first、wind_first 或 proportional")
    reserve = float(config.get("operating_reserve_ratio", 0.03))
    horizon = int(config.get("storage_lookahead_hours", 48))
    reserve_limit = float(config.get("max_reserve_shortfall_mwh", 0))
    if reserve < 0 or horizon < 1 or reserve_limit < 0:
        raise ValueError("运行备用、储能前瞻时长和备用短缺上限越界")
    mode = config.get("dispatch_mode", "rules")
    terminal_value = float(config.get("terminal_storage_value_yuan_per_mwh", 300))
    if mode not in {"rules", "gurobi"} or terminal_value < 0:
        raise ValueError("调度模式或窗口末储能价值参数错误")
    ga = GASettings(**config["genetic_algorithm"])
    # 精英数小于种群规模，交叉/变异率属于[0,1]，保证代际更新可执行。
    if (ga.population_size < 2 or ga.max_generations < 1 or
            not 0 <= ga.min_generations <= ga.max_generations or
            ga.stall_generations < 1 or not 1 <= ga.elite_count < ga.population_size or
            not 0 <= ga.crossover_rate <= 1 or not 0 <= ga.mutation_rate <= 1):
        raise ValueError("遗传算法参数越界")
    return Problem(existing, candidates, tuple(hours), reserve_margin, max_unserved,
                   priority, reserve, horizon, reserve_limit, mode, terminal_value), ga
