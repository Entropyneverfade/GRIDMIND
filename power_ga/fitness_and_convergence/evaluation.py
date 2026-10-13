"""规划评价：年化成本最小，缺供和备用率是硬约束。"""

from dataclasses import dataclass
from typing import List, Tuple

from ..common.domain import Problem
from ..common.domain import GASettings, POWER_TOLERANCE_MW, ANNUAL_ENERGY_TOLERANCE_MWH
from ..operation_simulation.engine import Simulation
from ..operation_simulation import simulate


@dataclass(frozen=True)
class Evaluation:
    chromosome: Tuple[int, ...]
    annual_fixed_cost_yuan: float
    variable_cost_yuan: float
    total_cost_yuan: float
    unserved_mwh: float
    shortage_hours: int
    firm_capacity_mw: float
    required_firm_capacity_mw: float
    reserve_gap_mw: float
    reserve_shortfall_mwh: float
    overgeneration_mwh: float
    feasible: bool
    violation: float

    def sort_key(self):
        """可行方案优先；可行方案比成本，不可行方案比归一化违约程度。"""
        return (0, self.total_cost_yuan) if self.feasible else (1, self.violation, self.total_cost_yuan)


def evaluate(problem: Problem, chromosome: Tuple[int, ...], simulation=None) -> Evaluation:
    """把运行结果转为规划评价；返回成本和可行性，供遗传算法比较。"""
    result: Simulation = simulation if simulation is not None else simulate(problem, chromosome)
    built = [p for bit, p in zip(chromosome, problem.candidates) if bit]
    fixed = sum(p.annual_fixed_cost_yuan for p in built)
    firm = sum(p.firm_capacity_mw for p in problem.existing) + sum(p.firm_capacity_mw for p in built)
    peak = max(h.load_mw for h in problem.hours)
    required_firm = peak * (1 + problem.reserve_margin)
    reserve_gap = max(0.0, required_firm - firm)
    excess_unserved = max(0.0, result.unserved_mwh - problem.max_unserved_mwh)
    excess_reserve = max(0, result.reserve_shortfall_mwh - problem.max_reserve_shortfall_mwh)
    # 多目标MILP会产生累计1e-6MWh级浮点误差；保留原值并按统一容差判断。
    feasible = (excess_unserved <= ANNUAL_ENERGY_TOLERANCE_MWH and reserve_gap <= POWER_TOLERANCE_MW and
                excess_reserve <= ANNUAL_ENERGY_TOLERANCE_MWH and
                result.overgeneration_mwh <= ANNUAL_ENERGY_TOLERANCE_MWH)
    annual_load = sum(h.load_mw for h in problem.hours)
    # 两种约束单位不同，分别除以全年负荷电量、峰值负荷后再相加。
    # 这个无量纲值只用来比较不可行方案，不替代硬约束。
    violation = ((excess_unserved + excess_reserve + result.overgeneration_mwh) / annual_load
                 + reserve_gap / peak)
    return Evaluation(chromosome, fixed, result.variable_cost_yuan,
                      fixed + result.variable_cost_yuan, result.unserved_mwh,
                      result.shortage_hours, firm, required_firm, reserve_gap,
                      result.reserve_shortfall_mwh, result.overgeneration_mwh,
                      feasible, violation)


def ppt_fitness(costs: List[float]) -> List[float]:
    """AF_i=(ΣOF-OF_i)/((N-1)ΣOF)；低成本适应度较高，概率总和为1。"""
    n = len(costs)
    if n < 2 or any(cost <= 0 for cost in costs):
        raise ValueError("PPT适应度要求至少两个正成本方案")
    total = sum(costs)
    return [(total - cost) / ((n - 1) * total) for cost in costs]


def should_stop(feasible: bool, generation: int, stalled: int, settings: GASettings) -> bool:
    """达到最小代数，且可行最优方案连续停滞指定代数时停止。

    若始终未找到可行解，不把“成本停滞”报告成成功收敛，继续至代数上限。
    """
    return (feasible and generation >= settings.min_generations and
            stalled >= settings.stall_generations)
