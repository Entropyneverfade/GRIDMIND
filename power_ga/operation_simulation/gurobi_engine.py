"""Gurobi滚动MILP：逐小时日历与逐日开机逻辑的联合优化扩展。

每次看未来H小时，只执行前24小时；存量传入下一窗口，不强制日末
回到初始SOC。缺电、过剩、备用短缺按优先级分别最小化，再优化费用。
"""

from .engine import HourlyDispatch, Simulation, StorageHour, _renewable_cost


def simulate(problem, chromosome, keep_hourly=False):
    """返回统一Simulation。Gurobi缺失、许可不足或求解失败均显式报错。"""
    try:
        import gurobipy as gp
        from gurobipy import GRB
    except ImportError as error:
        raise RuntimeError("优化模式需要gurobipy与有效Gurobi许可证") from error
    if len(chromosome) != len(problem.candidates) or any(v not in (0, 1) for v in chromosome):
        raise ValueError("染色体长度或取值错误")
    if problem.storage_lookahead_hours < 24:
        raise ValueError("Gurobi模式的前瞻时长应至少为24小时")
    plants = problem.existing + tuple(p for bit, p in zip(chromosome, problem.candidates) if bit)
    thermal = tuple(p for p in plants if p.technology == "thermal")
    stores = tuple(p for p in plants if p.technology == "storage")
    wc = sum(p.capacity_mw for p in plants if p.technology == "wind")
    sc = sum(p.capacity_mw for p in plants if p.technology == "solar")
    wind_cost, solar_cost = _renewable_cost(plants, "wind"), _renewable_cost(plants, "solar")
    energies = [p.storage.initial_energy_mwh for p in stores]
    initial_energy = sum(energies)
    hourly, storage_hourly, logs = [], [], []
    total_cost = max_balance = max_state = 0.0
    with gp.Env(empty=True) as environment:
        environment.setParam("OutputFlag", 0)
        environment.start()
        for first in range(0, len(problem.hours), 24):
            # 滚动优化：看未来H小时，仅把前24h写入全年结果和下一窗口初态。
            hours = problem.hours[first:first + problem.storage_lookahead_hours]
            n = len(hours)
            executed = min(24, n)
            with gp.Model("rolling_source_load_storage", env=environment) as model:
                model.Params.Threads = 2
                model.Params.TimeLimit = 30
                model.Params.MIPGap = 1e-6
                model.Params.FeasibilityTol = 1e-8
                model.Params.IntFeasTol = 1e-8
                # 二元开机状态以“日”为粒度，而出力和储能以“小时”为粒度。
                on = model.addVars(len(thermal), (n + 23) // 24, vtype=GRB.BINARY, name="on")
                power = model.addVars(len(thermal), n, lb=0, name="thermal")
                charge = model.addVars(len(stores), n, lb=0, name="charge")
                discharge = model.addVars(len(stores), n, lb=0, name="discharge")
                energy = model.addVars(len(stores), n + 1, lb=0, name="energy")
                charging = model.addVars(len(stores), n, vtype=GRB.BINARY, name="charging")
                storage_reserve = model.addVars(len(stores), n, lb=0, name="storage_reserve")
                wind_curt = model.addVars(n, lb=0, name="wind_curt")
                solar_curt = model.addVars(n, lb=0, name="solar_curt")
                shed = model.addVars(n, lb=0, name="unserved")
                spill = model.addVars(n, lb=0, name="physical_overgeneration")
                reserve_gap = model.addVars(n, lb=0, name="reserve_gap")
                priority_switch = model.addVars(n, vtype=GRB.BINARY, name="curtailment_priority")
                for j, plant in enumerate(thermal):
                    for t in range(n):
                        # y_j,d为开机二元量：Pmin_j*y≤P_j,t≤Pmax_j*y。
                        model.addConstr(power[j, t] >= plant.min_output_mw * on[j, t // 24])
                        model.addConstr(power[j, t] <= plant.capacity_mw * on[j, t // 24])
                for s, plant in enumerate(stores):
                    spec = plant.storage
                    model.addConstr(energy[s, 0] == energies[s])
                    for t in range(n + 1):
                        model.addConstr(energy[s, t] <= spec.energy_capacity_mwh)
                    for t in range(n):
                        # 充放电互斥；E[t+1]=E[t]+ηch Pch[t]−Pdis[t]/ηdis，Δt=1h。
                        model.addConstr(charge[s, t] <= spec.charge_power_mw * charging[s, t])
                        model.addConstr(discharge[s, t] <= plant.capacity_mw * (1 - charging[s, t]))
                        model.addConstr(energy[s, t + 1] == energy[s, t] + spec.eta_charge * charge[s, t]
                                        - discharge[s, t] / spec.eta_discharge)
                        model.addConstr(storage_reserve[s, t] <= plant.capacity_mw * (1 - charging[s, t]) - discharge[s, t])
                        # 库存足以持续1小时才能申报相应备用MW。
                        model.addConstr(storage_reserve[s, t] <= energy[s, t + 1] * spec.eta_discharge)
                operating_cost = gp.LinExpr()
                for t, h in enumerate(hours):
                    wa, sa = wc * h.wind_cf, sc * h.solar_cf
                    model.addConstr(wind_curt[t] <= wa)
                    model.addConstr(solar_curt[t] <= sa)
                    model.addConstr(shed[t] <= h.load_mw)
                    # 弃电遵循“第一序位弃至零后再弃第二序位”的先后约束。
                    if problem.curtailment_priority == "solar_first":
                        model.addConstr(wind_curt[t] <= wa * priority_switch[t])
                        model.addConstr(solar_curt[t] >= sa * priority_switch[t])
                    elif problem.curtailment_priority == "wind_first":
                        model.addConstr(solar_curt[t] <= sa * priority_switch[t])
                        model.addConstr(wind_curt[t] >= wa * priority_switch[t])
                    else:
                        model.addConstr(wind_curt[t] * sa == solar_curt[t] * wa)
                    # 源荷储平衡：火+风可用−弃风+光可用−弃光+放电+ENS=负荷+充电+过剩。
                    model.addConstr(gp.quicksum(power[j, t] for j in range(len(thermal))) + wa - wind_curt[t]
                                    + sa - solar_curt[t] + gp.quicksum(discharge[s, t] for s in range(len(stores)))
                                    + shed[t] == h.load_mw + gp.quicksum(charge[s, t] for s in range(len(stores))) + spill[t])
                    # 在线未用火电容量+储能可持续备用+不足量≥r_op×本小时负荷。
                    model.addConstr(gp.quicksum(p.capacity_mw * on[j, t // 24] - power[j, t]
                                               for j, p in enumerate(thermal)) +
                                    gp.quicksum(storage_reserve[s, t] for s in range(len(stores))) + reserve_gap[t]
                                    >= h.load_mw * problem.operating_reserve_ratio)
                    operating_cost += gp.quicksum(p.variable_cost_yuan_per_mwh * power[j, t]
                                                   for j, p in enumerate(thermal))
                    operating_cost += (wa - wind_curt[t]) * wind_cost + (sa - solar_curt[t]) * solar_cost
                    operating_cost += gp.quicksum(p.variable_cost_yuan_per_mwh * discharge[s, t]
                                                   for s, p in enumerate(stores))
                # 近似窗口外存量价值缓解短视放空；是调度政策参数，不计入实际年运行费。
                operating_cost -= problem.terminal_storage_value_yuan_per_mwh * gp.quicksum(
                    energy[s, n] - energies[s] for s in range(len(stores)))
                # 多目标按优先级字典序：先保供和物理可行，再最小费用，最后最小弃电。
                for i, (objective, name) in enumerate(((shed.sum(), "ENS"), (spill.sum(), "overgeneration"),
                        (reserve_gap.sum(), "reserve_shortfall"), (operating_cost, "operating_cost"),
                        (wind_curt.sum() + solar_curt.sum(), "curtailment"))):
                    model.setObjectiveN(objective, i, priority=5 - i, abstol=1e-8, reltol=0, name=name)
                model.setObjectiveN(on.sum(), 5, priority=0, abstol=1e-8, reltol=0, name="online_units_tie_break")
                model.optimize()
                if model.Status != GRB.OPTIMAL or model.SolCount == 0:
                    raise RuntimeError(f"Gurobi窗口{first}求解未最优完成: status={model.Status}, solutions={model.SolCount}")
                logs.append({"first_hour": first, "lookahead_hours": n, "executed_hours": executed,
                             "status": int(model.Status), "runtime_seconds": model.Runtime,
                             "variables": model.NumVars, "constraints": model.NumConstrs,
                             "optimal": True, "configured_mip_gap": model.Params.MIPGap})
                for t in range(executed):
                    h = hours[t]
                    start_energy = sum(energy[s, t].X for s in range(len(stores)))
                    end_energy = sum(energy[s, t + 1].X for s in range(len(stores)))
                    ch = sum(charge[s, t].X for s in range(len(stores)))
                    dis = sum(discharge[s, t].X for s in range(len(stores)))
                    th = sum(power[j, t].X for j in range(len(thermal)))
                    online = sum(p.capacity_mw * on[j, t // 24].X for j, p in enumerate(thermal))
                    wa, sa = wc * h.wind_cf, sc * h.solar_cf
                    wind, solar = wa - wind_curt[t].X, sa - solar_curt[t].X
                    balance = th + wind + solar + dis + shed[t].X - h.load_mw - ch - spill[t].X
                    reserve_available = online - th + sum(min(p.capacity_mw * (1 - charging[s, t].X)
                                               - discharge[s, t].X, energy[s, t + 1].X * p.storage.eta_discharge)
                                                          for s, p in enumerate(stores))
                    max_balance = max(max_balance, abs(balance))
                    if abs(balance) > 1e-6:
                        raise ArithmeticError("Gurobi解的功率平衡残差超限")
                    for s, p in enumerate(stores):
                        spec = p.storage
                        residual = energy[s, t + 1].X - energy[s, t].X - spec.eta_charge * charge[s, t].X + discharge[s, t].X / spec.eta_discharge
                        max_state = max(max_state, abs(residual))
                        if abs(residual) > 1e-6 or charge[s, t].X * discharge[s, t].X > 1e-6:
                            raise ArithmeticError("Gurobi解的储能状态或互斥约束错误")
                        storage_hourly.append(StorageHour(first + t, p.name, charge[s, t].X, discharge[s, t].X,
                            energy[s, t].X, energy[s, t + 1].X, energy[s, t + 1].X / spec.energy_capacity_mwh, residual))
                    total_cost += sum(p.variable_cost_yuan_per_mwh * power[j, t].X for j, p in enumerate(thermal))
                    total_cost += wind * wind_cost + solar * solar_cost + sum(p.variable_cost_yuan_per_mwh * discharge[s, t].X for s, p in enumerate(stores))
                    hourly.append(HourlyDispatch(first + t, h.load_mw, wa, sa, wind, solar, th,
                        wind_curt[t].X, solar_curt[t].X, shed[t].X, ch, dis, start_energy, end_energy,
                        online, h.load_mw * problem.operating_reserve_ratio, reserve_available,
                        max(0, h.load_mw * problem.operating_reserve_ratio - reserve_available), spill[t].X, balance))
                # 只保留执行24h后的真实库存，而不是整个前瞻窗口的终点库存。
                energies = [energy[s, executed].X for s in range(len(stores))]
            if keep_hourly and (first // 24 + 1) % 60 == 0:
                print(f"Gurobi已完成{first // 24 + 1}天", flush=True)
    def total(field):
        """逐小时MW按1h累加成MWh，备用不足对应MW·h。"""
        return sum(getattr(h, field) for h in hourly)
    charge_total, discharge_total, final_energy = total("storage_charge_mw"), total("storage_discharge_mw"), sum(energies)
    return Simulation(total("thermal_mw"), total("wind_available_mw"), total("solar_available_mw"),
        total("wind_mw"), total("solar_mw"), total("wind_curtailment_mw"), total("solar_curtailment_mw"),
        total("unserved_mw"), sum(h.unserved_mw > 1e-7 for h in hourly), max_balance, total_cost,
        charge_total, discharge_total, initial_energy, final_energy, initial_energy + charge_total - discharge_total - final_energy,
        max_state, total("reserve_shortfall_mw"), sum(h.reserve_shortfall_mw > 1e-7 for h in hourly),
        total("overgeneration_mw"), tuple(hourly) if keep_hourly else None,
        tuple(storage_hourly) if keep_hourly else None, tuple(logs))
