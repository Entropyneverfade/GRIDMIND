"""共享数据契约：所有模块只通过这些只读结构交换电站、曲线与参数。"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class StorageSpec:
    """储能的功率与能量分别定义；效率分开，避免往返效率重复使用。"""
    charge_power_mw: float
    energy_capacity_mwh: float
    eta_charge: float
    eta_discharge: float
    initial_energy_mwh: float = 0.0


@dataclass(frozen=True)
class Plant:
    """电站参数。MW 是功率，元/MWh 是每单位发电量的变动成本。"""
    name: str
    technology: str  # thermal / wind / solar / storage
    capacity_mw: float
    firm_capacity_mw: float  # 规划备用校验使用的可信容量；不代表随机故障模型
    variable_cost_yuan_per_mwh: float
    annual_fixed_cost_yuan: float = 0.0  # 仅新增项目计入规划目标
    min_output_mw: float = 0.0  # 火电开机后的最小技术出力
    storage: Optional[StorageSpec] = None  # 储能的capacity_mw为最大放电功率


@dataclass(frozen=True)
class Hour:
    """一个小时的输入；cf 为 0~1 的风光容量因子。"""
    load_mw: float
    wind_cf: float
    solar_cf: float


@dataclass(frozen=True)
class Problem:
    """只读问题对象；候选电站顺序必须与染色体每一位的顺序一致。"""
    existing: Tuple[Plant, ...]
    candidates: Tuple[Plant, ...]
    hours: Tuple[Hour, ...]
    reserve_margin: float
    max_unserved_mwh: float
    # 说明书5.1节调峰序位在无水电系统中的三种不同结果。
    curtailment_priority: str = "solar_first"  # solar_first / wind_first / proportional
    operating_reserve_ratio: float = 0.03  # 逐小时在线备用要求，与规划备用率分开
    storage_lookahead_hours: int = 48  # 跨日净负荷前瞻，用于规则式削峰阈值
    max_reserve_shortfall_mwh: float = 0.0  # 备用短缺功率的时间积分上限
    dispatch_mode: str = "rules"  # rules / gurobi
    terminal_storage_value_yuan_per_mwh: float = 300.0  # 滚动窗口末内部能量的近似后续价值


@dataclass(frozen=True)
class GASettings:
    population_size: int
    max_generations: int
    min_generations: int
    stall_generations: int
    elite_count: int
    crossover_rate: float
    mutation_rate: float
    seed: int


"""统一数值容差；保留原始结果，仅在可行性判定中容许浮点/求解误差。"""

POWER_TOLERANCE_MW = 1e-6
ANNUAL_ENERGY_TOLERANCE_MWH = 1e-4  # 8760个小时数值误差积分，0.1kWh量级

# 规划年固定365日：闰年输入曲线省略2月29日，故Σ月小时数=8760。
# 月预算、逐月表和窗口须共用此口径，避免2028年误按8784小时分段。
PLANNING_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
PLANNING_MONTH_HOURS = tuple(days * 24 for days in PLANNING_MONTH_DAYS)
