"""时间阶段动态规划：状态是已投运项目集合，阶段运行费用取8760小时模拟。"""

from dataclasses import dataclass
from math import inf, isclose
from types import SimpleNamespace

from ..common.domain import GASettings
from ..fitness_and_convergence.evaluation import Evaluation
from ..genetic_iteration.project_solver import evaluate_project
from ..genetic_iteration.solver import optimize
from ..operation_simulation.project_engine import simulate_project


@dataclass(frozen=True)
class StageResult:
    """一年的最优建设状态；state第i位=1表示该候选在当年已投运。"""
    year: int
    state: int
    newly_built: int
    annual_cost_yuan: float
    discounted_cost_yuan: float
    max_balance_residual_mw: float


@dataclass(frozen=True)
class PlanningResult:
    """保存DP与Gurobi两条独立求解路径，供结果表审计。"""
    stages: tuple[StageResult, ...]
    objective_yuan: float
    gurobi_objective_yuan: float
    gurobi_states: tuple[int, ...]
    evaluated_states: int
    discount_rate: float
    evaluations: tuple[dict[int, Evaluation], ...]


def _bits(mask, count):
    """从整数状态取0/1投运向量；位序始终与case.candidates一致。"""
    return tuple((mask >> i) & 1 for i in range(count))


def _state_costs(cases, count, progress=None):
    """每一阶段每一状态只运行一次8760小时；可行性由共同评价器判断。"""
    tables = []
    for t, case in enumerate(cases):
        row = {}
        for state in range(1 << count):
            row[state] = evaluate_project(case, _bits(state, count))
        tables.append(row)
        if progress:
            progress(f"阶段 {t + 1}/{len(cases)}：已评价 {len(row)} 个8760小时投运状态")
    return tuple(tables)


def _dp_tables(tables, discount_rate):
    """Bellman递推 F_t(s)=d_t c_t(s)+min_{p⊆s}F_{t-1}(p)。"""
    count = len(tables[0])
    previous = {0: 0.0}  # 规划前任何候选均未投运。
    parents = []
    for stage, table in enumerate(tables):
        now, parent = {}, {}
        factor = (1 + discount_rate) ** (-stage)
        for state in range(count):
            if not table[state].feasible:
                continue  # 缺供、备用和规划装机均为硬约束。
            best_cost, best_parent = inf, None
            subset = state
            while True:
                if subset in previous and previous[subset] < best_cost:
                    best_cost, best_parent = previous[subset], subset
                if subset == 0:
                    break
                subset = (subset - 1) & state
            if best_parent is not None:
                now[state] = best_cost + factor * table[state].total_cost_yuan
                parent[state] = best_parent
        if not now:
            raise ValueError(f"第{stage + 1}阶段没有可行投运状态")
        parents.append(parent)
        previous = now
    terminal = min(previous, key=lambda state: (previous[state], state))
    objective = previous[terminal]
    path = [terminal]
    for stage in range(len(tables) - 1, 0, -1):
        path.append(parents[stage][path[-1]])
    return tuple(reversed(path)), objective


def _gurobi_path(tables, discount_rate, count):
    """Gurobi最小费用状态路径MILP；单阶段one-hot，项目一经投运不可退出。"""
    try:
        # 冻结打包环境可能跳过site.py提供的交互help对象；求解器扩展模块导入时
        # 仍会查找该内建名称。只在缺失时补回标准pydoc帮助对象。
        import builtins
        if not hasattr(builtins, "help"):
            import pydoc
            builtins.help = pydoc.help
        import gurobipy as gp
        from gurobipy import GRB
    except ImportError as error:
        raise RuntimeError("无法载入Gurobi或其内部模块；请核查求解器安装、EXE打包和许可") from error
    model = gp.Model("gridmind_stage_path")
    model.Params.OutputFlag = 0
    feasible = [tuple(s for s, e in table.items() if e.feasible) for table in tables]
    # z[t,s]=1 表示阶段t末恰处于已投运集合s；仅为可行状态创建变量。
    z = {(t, s): model.addVar(vtype=GRB.BINARY, name=f"state_{t}_{s}")
         for t, states in enumerate(feasible) for s in states}
    for t, states in enumerate(feasible):
        model.addConstr(gp.quicksum(z[t, s] for s in states) == 1, name=f"one_state_{t}")
    for t in range(1, len(tables)):
        for bit in range(count):
            # 累计建设只能从0变1：Σ_s bit_i(s)z[t-1,s]≤Σ_s bit_i(s)z[t,s]。
            before = gp.quicksum(z[t - 1, s] for s in feasible[t - 1] if s & (1 << bit))
            after = gp.quicksum(z[t, s] for s in feasible[t] if s & (1 << bit))
            model.addConstr(before <= after, name=f"monotonic_{t}_{bit}")
    model.setObjective(gp.quicksum(
        tables[t][s].total_cost_yuan / (1 + discount_rate) ** t * z[t, s]
        for t, states in enumerate(feasible) for s in states), GRB.MINIMIZE)
    model.optimize()
    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(f"Gurobi阶段路径未取得最优解，状态码 {model.Status}")
    path = tuple(next(s for s in states if z[t, s].X > 0.5)
                 for t, states in enumerate(feasible))
    return path, model.ObjVal


def _validate_cases(cases, discount_rate, max_candidates):
    """候选身份、年份和折现率必须在阶段间一致，防止状态位含义漂移。"""
    cases = tuple(cases)
    if len(cases) < 2:
        raise ValueError("动态规划至少需要两个按年份排列的阶段")
    count = len(cases[0].candidates)
    if not 1 <= count <= max_candidates:
        raise ValueError(f"动态规划仅允许1至{max_candidates}个候选状态位；当前为{count}")
    identities = tuple((p.station_id, p.technology, p.capacity_mw)
                       for p in cases[0].candidates)
    for left, right in zip(cases, cases[1:]):
        if right.target_year != left.target_year + 1:
            raise ValueError("动态规划阶段必须按连续年份排列")
    for case in cases:
        if tuple((p.station_id, p.technology, p.capacity_mw)
                 for p in case.candidates) != identities:
            raise ValueError("各年度候选项目身份、类型、容量及位序必须一致")
    if not 0 <= discount_rate < 1:
        raise ValueError("贴现率必须在[0,1)内")
    return cases, count


def solve_stage_planning(cases, discount_rate=0.07, max_candidates=8, progress=None):
    """逐年枚举运行状态、Bellman递推，再用Gurobi独立证明同一最优费用。"""
    cases, count = _validate_cases(cases, discount_rate, max_candidates)
    tables = _state_costs(cases, count, progress)
    dp_path, objective = _dp_tables(tables, discount_rate)
    gurobi_path, gurobi_cost = _gurobi_path(tables, discount_rate, count)
    if not isclose(objective, gurobi_cost, rel_tol=1e-8, abs_tol=0.01):
        raise AssertionError("Bellman递推与Gurobi目标不一致")
    stages, previous = [], 0
    for t, (case, state) in enumerate(zip(cases, dp_path)):
        item = tables[t][state]
        # 只对最终状态复算完整8760行，核对功率平衡；避免把未知残差写成零。
        simulation = simulate_project(case, _bits(state, count), keep_hourly=True)
        residual = simulation.summary["max_balance_residual_mw"]
        if residual > 1e-6:
            raise AssertionError(f"第{t + 1}阶段最大功率平衡残差 {residual} MW")
        stages.append(StageResult(case.target_year, state, state & ~previous,
                                  item.total_cost_yuan,
                                  item.total_cost_yuan / (1 + discount_rate) ** t,
                                  residual))
        previous = state
    return PlanningResult(tuple(stages), objective, gurobi_cost, gurobi_path,
                          len(cases) * (1 << count), discount_rate, tables)


def compare_ga_on_stages(cases, tables, discount_rate=0.07, settings=None):
    """GA在同一阶段费用表上搜索建站年份；与DP共享运行模拟和硬约束。"""
    cases = tuple(cases)
    count, periods = len(cases[0].candidates), len(cases)
    settings = settings or GASettings(48, 60, 10, 12, 2, 0.85, 0.04, 19)
    # 第t组bit表示该项目在阶段t选择建设；重复置1按最早建设年解释。
    proxy = SimpleNamespace(candidates=cases[0].candidates * periods)

    def evaluate_bits(_, chromosome):
        """把逐年建设基因转为累计状态，费用与DP完全同表同贴现率。"""
        state, fixed, variable, violation = 0, 0.0, 0.0, 0.0
        shortage, reserve_shortfall, over = 0.0, 0.0, 0.0
        feasible = True
        for t in range(periods):
            state |= sum((1 << i) for i, bit in enumerate(chromosome[t * count:(t + 1) * count]) if bit)
            item = tables[t][state]
            factor = (1 + discount_rate) ** (-t)
            fixed += factor * item.annual_fixed_cost_yuan
            variable += factor * item.variable_cost_yuan
            violation += item.violation
            shortage += item.unserved_mwh
            reserve_shortfall += item.reserve_shortfall_mwh
            over += item.overgeneration_mwh
            feasible &= item.feasible
        final = tables[-1][state]
        return Evaluation(tuple(chromosome), fixed, variable, fixed + variable,
                          shortage, 0, final.firm_capacity_mw,
                          final.required_firm_capacity_mw, final.reserve_gap_mw,
                          reserve_shortfall, over, feasible, violation)

    # 对每个候选加入“仅末年建”和“首年建”两个单项目种子，
    # 其余仍随机；这与PPT的初始种群和精英保留结构一致。
    seeds = []
    for stage in reversed(range(periods)):
        for bit in range(count):
            gene = [0] * (count * periods)
            gene[stage * count + bit] = 1
            seeds.append(tuple(gene))
    result = optimize(proxy, settings, evaluator=evaluate_bits, seed_population=seeds)
    path, state = [], 0
    for t in range(periods):
        state |= sum((1 << i) for i, bit in enumerate(
            result.best.chromosome[t * count:(t + 1) * count]) if bit)
        path.append(state)
    return result, tuple(path)
