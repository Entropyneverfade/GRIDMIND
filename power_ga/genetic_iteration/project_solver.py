"""项目算例规划评价：复用轮盘赌、交叉、位变异和精英保留。"""

from ..common.domain import ANNUAL_ENERGY_TOLERANCE_MWH, POWER_TOLERANCE_MW
from ..fitness_and_convergence.evaluation import Evaluation
from ..operation_simulation.project_engine import simulate_project
from .solver import optimize


def evaluate_project(case, chromosome):
    """目标=候选年化资本费+运行费；缺供、在线备用与容量均为硬约束。"""
    simulation = simulate_project(case, chromosome, keep_hourly=False)
    metrics = simulation.summary
    built = [p for bit, p in zip(chromosome, case.candidates) if bit]
    fixed = sum(p.annual_cost_yuan for p in built)
    # 风光容量信用需经ELCC或多场景可靠性另算；这里保守取0。
    firm_types = {"coal", "gas", "hydro", "biomass"}
    firm = sum(p.capacity_mw for p in case.existing if p.technology in firm_types)
    firm += sum(p.capacity_mw for p in built if p.technology in firm_types)
    domestic_peak = max(case.domestic_load_mw)
    required = domestic_peak * (1 + case.reserve_margin)
    reserve_gap = max(0.0, required - firm)
    unserved = metrics["unserved"]
    over = metrics["overgeneration"]
    online_reserve_gap = metrics["reserve_shortfall"]
    # 在线备用短缺为逐时 max(0, r×总负荷−可用备用)×1h 的年度积分。
    # 只有全年积分不超数值容差才可行，不能仅用额定装机备用替代运行备用。
    feasible = (unserved <= ANNUAL_ENERGY_TOLERANCE_MWH and
                over <= ANNUAL_ENERGY_TOLERANCE_MWH and
                online_reserve_gap <= ANNUAL_ENERGY_TOLERANCE_MWH and
                reserve_gap <= POWER_TOLERANCE_MW)
    scale = max(sum(case.domestic_load_mw), 1.0)
    violation = ((unserved + over + online_reserve_gap) / scale +
                 reserve_gap / max(domestic_peak, 1.0))
    return Evaluation(tuple(chromosome), fixed, metrics["variable_cost"],
                      fixed + metrics["variable_cost"], unserved,
                      int(metrics["shortage_hours"]), firm, required, reserve_gap,
                      online_reserve_gap, over, feasible, violation)


def optimize_project(case, settings, progress=None):
    """适应度、精英和终止条件与通用GA相同，仅替换8760h评价器。"""
    if not case.candidates:
        raise ValueError("该目标年没有相对基年的新增候选容量；可直接运行模拟")
    return optimize(case, settings, evaluator=evaluate_project, progress=progress)
