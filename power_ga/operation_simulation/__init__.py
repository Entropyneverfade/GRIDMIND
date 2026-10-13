"""模块3统一入口：按配置选用规则引擎或滚动Gurobi引擎。"""


def simulate(problem, chromosome, keep_hourly=False):
    """相同输入输出契约，使GA只需调用一个运行接口。"""
    if problem.dispatch_mode == "rules":
        from .engine import simulate as run
    elif problem.dispatch_mode == "gurobi":
        from .gurobi_engine import simulate as run
    else:
        raise ValueError(f"未实现的运行模式: {problem.dispatch_mode}")
    return run(problem, chromosome, keep_hourly)
