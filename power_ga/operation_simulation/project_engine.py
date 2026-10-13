"""真实项目全年运行：八类电源、跨日储能、水电月水量和联络线外送。"""

import math
from calendar import monthrange
from dataclasses import dataclass, replace
from typing import Tuple

from ..data_collection.project_case import CasePlant, ProjectCase


@dataclass(frozen=True)
class ProjectHour:
    """功率为MW，1小时积分即MWh；储能库存为内部MWh。"""
    hour: int
    domestic_load_mw: float
    export_mw: float
    load_mw: float
    coal_mw: float
    gas_mw: float
    hydro_mw: float
    biomass_mw: float
    wind_available_mw: float
    solar_available_mw: float
    wind_mw: float
    solar_mw: float
    wind_curtailment_mw: float
    solar_curtailment_mw: float
    pumped_charge_mw: float
    pumped_discharge_mw: float
    battery_charge_mw: float
    battery_discharge_mw: float
    storage_charge_mw: float
    storage_discharge_mw: float
    storage_energy_end_mwh: float
    thermal_mw: float
    unserved_mw: float
    reserve_requirement_mw: float
    reserve_available_mw: float
    reserve_shortfall_mw: float
    overgeneration_mw: float
    balance_residual_mw: float


@dataclass(frozen=True)
class ProjectSimulation:
    """整年结果，summary中的电量均为逐小时功率×1h的积分。"""
    hourly: Tuple[ProjectHour, ...]
    summary: dict
    station_generation_mwh: dict
    storage_hourly: tuple = ()


class _Storage:
    """同一储能站在全年连续更新，不在日/月窗口重置。"""

    def __init__(self, plant: CasePlant):
        self.plant = plant
        self.capacity_mwh = plant.capacity_mw * plant.storage_hours
        self.energy_mwh = 0.0  # 年初零库存，禁止初始库存免费供电。
        # 单字段效率解释为往返效率，ηch×ηdis=ηroundtrip。
        self.eta = math.sqrt(plant.roundtrip_efficiency)

    def charge(self, request_mw):
        """Pch≤min(富余,充电额定MW,(Emax−Et)/ηch)，Δt=1h。"""
        power = min(max(0.0, request_mw), self.plant.capacity_mw * self.plant.charge_ratio,
                    max(0.0, self.capacity_mwh - self.energy_mwh) / self.eta)
        self.energy_mwh += power * self.eta
        return power

    def discharge(self, request_mw):
        """Pdis≤min(放电额定MW,Et×ηdis)，Et+1=Et−Pdis/ηdis。"""
        power = min(max(0.0, request_mw), self.plant.capacity_mw, self.energy_mwh * self.eta)
        self.energy_mwh -= power / self.eta
        return power


def _monthly_index(year):
    """给每小时附所属月；水电月水量不能跨月借用。"""
    months = []
    for month in range(1, 13):
        size = monthrange(year, month)[1] * 24
        months.extend([month - 1] * size)
    if len(months) != 8760:
        raise ValueError("当前引擎只接受非闰年8760小时")
    return months


def _renewable_availability(plants, kind):
    """逐站使用不同风/光曲线：A_t=Σ_j P_j×cf_j,t。"""
    series = [0.0] * 8760
    for plant in plants:
        if plant.technology == kind:
            if len(plant.profile) != 8760:
                raise ValueError(f"电站缺少8760小时出力曲线：{plant.name}")
            series = [a + plant.capacity_mw * cf for a, cf in zip(series, plant.profile)]
    return series


def _hydro_target(net_load, capacity_mw, monthly_budget, year):
    """水电月电量按净负荷高低分配：p_t=min(Pmax,λ·净负荷_t)。

    二分求λ使Σ_t p_t=min(月水量预算,Pmax×月小时数)，是“削减月内净负荷
    起伏”的透明近似；不声称代替逐库流量/水头/级联水力优化。
    """
    profile = []
    first = 0
    for month in range(1, 13):
        size = monthrange(year, month)[1] * 24
        weights = [max(0.0, v) for v in net_load[first:first + size]]
        budget = min(monthly_budget[month - 1], capacity_mw * size)
        if budget <= 0:
            profile.extend([0.0] * size)
        elif max(weights) <= 0:
            profile.extend([budget / size] * size)
        else:
            low, high = 0.0, max(1.0, capacity_mw / min(v for v in weights if v > 0))
            # f(λ)=Σ min(Pmax,λw_t) 单调，60次二分达双精度。
            for _ in range(60):
                middle = (low + high) / 2
                if sum(min(capacity_mw, middle * w) for w in weights) < budget:
                    low = middle
                else:
                    high = middle
            profile.extend(min(capacity_mw, high * w) for w in weights)
        first += size
    return tuple(profile)


def simulate_project(case: ProjectCase, chromosome, keep_hourly=False,
                     hydro_annual_utilization=0.42, reserve_ratio=0.03):
    """单个规划方案8760h顺序模拟；报价与月水量规则是可审计近似。"""
    if len(chromosome) != len(case.candidates) or any(bit not in (0, 1) for bit in chromosome):
        raise ValueError("规划染色体与候选电站不匹配")
    if not 0 < hydro_annual_utilization <= 1 or reserve_ratio < 0:
        raise ValueError("水电利用率或在线备用参数越界")
    # 同站基年存量与新增容量合为一个运行对象，避免同一电站ID在出力字典中覆盖。
    by_station = {p.station_id: p for p in case.existing}
    for bit, candidate in zip(chromosome, case.candidates):
        if bit:
            old = by_station.get(candidate.station_id)
            by_station[candidate.station_id] = (replace(old, capacity_mw=old.capacity_mw + candidate.capacity_mw)
                                                if old else candidate)
    plants = tuple(by_station.values())
    wind_avail = _renewable_availability(plants, "wind")
    solar_avail = _renewable_availability(plants, "solar")
    dispatchable = tuple(sorted((p for p in plants if p.technology in {"coal", "gas", "hydro", "biomass"}),
                                key=lambda p: (p.variable_cost_yuan_per_mwh, p.station_id)))
    stores = [_Storage(p) for p in plants if p.technology in {"pumped", "battery"}]
    month_of = _monthly_index(case.target_year)
    # 月可用水电量=月小时数×额定MW×设定年利用率×该月水文相对系数。
    # 0.42为可编辑运行参数，不是项目库提供的实测来水电量。
    hydro_budget = {}
    for p in dispatchable:
        if p.technology == "hydro":
            hydro_budget[p.station_id] = [p.capacity_mw * monthrange(case.target_year, m + 1)[1] * 24
                                          * hydro_annual_utilization * p.hydro_monthly_factor[m]
                                          for m in range(12)]
    load = [a + b for a, b in zip(case.domestic_load_mw, case.export_mw)]
    net = [max(0.0, l - w - s) for l, w, s in zip(load, wind_avail, solar_avail)]
    hydro_schedule = {p.station_id: _hydro_target(net, p.capacity_mw,
                                                   hydro_budget[p.station_id], case.target_year)
                      for p in dispatchable if p.technology == "hydro"}
    prefix = [0.0]
    for value in net:
        prefix.append(prefix[-1] + value)
    totals = {key: 0.0 for key in ("load", "domestic_load", "export", "coal", "gas", "hydro",
                                  "biomass", "wind", "solar", "wind_available", "solar_available",
                                  "wind_curtailment", "solar_curtailment", "pumped_charge",
                                  "pumped_discharge", "battery_charge", "battery_discharge",
                                  "unserved", "reserve_shortfall", "overgeneration", "variable_cost")}
    station_mwh = {p.name: 0.0 for p in plants}
    rows = []
    storage_rows = []
    peak_residual = 0.0
    shortage_hours = 0
    online = ()
    for t in range(8760):
        month = month_of[t]
        if t % 24 == 0:
            # 日前开机：以次日最大净负荷+在线备用为容量需求，按变动成本排序。
            required = max(net[t:min(t + 24, 8760)]) * (1 + reserve_ratio)
            selected, capacity = [], 0.0
            for plant in dispatchable:
                if capacity >= required:
                    break
                selected.append(plant)
                capacity += plant.capacity_mw
            online = tuple(selected)
        # 水电小时上限来自月水量分配曲线，且不超过实际剩余月预算。
        max_output = {}
        for p in online:
            if p.technology == "hydro":
                budget = hydro_budget[p.station_id][month]
                max_output[p.station_id] = min(p.capacity_mw, budget,
                                               hydro_schedule[p.station_id][t])
            else:
                max_output[p.station_id] = p.capacity_mw
        min_output = {p.station_id: min(max_output[p.station_id], p.capacity_mw * p.min_fraction)
                      for p in online}
        must_run = sum(min_output.values())
        # 储能先吸纳“新能源+开机最小出力”带来的富余，再根据未来24h净负荷放电。
        surplus = max(0.0, must_run + wind_avail[t] + solar_avail[t] - load[t])
        charge_by_kind = {"pumped": 0.0, "battery": 0.0}
        discharge_by_kind = {"pumped": 0.0, "battery": 0.0}
        storage_starts = [state.energy_mwh for state in stores]
        storage_charges = [0.0] * len(stores)
        storage_discharges = [0.0] * len(stores)
        for i, state in enumerate(stores):
            power = state.charge(surplus)
            surplus -= power
            charge_by_kind[state.plant.technology] += power
            storage_charges[i] = power
        charge = sum(charge_by_kind.values())
        # 当前实现采用“先弃光、后弃风”；弃电保留在独立列，不混作发电。
        curtail = max(0.0, must_run + wind_avail[t] + solar_avail[t] - load[t] - charge)
        solar_curt = min(solar_avail[t], curtail)
        wind_curt = min(wind_avail[t], curtail - solar_curt)
        wind = wind_avail[t] - wind_curt
        solar = solar_avail[t] - solar_curt
        residual = load[t] + charge - wind - solar
        end = min(8760, t + 24)
        threshold = (prefix[end] - prefix[t]) / (end - t)
        online_capacity = sum(max_output.values())
        discharge_request = min(max(0.0, residual - threshold, residual - online_capacity),
                                max(0.0, residual - must_run))
        if charge < 1e-9:
            for i, state in enumerate(stores):
                power = state.discharge(discharge_request)
                discharge_request -= power
                discharge_by_kind[state.plant.technology] += power
                storage_discharges[i] = power
        discharge = sum(discharge_by_kind.values())
        remaining = max(0.0, residual - discharge - must_run)
        generation = dict(min_output)
        for p in online:
            addition = min(remaining, max_output[p.station_id] - generation[p.station_id])
            generation[p.station_id] += addition
            remaining -= addition
        unserved = remaining
        if unserved > 1e-6:
            shortage_hours += 1
        by_kind = {kind: 0.0 for kind in ("coal", "gas", "hydro", "biomass")}
        for p in online:
            power = generation[p.station_id]
            by_kind[p.technology] += power
            station_mwh[p.name] += power
            totals["variable_cost"] += power * p.variable_cost_yuan_per_mwh
            if p.technology == "hydro":
                hydro_budget[p.station_id][month] = max(0.0, hydro_budget[p.station_id][month] - power)
        totals["variable_cost"] += sum(state.plant.variable_cost_yuan_per_mwh * power
                                       for state, power in zip(stores, storage_discharges))
        if keep_hourly:
            for i, state in enumerate(stores):
                # 状态守恒残差=Et+1−Et−ηchPch+Pdis/ηdis；应接近数值零。
                residual = (state.energy_mwh - storage_starts[i] -
                            state.eta * storage_charges[i] + storage_discharges[i] / state.eta)
                storage_rows.append((t, state.plant.name, state.plant.technology,
                                     storage_charges[i], storage_discharges[i],
                                     storage_starts[i], state.energy_mwh,
                                     state.energy_mwh / state.capacity_mwh, residual))
        # 风光费用按实际消纳电量×技术对应单位费用；各站曲线用于可用功率。
        for kind, actual, available in (("wind", wind, wind_avail[t]), ("solar", solar, solar_avail[t])):
            grouped = [p for p in plants if p.technology == kind]
            if available > 0:
                for p in grouped:
                    share = p.capacity_mw * p.profile[t] / available
                    station_mwh[p.name] += actual * share
                    totals["variable_cost"] += actual * share * p.variable_cost_yuan_per_mwh
        reserve_need = load[t] * reserve_ratio
        reserve_avail = sum(max_output[p.station_id] - generation[p.station_id] for p in online)
        reserve_avail += sum(min(s.plant.capacity_mw, s.energy_mwh * s.eta) for s in stores)
        reserve_gap = max(0.0, reserve_need - reserve_avail)
        supply = sum(by_kind.values()) + wind + solar + discharge + unserved
        over = max(0.0, supply - load[t] - charge)
        balance = supply - load[t] - charge - over
        peak_residual = max(peak_residual, abs(balance))
        values = {"load": load[t], "domestic_load": case.domestic_load_mw[t],
                  "export": case.export_mw[t], **by_kind, "wind": wind, "solar": solar,
                  "wind_available": wind_avail[t], "solar_available": solar_avail[t],
                  "wind_curtailment": wind_curt, "solar_curtailment": solar_curt,
                  "pumped_charge": charge_by_kind["pumped"],
                  "pumped_discharge": discharge_by_kind["pumped"],
                  "battery_charge": charge_by_kind["battery"],
                  "battery_discharge": discharge_by_kind["battery"],
                  "unserved": unserved, "reserve_shortfall": reserve_gap,
                  "overgeneration": over}
        for key, value in values.items():
            totals[key] += value
        if keep_hourly:
            rows.append(ProjectHour(t, case.domestic_load_mw[t], case.export_mw[t], load[t],
                                    by_kind["coal"], by_kind["gas"], by_kind["hydro"],
                                    by_kind["biomass"], wind_avail[t], solar_avail[t], wind, solar,
                                    wind_curt, solar_curt, charge_by_kind["pumped"],
                                    discharge_by_kind["pumped"], charge_by_kind["battery"],
                                    discharge_by_kind["battery"], charge, discharge,
                                    sum(s.energy_mwh for s in stores),
                                    by_kind["coal"] + by_kind["gas"] + by_kind["biomass"],
                                    unserved, reserve_need, reserve_avail, reserve_gap, over, balance))
    totals["shortage_hours"] = shortage_hours
    totals["max_balance_residual_mw"] = peak_residual
    totals["storage_final_mwh"] = sum(s.energy_mwh for s in stores)
    totals["hydro_unused_budget_mwh"] = sum(sum(x) for x in hydro_budget.values())
    return ProjectSimulation(tuple(rows), totals, station_mwh, tuple(storage_rows))
