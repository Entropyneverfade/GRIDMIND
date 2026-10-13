"""按规划年份递推候选电站投运状态，并用Gurobi核验最优路径。"""

from .solver import solve_stage_planning, compare_ga_on_stages

__all__ = ["solve_stage_planning", "compare_ga_on_stages"]
