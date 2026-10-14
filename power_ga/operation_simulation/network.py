"""分区电力平衡与跨区传输的小时线性模型；线路参数必须显式输入。"""

from dataclasses import dataclass
from math import isfinite
from collections import deque


@dataclass(frozen=True)
class Zone:
    """负荷、风光可用功率与固定储能功率均为该小时的MW。"""

    name: str
    demand_mw: float
    wind_available_mw: float = 0.0
    solar_available_mw: float = 0.0
    fixed_discharge_mw: float = 0.0
    fixed_charge_mw: float = 0.0


@dataclass(frozen=True)
class Generator:
    """可调机组出力范围与变动成本；每个小时可重新给定可用容量。"""

    name: str
    zone: str
    minimum_mw: float
    maximum_mw: float
    cost_yuan_per_mwh: float
    technology: str = "unclassified"


@dataclass(frozen=True)
class Link:
    """正流向为source→target；ac用等值电纳，dc为可控传输。"""

    name: str
    source: str
    target: str
    limit_mw: float
    kind: str = "dc"
    susceptance_mw_per_rad: float | None = None


@dataclass(frozen=True)
class NetworkResult:
    """一小时最优解；逐区残差和线路限额均应在数值容差内。"""

    generation_mw: dict
    flows_mw: dict
    zones: dict
    max_balance_residual_mw: float
    objective_yuan: float


@dataclass(frozen=True)
class NetworkSeriesResult:
    """连续小时结果；每小时独立优化，固定储能计划由调用方提供。"""

    hourly: tuple[NetworkResult, ...]
    max_balance_residual_mw: float
    total_unserved_mwh: float
    total_wind_curtailment_mwh: float
    total_solar_curtailment_mwh: float


def solve_network_hour(zones, generators, links, *,
                       shortage_cost_yuan_per_mwh=1_000_000.0,
                       spill_cost_yuan_per_mwh=10_000.0):
    """求解线性经济调度，含区间传输、分区缺供和中性风光弃电。

    各区平衡：常规出力+风光使用+固定放电+缺供+净流入
    =负荷+固定充电+溢出。AC边满足 f=b(θ源−θ受)，DC边为可控f。
    这是无损有功近似；没有电压、无功、N-1、动态稳定或损耗。
    """
    import builtins

    # PyInstaller的隔离解释器可能不执行site初始化；Gurobi扩展导入时会引用help。
    if not hasattr(builtins, "help"):
        import site
        site.sethelper()
    import gurobipy as gp
    from gurobipy import GRB

    zones = tuple(zones)
    generators = tuple(generators)
    links = tuple(links)
    names = [zone.name for zone in zones]
    if not names or len(names) != len(set(names)):
        raise ValueError("分区不能为空且名称必须唯一")
    zone_by_name = {zone.name: zone for zone in zones}
    for zone in zones:
        quantities = (zone.demand_mw, zone.wind_available_mw, zone.solar_available_mw,
                      zone.fixed_charge_mw, zone.fixed_discharge_mw)
        if any(not isfinite(value) or value < 0 for value in quantities):
            raise ValueError(f"分区功率必须是非负有限值：{zone.name}")
    if shortage_cost_yuan_per_mwh <= 0 or spill_cost_yuan_per_mwh <= 0:
        raise ValueError("缺供和溢出罚价必须为正")
    generator_names = set()
    for unit in generators:
        if (unit.name in generator_names or unit.zone not in zone_by_name or
                min(unit.minimum_mw, unit.maximum_mw, unit.cost_yuan_per_mwh) < 0 or
                unit.minimum_mw > unit.maximum_mw or
                any(not isfinite(value) for value in
                    (unit.minimum_mw, unit.maximum_mw, unit.cost_yuan_per_mwh))):
            raise ValueError(f"机组参数或分区错误：{unit.name}")
        generator_names.add(unit.name)
    link_names = set()
    for link in links:
        if (link.name in link_names or link.source not in zone_by_name or
                link.target not in zone_by_name or link.source == link.target or
                not isfinite(link.limit_mw) or link.limit_mw <= 0 or
                link.kind not in {"ac", "dc"} or
                (link.kind == "ac" and (link.susceptance_mw_per_rad is None or
                 not isfinite(link.susceptance_mw_per_rad) or
                 link.susceptance_mw_per_rad <= 0))):
            raise ValueError(f"联络线参数错误：{link.name}")
        link_names.add(link.name)

    model = gp.Model("gridmind_zonal_hour")
    model.Params.OutputFlag = 0
    # g_j∈[Pmin,Pmax]；风光只建总使用量R，解后按可用份额分给风、光。
    generation = {unit.name: model.addVar(lb=unit.minimum_mw, ub=unit.maximum_mw,
                                           name=f"g_{index}")
                  for index, unit in enumerate(generators)}
    renewable = {name: model.addVar(lb=0, ub=zone.wind_available_mw + zone.solar_available_mw,
                                    name=f"renew_{index}")
                 for index, (name, zone) in enumerate(zone_by_name.items())}
    shortage = {name: model.addVar(lb=0, name=f"short_{index}")
                for index, name in enumerate(names)}
    spill = {name: model.addVar(lb=0, name=f"spill_{index}")
             for index, name in enumerate(names)}
    flow = {link.name: model.addVar(lb=-link.limit_mw, ub=link.limit_mw,
                                    name=f"flow_{index}")
            for index, link in enumerate(links)}
    # 多个交流孤岛各设一个角度参考；直流联络不强迫两岛同步。
    parent = {name: name for name in names}

    def root(name):
        while parent[name] != name:
            name = parent[name]
        return name

    for link in links:
        if link.kind == "ac":
            parent[root(link.target)] = root(link.source)
    references = {root(name) for name in names}
    angle = {name: model.addVar(lb=-GRB.INFINITY, name=f"theta_{index}")
             for index, name in enumerate(names)}
    for name in references:
        model.addConstr(angle[name] == 0)
    for link in links:
        if link.kind == "ac":
            # 交流DC近似潮流：f_ij=b_ij(θ_i−θ_j)，电纳由用户输入。
            model.addConstr(flow[link.name] == link.susceptance_mw_per_rad *
                            (angle[link.source] - angle[link.target]))
    for name, zone in zone_by_name.items():
        local = gp.quicksum(generation[unit.name] for unit in generators if unit.zone == name)
        incoming = gp.quicksum(flow[link.name] for link in links if link.target == name)
        outgoing = gp.quicksum(flow[link.name] for link in links if link.source == name)
        model.addConstr(local + renewable[name] + zone.fixed_discharge_mw +
                        shortage[name] + incoming - outgoing ==
                        zone.demand_mw + zone.fixed_charge_mw + spill[name])
    # 正的新能源弃电罚价使可用电优先消纳；小流量罚价排除无意义环流。
    abs_flow = {link.name: model.addVar(lb=0, name=f"absflow_{index}")
                for index, link in enumerate(links)}
    for link in links:
        model.addConstr(abs_flow[link.name] >= flow[link.name])
        model.addConstr(abs_flow[link.name] >= -flow[link.name])
    model.setObjective(
        gp.quicksum(unit.cost_yuan_per_mwh * generation[unit.name] for unit in generators) +
        gp.quicksum(shortage_cost_yuan_per_mwh * shortage[name] +
                    spill_cost_yuan_per_mwh * spill[name] +
                    0.01 * (zone.wind_available_mw + zone.solar_available_mw - renewable[name])
                    for name, zone in zone_by_name.items()) +
        gp.quicksum(0.0001 * abs_flow[link.name] for link in links), GRB.MINIMIZE)
    model.optimize()
    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(f"分区运行模型未得到最优解，Gurobi状态={model.Status}")
    gen_values = {name: var.X for name, var in generation.items()}
    flow_values = {name: var.X for name, var in flow.items()}
    zone_results = {}
    residuals = []
    for name, zone in zone_by_name.items():
        total_available = zone.wind_available_mw + zone.solar_available_mw
        used = renewable[name].X
        # Qw=(A−R)Aw/A，Qs=(A−R)As/A，A=Aw+As；A=0时均为0。
        curtailed = max(0.0, total_available - used)
        wind_curtail = curtailed * zone.wind_available_mw / total_available if total_available else 0.0
        solar_curtail = curtailed - wind_curtail
        local = sum(gen_values[unit.name] for unit in generators if unit.zone == name)
        imports = sum(flow_values[link.name] for link in links if link.target == name)
        exports = sum(flow_values[link.name] for link in links if link.source == name)
        residual = (local + used + zone.fixed_discharge_mw + shortage[name].X + imports -
                    exports - zone.demand_mw - zone.fixed_charge_mw - spill[name].X)
        residuals.append(abs(residual))
        zone_results[name] = {"wind_mw": zone.wind_available_mw - wind_curtail,
                              "solar_mw": zone.solar_available_mw - solar_curtail,
                              "wind_curtailment_mw": wind_curtail,
                              "solar_curtailment_mw": solar_curtail,
                              "unserved_mw": shortage[name].X,
                              "spill_mw": spill[name].X,
                              "balance_residual_mw": residual}
    return NetworkResult(gen_values, flow_values, zone_results,
                         max(residuals, default=0.0), model.ObjVal)


def solve_network_timeseries(hourly_zones, hourly_generators, links):
    """逐小时调用分区模型；1h步长时Σ_t功率(MW)即全年电量(MWh)。

    输入可以有8760个小时；时序储能库存与水量需由上层运行模型提供，
    此处仅验收其固定充放电并求同小时的机组与跨区传输。
    """
    zone_hours = tuple(hourly_zones)
    generator_hours = tuple(hourly_generators)
    if not zone_hours or len(zone_hours) != len(generator_hours):
        raise ValueError("分区与机组的小时序列必须非空且等长")
    results = tuple(solve_network_hour(zones, generators, links)
                    for zones, generators in zip(zone_hours, generator_hours))
    zone_rows = (values for result in results for values in result.zones.values())
    # 在一个循环内累计三个电量，避免多次遍历可能的一次性迭代器。
    unserved = wind_curtail = solar_curtail = 0.0
    for values in zone_rows:
        unserved += values["unserved_mw"]
        wind_curtail += values["wind_curtailment_mw"]
        solar_curtail += values["solar_curtailment_mw"]
    return NetworkSeriesResult(results,
                               max(result.max_balance_residual_mw for result in results),
                               unserved, wind_curtail, solar_curtail)


def solve_network_hour_heuristic(zones, generators, links):
    """可控区间通道的确定性启发式调度，不依赖求解器。

    步骤为可再生及最低出力→剩余容量路径送电→变动成本序位增发
    →缺供/风光按可用份额弃电。交流网环流不能用自由路径模拟，故本函数
    只接受可控直流/等值传输通道；结果是可行调度而非费用最优证明。
    """
    zones = tuple(zones)
    generators = tuple(generators)
    links = tuple(links)
    names = tuple(zone.name for zone in zones)
    name_set = set(names)
    if not zones or len(name_set) != len(zones):
        raise ValueError("分区不能为空且名称必须唯一")
    if any(link.kind != "dc" or link.source not in name_set or link.target not in name_set or
           link.source == link.target or not isfinite(link.limit_mw) or link.limit_mw <= 0
           for link in links):
        raise ValueError("启发式模式仅接受参数有效的可控直流/等值传输通道")
    if len({link.name for link in links}) != len(links):
        raise ValueError("联络线名称必须唯一")
    if len({unit.name for unit in generators}) != len(generators):
        raise ValueError("机组名称必须唯一")
    for zone in zones:
        if any(not isfinite(v) or v < 0 for v in
               (zone.demand_mw, zone.wind_available_mw, zone.solar_available_mw,
                zone.fixed_charge_mw, zone.fixed_discharge_mw)):
            raise ValueError("分区输入必须是非负有限值")
    for unit in generators:
        if (unit.zone not in name_set or unit.minimum_mw < 0 or
                unit.maximum_mw < unit.minimum_mw or unit.cost_yuan_per_mwh < 0 or
                any(not isfinite(v) for v in (unit.minimum_mw, unit.maximum_mw,
                                               unit.cost_yuan_per_mwh))):
            raise ValueError("机组参数错误")
    zone_map = {zone.name: zone for zone in zones}
    output = {unit.name: unit.minimum_mw for unit in generators}
    flow = {link.name: 0.0 for link in links}
    # n_i=本地最低出力+风光可用+固定放电−负荷−固定充电；n_i>0可外送。
    net = {name: sum(output[unit.name] for unit in generators if unit.zone == name) +
           zone.wind_available_mw + zone.solar_available_mw + zone.fixed_discharge_mw -
           zone.demand_mw - zone.fixed_charge_mw for name, zone in zone_map.items()}

    def path(source, target):
        """在当前线路余量上广度优先找一条可行增广路。"""
        queue = deque([source])
        previous = {source: None}
        while queue:
            current = queue.popleft()
            if current == target:
                break
            for link in links:
                for neighbor, direction, residual in (
                    (link.target, 1, link.limit_mw - flow[link.name])
                    if current == link.source else (None, 0, 0),
                    (link.source, -1, link.limit_mw + flow[link.name])
                    if current == link.target else (None, 0, 0),
                ):
                    if neighbor is not None and neighbor not in previous and residual > 1e-9:
                        previous[neighbor] = (current, link, direction, residual)
                        queue.append(neighbor)
        if target not in previous:
            return (), 0.0
        steps, limit, current = [], float("inf"), target
        while current != source:
            prior, link, direction, residual = previous[current]
            steps.append((link, direction))
            limit = min(limit, residual)
            current = prior
        return tuple(steps), limit

    def transfer(source, target, maximum):
        """增广量δ=min(源富余,受端缺额,各边剩余容量)。"""
        steps, limit = path(source, target)
        amount = min(maximum, limit)
        if amount <= 1e-9:
            return 0.0
        for link, direction in steps:
            flow[link.name] += direction * amount
        net[source] -= amount
        net[target] += amount
        return amount

    # 零边际成本的当地风光富余优先跨区消纳，可多次经过中间分区。
    for source in names:
        for target in names:
            if source != target:
                while net[source] > 1e-9 and net[target] < -1e-9:
                    moved = transfer(source, target, min(net[source], -net[target]))
                    if moved <= 1e-9:
                        break
    # 可调机组按成本从低到高增发；先满足本站，再沿剩余通道输送。
    for unit in sorted(generators, key=lambda item: (item.cost_yuan_per_mwh, item.name)):
        remaining = unit.maximum_mw - output[unit.name]
        local = min(remaining, max(0.0, -net[unit.zone]))
        output[unit.name] += local
        net[unit.zone] += local
        remaining -= local
        for target in names:
            if target == unit.zone:
                continue
            while remaining > 1e-9 and net[target] < -1e-9:
                steps, limit = path(unit.zone, target)
                amount = min(remaining, -net[target], limit)
                if amount <= 1e-9:
                    break
                output[unit.name] += amount
                remaining -= amount
                net[unit.zone] += amount
                # 调用相同增广操作更新线路和受端，不虚构供给。
                transfer(unit.zone, target, amount)
    zone_results, residuals = {}, []
    for name, zone in zone_map.items():
        available = zone.wind_available_mw + zone.solar_available_mw
        curtail = min(max(0.0, net[name]), available)
        wind_curtail = curtail * zone.wind_available_mw / available if available else 0.0
        solar_curtail = curtail - wind_curtail
        unserved = max(0.0, -net[name])
        spill = max(0.0, net[name] - curtail)
        imports = sum(flow[link.name] for link in links if link.target == name)
        exports = sum(flow[link.name] for link in links if link.source == name)
        residual = (sum(output[unit.name] for unit in generators if unit.zone == name) +
                    available - curtail + zone.fixed_discharge_mw + unserved + imports -
                    exports - zone.demand_mw - zone.fixed_charge_mw - spill)
        residuals.append(abs(residual))
        zone_results[name] = {"wind_mw": zone.wind_available_mw - wind_curtail,
                              "solar_mw": zone.solar_available_mw - solar_curtail,
                              "wind_curtailment_mw": wind_curtail,
                              "solar_curtailment_mw": solar_curtail,
                              "unserved_mw": unserved, "spill_mw": spill,
                              "balance_residual_mw": residual}
    objective = (sum(unit.cost_yuan_per_mwh * output[unit.name] for unit in generators) +
                 sum(1_000_000 * row["unserved_mw"] + 10_000 * row["spill_mw"] +
                     0.01 * (row["wind_curtailment_mw"] + row["solar_curtailment_mw"])
                     for row in zone_results.values()) +
                 0.0001 * sum(abs(value) for value in flow.values()))
    return NetworkResult(output, flow, zone_results, max(residuals, default=0.0), objective)
