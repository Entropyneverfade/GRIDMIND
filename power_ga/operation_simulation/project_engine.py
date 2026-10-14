"""真实项目全年运行：八类电源、跨日储能、水电月水量和联络线外送。"""

import math
from dataclasses import dataclass, replace
from typing import Tuple

import numpy as np

from ..common.domain import PLANNING_MONTH_HOURS
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
    commitment_hourly: tuple = ()
    operating_plants: tuple = ()


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


def _allocate_curtailment(wind_available_mw: float, solar_available_mw: float,
                          requested_mw: float) -> tuple[float, float]:
    """单区聚合调峰按当时可用出力比例分摊弃风、弃光，返回二者MW。"""
    # 先保证总弃电不超过两类资源的可用功率；Q=min(max(富余,0),Aw+As)。
    available = wind_available_mw + solar_available_mw
    total = min(max(0.0, requested_mw), available)
    if available <= 0.0:
        return 0.0, 0.0
    # 无网架/报价/调度优先级资料时用中性的可用份额规则：Qw=Q·Aw/(Aw+As)。
    # Qs=Q−Qw，故逐时弃电守恒且只要两类均可用、Q>0，两者均可能弃电。
    wind = min(wind_available_mw, total * wind_available_mw / available)
    solar = min(solar_available_mw, total - wind)
    return wind, solar


def _monthly_index():
    """按365日规划年给8760小时附所属月；闰年也不含2月29日。"""
    months = []
    for month, size in enumerate(PLANNING_MONTH_HOURS):
        months.extend([month] * size)
    if len(months) != 8760:
        raise ValueError("规划年月分段必须覆盖8760小时")
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


def _hydro_target(net_load, capacity_mw, monthly_budget):
    """水电月电量按净负荷高低分配：p_t=min(Pmax,λ·净负荷_t)。

    二分求λ使Σ_t p_t不超过月水量预算，是“削减月内净负荷起伏”的
    透明近似。月预算是发电上限；无正净负荷时允许弃水，不强制发电。
    本规则不声称代替逐库流量/水头/级联水力优化。
    """
    profile = []
    first = 0
    for month, size in enumerate(PLANNING_MONTH_HOURS):
        # 同一个月的二分要累计约60×700个小时；数组运算保持原公式而减少Python循环。
        weights = np.maximum(0.0, np.asarray(net_load[first:first + size], dtype=float))
        budget = min(monthly_budget[month], capacity_mw * size)
        if budget <= 0:
            profile.extend([0.0] * size)
        elif float(weights.max()) <= 0:
            # w_t=0 对所有小时成立时，p_t=min(Pmax,λw_t)=0；剩余水量未用。
            # 强制摊销预算会凭空制造发电与过剩，也违背月水量“上限”口径。
            profile.extend([0.0] * size)
        else:
            low, high = 0.0, max(1.0, capacity_mw / float(weights[weights > 0].min()))
            # f(λ)=Σ min(Pmax,λw_t) 单调，60次二分达双精度。
            for _ in range(60):
                middle = (low + high) / 2
                if float(np.minimum(capacity_mw, middle * weights).sum()) < budget:
                    low = middle
                else:
                    high = middle
            profile.extend(np.minimum(capacity_mw, high * weights).tolist())
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
            by_station[candidate.station_id] = (
                replace(old, capacity_mw=old.capacity_mw + candidate.capacity_mw,
                        unit_count=old.unit_count + candidate.unit_count,
                        startup_cost_yuan=old.startup_cost_yuan + candidate.startup_cost_yuan,
                        planned_maintenance_units=tuple(a + b for a, b in zip(
                            old.planned_maintenance_units, candidate.planned_maintenance_units)),
                        monthly_min_online_units=tuple(a + b for a, b in zip(
                            old.monthly_min_online_units, candidate.monthly_min_online_units)))
                if old else candidate)
    plants = tuple(by_station.values())
    wind_avail = _renewable_availability(plants, "wind")
    solar_avail = _renewable_availability(plants, "solar")
    dispatchable = tuple(sorted((p for p in plants if p.technology in {"coal", "gas", "hydro", "biomass"}),
                                key=lambda p: (p.variable_cost_yuan_per_mwh, p.station_id)))
    stores = [_Storage(p) for p in plants if p.technology in {"pumped", "battery"}]
    # 削峰放电按机组额定放电功率P额定由小到大；同容量用电站ID确定顺序。
    # 只调整放电先后，不重排stores本身，避免逐站库存/逐时表索引错位。
    discharge_order = sorted(range(len(stores)),
                             key=lambda i: (stores[i].plant.capacity_mw,
                                            stores[i].plant.station_id))
    month_of = _monthly_index()
    # 月可用水电量=月小时数×额定MW×设定年利用率×该月水文相对系数。
    # 0.42为可编辑运行参数，不是项目库提供的实测来水电量。
    hydro_budget = {}
    for p in dispatchable:
        if p.technology == "hydro":
            hydro_budget[p.station_id] = [p.capacity_mw * hours * hydro_annual_utilization
                                          * p.hydro_monthly_factor[m]
                                          for m, hours in enumerate(PLANNING_MONTH_HOURS)]
    load = [a + b for a, b in zip(case.domestic_load_mw, case.export_mw)]
    net = [max(0.0, l - w - s) for l, w, s in zip(load, wind_avail, solar_avail)]
    hydro_schedule = {p.station_id: _hydro_target(net, p.capacity_mw,
                                                   hydro_budget[p.station_id])
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
    commitment_rows = []
    peak_residual = 0.0
    shortage_hours = 0
    online = ()
    # 年初全部常规机组停机且已满足最短停机时间；状态在日/月边界连续。
    previous_power = {p.station_id: 0.0 for p in dispatchable}
    on_hours = {p.station_id: 0 for p in dispatchable}
    off_hours = {p.station_id: max(8760, p.min_down_hours) for p in dispatchable}
    starts_today = {p.station_id: 0 for p in dispatchable}
    last_online = set()
    startup_count = 0
    max_ramp_residual = 0.0
    for t in range(8760):
        month = month_of[t]
        if t % 24 == 0:
            starts_today = {p.station_id: 0 for p in dispatchable}
            # 日前开机需满足净负荷+按原始总负荷计的在线备用。
            # 水电只按本日逐时可用上限的最小值计容量；额定MW若无水量不能
            # 承担全天备用，否则会少开煤/气机组并产生虚假的缺供。
            day_end = min(t + 24, 8760)
            required = max(net[h] + reserve_ratio * load[h] for h in range(t, day_end))
            selected, capacity = [], 0.0
            # 最短运行时间、停机爬坡和月最低开机台数先占用日前开机名额。
            for plant in dispatchable:
                sid = plant.station_id
                active_units = plant.unit_count - plant.planned_maintenance_units[month]
                if plant.monthly_min_online_units[month] > active_units:
                    raise ValueError(f"电站{sid}月最小开机台数超过检修后可用台数")
                ramp = plant.capacity_mw * plant.ramp_fraction_per_hour
                forced = (sid in last_online and on_hours[sid] < plant.min_up_hours) or \
                    previous_power[sid] > ramp + 1e-9 or \
                    plant.monthly_min_online_units[month] > 0
                if forced:
                    selected.append(plant)
                    capacity += (min(hydro_schedule[sid][h] for h in range(t, day_end))
                                 if plant.technology == "hydro" else
                                 plant.capacity_mw * active_units / plant.unit_count *
                                 plant.monthly_max_fraction[month])
            for plant in dispatchable:
                if capacity >= required:
                    break
                if plant in selected:
                    continue
                # 刚停机的机组必须经过规定的最短停机时间才能重新启动。
                if plant.station_id not in last_online and off_hours[plant.station_id] < plant.min_down_hours:
                    continue
                if (plant.station_id not in last_online and
                        plant.capacity_mw * plant.min_fraction >
                        plant.capacity_mw * plant.ramp_fraction_per_hour + 1e-9):
                    continue  # 启动第一小时不能同时满足技术最小出力与启动爬坡。
                selected.append(plant)
                credit = (min(hydro_schedule[plant.station_id][h]
                              for h in range(t, day_end))
                          if plant.technology == "hydro" else
                          plant.capacity_mw *
                          (plant.unit_count - plant.planned_maintenance_units[month]) /
                          plant.unit_count * plant.monthly_max_fraction[month])
                capacity += credit
            online = tuple(selected)
            newly_online = {p.station_id for p in online} - last_online
            for p in online:
                if p.station_id in newly_online:
                    starts_today[p.station_id] += 1
                    startup_count += 1
                    if starts_today[p.station_id] > p.max_daily_starts:
                        raise ValueError(f"电站{p.station_id}超过日最大启动次数")
                    totals["variable_cost"] += p.startup_cost_yuan
            last_online = {p.station_id for p in online}
        # 水电小时上限来自月水量分配曲线，且不超过实际剩余月预算。
        max_output = {}
        min_output = {}
        for p in online:
            sid = p.station_id
            available_fraction = ((p.unit_count - p.planned_maintenance_units[month]) /
                                  p.unit_count)
            if p.technology == "hydro":
                budget = hydro_budget[sid][month]
                physical_max = min(p.capacity_mw * available_fraction, budget,
                                   hydro_schedule[sid][t])
            else:
                physical_max = p.capacity_mw * available_fraction * p.monthly_max_fraction[month]
            # 相邻小时出力上下限：Pprev−RD≤Pt≤Pprev+RU；月技术下限同时生效。
            ramp = p.capacity_mw * p.ramp_fraction_per_hour
            max_output[sid] = min(physical_max, previous_power[sid] + ramp)
            technical_min = p.capacity_mw * available_fraction * max(
                p.min_fraction, p.monthly_min_fraction[month])
            min_output[sid] = max(technical_min, previous_power[sid] - ramp)
            if min_output[sid] > max_output[sid] + 1e-7:
                raise ValueError(f"电站{sid}第{t}小时爬坡与月最大/最小出力约束相冲突")
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
        # 单区没有电网约束和报价时按可用份额分摊风光弃电；弃电独立列不混作发电。
        curtail = max(0.0, must_run + wind_avail[t] + solar_avail[t] - load[t] - charge)
        wind_curt, solar_curt = _allocate_curtailment(wind_avail[t], solar_avail[t], curtail)
        wind = wind_avail[t] - wind_curt
        solar = solar_avail[t] - solar_curt
        residual = load[t] + charge - wind - solar
        end = min(8760, t + 24)
        threshold = (prefix[end] - prefix[t]) / (end - t)
        online_capacity = sum(max_output.values())
        discharge_request = min(max(0.0, residual - threshold, residual - online_capacity),
                                max(0.0, residual - must_run))
        if charge < 1e-9:
            for i in discharge_order:
                state = stores[i]
                # 逐站Pdis=min(剩余削峰需求,P额定,Et·ηdis)；小功率站先占用需求。
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
        # 逐站更新状态并核验停机小时从Pprev降至0同样受下降爬坡限制。
        for p in dispatchable:
            sid = p.station_id
            power = generation.get(sid, 0.0)
            ramp = p.capacity_mw * p.ramp_fraction_per_hour
            max_ramp_residual = max(max_ramp_residual,
                                    max(0.0, abs(power - previous_power[sid]) - ramp))
            if sid in last_online:
                on_hours[sid] += 1
                off_hours[sid] = 0
            else:
                off_hours[sid] += 1
                on_hours[sid] = 0
            if keep_hourly:
                commitment_rows.append((t, sid, p.technology, int(sid in last_online),
                                        previous_power[sid], power, ramp,
                                        p.capacity_mw * p.monthly_max_fraction[month],
                                        p.capacity_mw * max(p.min_fraction,
                                                            p.monthly_min_fraction[month]),
                                        on_hours[sid], off_hours[sid]))
            previous_power[sid] = power
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
        # 备用不得超过一小时内可爬升的出力余量。
        reserve_avail = sum(min(max_output[p.station_id] - generation[p.station_id],
                                p.capacity_mw * p.ramp_fraction_per_hour) for p in online)
        # 备用只计当时未使用的放电功率且须能持续1小时：
        # R_s=min(Pmax−Pdis, E_end×ηdis/1h)；正在充电的站不重复承担备用。
        # 否则同一MW会同时记为充电、放电备用，导致规划虚假可行。
        reserve_avail += sum(
            min(max(0.0, state.plant.capacity_mw - storage_discharges[i]),
                state.energy_mwh * state.eta)
            for i, state in enumerate(stores) if storage_charges[i] < 1e-9)
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
    totals["startup_count"] = startup_count
    totals["max_ramp_violation_mw"] = max_ramp_residual
    return ProjectSimulation(tuple(rows), totals, station_mwh, tuple(storage_rows),
                             tuple(commitment_rows), plants)
