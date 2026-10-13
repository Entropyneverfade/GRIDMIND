"""规则运行引擎：每日开机、逐小时源荷储协调、全年状态连续。

说明书明确的成本序位、弃电序位、8760h库容约束作为基础；每日开机
需求和储能前瞻阈值是本程序自行设定的透明基线。
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from ..common.domain import Plant, Problem


def commit_for_day(day_hours, ordered_plants, wind_capacity, solar_capacity, reserve_ratio):
    """按成本序位开机，容量覆盖每日最大净负荷与在线备用要求。

    为避免把储能额定功率直接当成全天可靠容量，本基线不开机时扣除
    储能功率；储能在小时层降低火电出力并改善新能源消纳。此规则是
    本程序的保守实现，所参考说明书没有公开全部开机计算细节。
    """
    # P_required=max_t{max(0,L_t−W_t−S_t)+r_op×L_t}，按成本序位累计开机容量。
    required = max(max(0, h.load_mw - wind_capacity * h.wind_cf -
                       solar_capacity * h.solar_cf) + h.load_mw * reserve_ratio
                   for h in day_hours)
    online = []
    capacity = 0.0
    for plant in ordered_plants:
        if capacity >= required:
            break
        online.append(plant)
        capacity += plant.capacity_mw
    return tuple(online)


@dataclass(frozen=True)
class RenewableDispatch:
    wind_available_mw: float
    solar_available_mw: float
    wind_mw: float
    solar_mw: float
    wind_curtailment_mw: float
    solar_curtailment_mw: float


def dispatch_renewables(load_mw: float, wind_capacity_mw: float,
                        solar_capacity_mw: float, wind_cf: float,
                        solar_cf: float, priority="solar_first") -> RenewableDispatch:
    """输入均为 MW/cf，返回一个小时的可用、实际和弃电功率。

    先计算供给过剩量，再按序位分配弃电。没有水电时，说明书六种
    可再生能源序位归并为：光伏先弃、风电先弃、风光同序位按比例弃。
    注意“先弃电”和“先消纳”方向相反，名称直接指弃电对象。
    """
    wind_available = wind_capacity_mw * wind_cf
    solar_available = solar_capacity_mw * solar_cf
    # 弃电总量=max(0,风可用+光可用−可消纳功率)，再按配置序位分摊。
    excess = max(0.0, wind_available + solar_available - load_mw)
    if priority == "solar_first":
        solar_curtailment = min(excess, solar_available)
        wind_curtailment = excess - solar_curtailment
    elif priority == "wind_first":
        wind_curtailment = min(excess, wind_available)
        solar_curtailment = excess - wind_curtailment
    elif priority == "proportional":
        # 同序位类型按当前可用出力比例承担弃电，零供给时无需分配。
        total = wind_available + solar_available
        wind_curtailment = excess * wind_available / total if total else 0.0
        solar_curtailment = excess - wind_curtailment
    else:
        raise ValueError(f"未知弃电序位: {priority}")
    wind = wind_available - wind_curtailment
    solar = solar_available - solar_curtailment
    return RenewableDispatch(wind_available, solar_available, wind, solar,
                             wind_curtailment, solar_curtailment)


@dataclass(frozen=True)
class ThermalDispatch:
    generation_by_plant_mw: Tuple[float, ...]
    total_mw: float
    cost_yuan: float
    remaining_mw: float


def dispatch_thermal(remaining_mw: float, ordered_plants: Tuple[Plant, ...]) -> ThermalDispatch:
    """输入已经按单位成本排序的机组，逐台调用至需求满足或容量耗尽。

    输入是逐日计划确定的在线机组；先承担最小出力，再按成本序位
    增发。检修、爬坡和最小开停机时间仍需要后续独立扩展。
    """
    # 在线机组先满足Pmin≤P≤Pmax，再按变动成本元/MWh升序补足净负荷。
    generation = [plant.min_output_mw for plant in ordered_plants]
    remaining = max(0.0, remaining_mw - sum(generation))
    for i, plant in enumerate(ordered_plants):
        increase = min(remaining, plant.capacity_mw - generation[i])
        generation[i] += increase
        remaining -= increase
    cost = sum(output * p.variable_cost_yuan_per_mwh for output, p in zip(generation, ordered_plants))
    return ThermalDispatch(tuple(generation), sum(generation), cost, remaining)


@dataclass
class StorageState:
    plant: object
    energy_mwh: float  # 小时开始时的内部存储能量，不是向电网放出的电量

    def charge(self, request_mw):
        """仅使用富余电力，受充电功率和可用库容同时限制，步长1h。"""
        spec = self.plant.storage
        # Pch≤min(P请求,Pch,max,(Emax−E)/ηch)，Δt=1h。
        power = min(max(0, request_mw), spec.charge_power_mw,
                    max(0, spec.energy_capacity_mwh - self.energy_mwh) / spec.eta_charge)
        self.energy_mwh += power * spec.eta_charge
        return power

    def discharge(self, request_mw):
        """电网放电量=内部减少能量×放电效率，不能用额定容量代替可放电量。"""
        spec = self.plant.storage
        # Pdis≤min(P请求,Pdis,max,E×ηdis)，随后E'=E−Pdis/ηdis。
        power = min(max(0, request_mw), self.plant.capacity_mw,
                    max(0, self.energy_mwh) * spec.eta_discharge)
        self.energy_mwh -= power / spec.eta_discharge
        return power

    def reserve_mw(self, discharged_mw, charging_mw):
        """保守计算1小时可持续备用；正在充电的储能不重复承担备用。"""
        if charging_mw > 1e-9:
            return 0.0
        # 可持续1h备用=min(剩余放电功率,当前库存×放电效率)。
        return min(max(0, self.plant.capacity_mw - discharged_mw),
                   max(0, self.energy_mwh) * self.plant.storage.eta_discharge)


@dataclass(frozen=True)
class HourlyDispatch:
    """单小时系统结果，功率均MW；库存字段MWh，残差用于守恒审计。"""
    hour: int
    load_mw: float
    wind_available_mw: float
    solar_available_mw: float
    wind_mw: float
    solar_mw: float
    thermal_mw: float
    wind_curtailment_mw: float
    solar_curtailment_mw: float
    unserved_mw: float
    storage_charge_mw: float
    storage_discharge_mw: float
    storage_energy_start_mwh: float
    storage_energy_end_mwh: float
    thermal_online_mw: float
    reserve_requirement_mw: float
    reserve_available_mw: float
    reserve_shortfall_mw: float
    overgeneration_mw: float
    balance_residual_mw: float


@dataclass(frozen=True)
class StorageHour:
    """每座储能每小时的充放电、期初期末内部库存和状态残差。"""
    hour: int
    name: str
    charge_mw: float
    discharge_mw: float
    start_energy_mwh: float
    end_energy_mwh: float
    soc_end: float
    state_residual_mwh: float


@dataclass(frozen=True)
class Simulation:
    """全年指标：MW按1h求和成MWh；hourly可按需保留8760个点。"""
    thermal_mwh: float
    wind_available_mwh: float
    solar_available_mwh: float
    wind_mwh: float
    solar_mwh: float
    wind_curtailment_mwh: float
    solar_curtailment_mwh: float
    unserved_mwh: float
    shortage_hours: int
    max_balance_residual_mw: float
    variable_cost_yuan: float
    storage_charge_mwh: float
    storage_discharge_mwh: float
    storage_initial_mwh: float
    storage_final_mwh: float
    storage_loss_mwh: float
    max_storage_residual_mwh: float
    reserve_shortfall_mwh: float
    reserve_shortfall_hours: int
    overgeneration_mwh: float
    hourly: Optional[Tuple[HourlyDispatch, ...]]
    storage_hourly: Optional[Tuple[StorageHour, ...]]
    solver_log: tuple = ()  # 优化模式每个滚动窗口的状态、耗时和模型规模


def simulate(problem: Problem, chromosome: Tuple[int, ...], keep_hourly=False) -> Simulation:
    """一个建设方案的全过程。每小时功率步长1h，所有状态只在年初初始化。

    储能先吸收净富余电力，非充电小时在高净负荷或容量不足时放电。
    高净负荷阈值取未来H小时平均正净负荷；这是可解释的前瞻规则，
    并非LP/MILP最优解。SOC不会在24h边界复位。
    """
    if len(chromosome) != len(problem.candidates) or any(bit not in (0, 1) for bit in chromosome):
        raise ValueError("染色体长度或取值错误")
    plants = problem.existing + tuple(p for bit, p in zip(chromosome, problem.candidates) if bit)
    wind_capacity = sum(p.capacity_mw for p in plants if p.technology == "wind")
    solar_capacity = sum(p.capacity_mw for p in plants if p.technology == "solar")
    thermal = tuple(sorted((p for p in plants if p.technology == "thermal"),
                           key=lambda p: (p.variable_cost_yuan_per_mwh, p.name)))
    states = [StorageState(p, p.storage.initial_energy_mwh) for p in plants if p.technology == "storage"]
    initial_energy = sum(s.energy_mwh for s in states)
    wind_cost, solar_cost = _renewable_cost(plants, "wind"), _renewable_cost(plants, "solar")
    # 前缀和用于O(1)查询未来H小时平均净负荷，避免每小时重复扫描窗口。
    prefix = [0.0]
    for h in problem.hours:
        prefix.append(prefix[-1] + max(0, h.load_mw - wind_capacity * h.wind_cf - solar_capacity * h.solar_cf))
    sums = {key: 0.0 for key in ("thermal", "wind_avail", "solar_avail", "wind", "solar",
                                "wind_curt", "solar_curt", "unserved", "cost", "charge",
                                "discharge", "reserve_gap", "overgeneration")}
    shortage_hours = reserve_hours = 0
    max_balance = max_state_residual = 0.0
    detail, storage_detail = ([] if keep_hourly else None), ([] if keep_hourly else None)
    online = ()

    for index, hour in enumerate(problem.hours):
        if index % 24 == 0:
            online = commit_for_day(problem.hours[index:index + 24], thermal,
                                    wind_capacity, solar_capacity, problem.operating_reserve_ratio)
        capacity = sum(p.capacity_mw for p in online)
        minimum = sum(p.min_output_mw for p in online)
        wind_available, solar_available = wind_capacity * hour.wind_cf, solar_capacity * hour.solar_cf
        starts = [s.energy_mwh for s in states]
        charge_powers, discharge_powers = [0.0] * len(states), [0.0] * len(states)

        # 第1层：吸收风光与必须运行火电共同形成的富余；受库容和功率限制。
        surplus = max(0.0, minimum + wind_available + solar_available - hour.load_mw)
        for i, state in enumerate(states):
            charge_powers[i] = state.charge(surplus)
            surplus -= charge_powers[i]
        charge = sum(charge_powers)
        # 第2层：充电后仍过剩，按配置的风光调峰序位弃电；先弃与先消纳方向相反。
        renewable = dispatch_renewables(max(0, hour.load_mw + charge - minimum),
                                        wind_capacity, solar_capacity, hour.wind_cf,
                                        hour.solar_cf, problem.curtailment_priority)
        net_demand = hour.load_mw + charge - renewable.wind_mw - renewable.solar_mw
        # 第3层：只有未充电的小时才放电，缓解峰荷或容量缺口。
        end = min(len(problem.hours), index + problem.storage_lookahead_hours)
        threshold = (prefix[end] - prefix[index]) / (end - index)
        discharge_request = max(0, net_demand - threshold, net_demand - capacity)
        discharge_request = min(discharge_request, max(0, net_demand - minimum))
        if charge <= 1e-9:
            for i, state in enumerate(states):
                discharge_powers[i] = state.discharge(discharge_request)
                discharge_request -= discharge_powers[i]
        discharge = sum(discharge_powers)
        # 第4层：在在线机组最小/最大出力内按成本调用；缺口显式记为ENS。
        thermal_dispatch = dispatch_thermal(net_demand - discharge, online)
        unserved = thermal_dispatch.remaining_mw
        source = thermal_dispatch.total_mw + renewable.wind_mw + renewable.solar_mw + discharge
        demand = hour.load_mw + charge
        # 若最小火电出力本身过大，不能偷偷删除电能，明确记录物理调度不可行过剩。
        overgeneration = max(0, source - demand)
        balance = source + unserved - demand - overgeneration
        reserve_requirement = hour.load_mw * problem.operating_reserve_ratio
        reserve_available = max(0, capacity - thermal_dispatch.total_mw) + sum(
            s.reserve_mw(discharge_powers[i], charge_powers[i]) for i, s in enumerate(states))
        reserve_gap = max(0, reserve_requirement - reserve_available)
        max_balance = max(max_balance, abs(balance))
        if abs(balance) > 1e-7:
            raise ArithmeticError(f"第{index}小时功率不平衡: {balance} MW")
        for i, state in enumerate(states):
            spec = state.plant.storage
            residual = state.energy_mwh - starts[i] - spec.eta_charge * charge_powers[i] + discharge_powers[i] / spec.eta_discharge
            max_state_residual = max(max_state_residual, abs(residual))
            if (abs(residual) > 1e-7 or not -1e-7 <= state.energy_mwh <= spec.energy_capacity_mwh + 1e-7 or
                    charge_powers[i] * discharge_powers[i] > 1e-9):
                raise ArithmeticError(f"储能状态不守恒或越界: {state.plant.name},小时{index}")
            if storage_detail is not None:
                storage_detail.append(StorageHour(index, state.plant.name, charge_powers[i],
                                                   discharge_powers[i], starts[i], state.energy_mwh,
                                                   state.energy_mwh / spec.energy_capacity_mwh, residual))
        values = (thermal_dispatch.total_mw, wind_available, solar_available, renewable.wind_mw,
                  renewable.solar_mw, renewable.wind_curtailment_mw, renewable.solar_curtailment_mw,
                  unserved, thermal_dispatch.cost_yuan + renewable.wind_mw * wind_cost +
                  renewable.solar_mw * solar_cost + sum(s.plant.variable_cost_yuan_per_mwh *
                  discharge_powers[i] for i, s in enumerate(states)), charge, discharge, reserve_gap, overgeneration)
        for key, value in zip(sums, values):
            sums[key] += value  # MW×1h=MWh；cost字段本身已经是该小时的元。
        shortage_hours += unserved > 1e-9
        reserve_hours += reserve_gap > 1e-9
        if detail is not None:
            detail.append(HourlyDispatch(index, hour.load_mw, wind_available, solar_available,
                                         renewable.wind_mw, renewable.solar_mw, thermal_dispatch.total_mw,
                                         renewable.wind_curtailment_mw, renewable.solar_curtailment_mw,
                                         unserved, charge, discharge, sum(starts), sum(s.energy_mwh for s in states),
                                         capacity, reserve_requirement, reserve_available, reserve_gap,
                                         overgeneration, balance))
    final_energy = sum(s.energy_mwh for s in states)
    # 网侧输入-网侧输出-库存增加量=充放转换损失，端点库存不得漏算。
    storage_loss = initial_energy + sums["charge"] - sums["discharge"] - final_energy
    return Simulation(sums["thermal"], sums["wind_avail"], sums["solar_avail"], sums["wind"], sums["solar"],
                      sums["wind_curt"], sums["solar_curt"], sums["unserved"], shortage_hours, max_balance,
                      sums["cost"], sums["charge"], sums["discharge"], initial_energy, final_energy,
                      storage_loss, max_state_residual, sums["reserve_gap"], reserve_hours,
                      sums["overgeneration"], tuple(detail) if detail is not None else None,
                      tuple(storage_detail) if storage_detail is not None else None)


def _renewable_cost(plants, technology):
    """聚合风/光出力前核对同技术边际费用一致，避免错误平均价格。"""
    costs = {p.variable_cost_yuan_per_mwh for p in plants if p.technology == technology}
    if len(costs) > 1:
        raise ValueError(f"当前聚合模型要求{technology}电站变动成本相同")
    return next(iter(costs), 0.0)
