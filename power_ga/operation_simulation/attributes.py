"""电力部门分区投入产出式属性追踪：碳、SO₂与物理新能源份额。"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class PowerAttribute:
    """发电/储能放电的直接属性：tCO₂/MWh、kgSO₂/MWh、可再生份额。"""

    carbon_t_per_mwh: float
    sulfur_kg_per_mwh: float
    renewable_fraction: float


@dataclass(frozen=True)
class ZoneAttribute:
    """消费端归属，1h步长下MW×属性强度即t或kg。"""

    carbon_t_per_mwh: float
    sulfur_kg_per_mwh: float
    renewable_fraction: float
    served_load_mwh: float
    consumed_carbon_t: float
    consumed_sulfur_kg: float
    consumed_renewable_mwh: float


@dataclass(frozen=True)
class AttributeResult:
    """全系统源端与用端守恒残差；不含上游生命周期与大气扩散。"""

    zones: dict
    carbon_balance_t: float
    sulfur_balance_kg: float
    renewable_balance_mwh: float


def _linear_solve(matrix, rhs):
    """带主元的高斯消元，求(M·x=b)；孤立零功率区的强度定义为0。"""
    count = len(rhs)
    a = [list(row) + [float(value)] for row, value in zip(matrix, rhs)]
    for col in range(count):
        pivot = max(range(col, count), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) <= 1e-10:
            raise ValueError("属性追踪矩阵奇异：检查无终端负荷的闭环流")
        a[col], a[pivot] = a[pivot], a[col]
        scale = a[col][col]
        a[col] = [value / scale for value in a[col]]
        for row in range(count):
            if row != col:
                factor = a[row][col]
                a[row] = [value - factor * base for value, base in zip(a[row], a[col])]
    return tuple(row[-1] for row in a)


def trace_power_attributes(zones, generators, links, dispatch, generator_attributes,
                           storage_discharge_attributes=None):
    """由已求得的跨区流量做三种属性的多区域投入产出式比例分摊。

    对区i、属性k：Pout_i·q_i^k−Σ_j F_{j→i}q_j^k=本地直接属性_i^k。
    Pout_i=本地发电+储能放电+进口=已服务负荷+充电+溢出+出口。
    这是一小时物理电力混合的消费归属，不能作为绿证所有权或完整经济MRIO。
    """
    zones = tuple(zones)
    generators = tuple(generators)
    links = tuple(links)
    storage_discharge_attributes = storage_discharge_attributes or {}
    index = {zone.name: position for position, zone in enumerate(zones)}
    if not zones or len(index) != len(zones):
        raise ValueError("区域名称必须唯一且非空")
    if set(dispatch.zones) != set(index):
        raise ValueError("运行结果的分区与属性输入不一致")
    def check_factor(value, label):
        if (not isinstance(value, PowerAttribute) or
                any(not isfinite(number) for number in
                    (value.carbon_t_per_mwh, value.sulfur_kg_per_mwh,
                     value.renewable_fraction)) or
                min(value.carbon_t_per_mwh, value.sulfur_kg_per_mwh,
                    value.renewable_fraction) < 0 or value.renewable_fraction > 1):
            raise ValueError(f"属性因子越界：{label}")

    n = len(zones)
    matrix = [[0.0] * n for _ in zones]
    local_carbon = [0.0] * n
    local_sulfur = [0.0] * n
    local_renewable = [0.0] * n
    served = [0.0] * n
    other_sink = [0.0] * n
    for unit in generators:
        amount = dispatch.generation_mw.get(unit.name, 0.0)
        if amount <= 1e-10:
            continue
        if unit.name not in generator_attributes:
            raise ValueError(f"缺少已发电机组的属性因子：{unit.name}")
        factor = generator_attributes[unit.name]
        check_factor(factor, unit.name)
        pos = index[unit.zone]
        local_carbon[pos] += amount * factor.carbon_t_per_mwh
        local_sulfur[pos] += amount * factor.sulfur_kg_per_mwh
        local_renewable[pos] += amount * factor.renewable_fraction
    for pos, zone in enumerate(zones):
        row = dispatch.zones[zone.name]
        local_renewable[pos] += row["wind_mw"] + row["solar_mw"]
        if zone.fixed_discharge_mw > 1e-10:
            if zone.name not in storage_discharge_attributes:
                raise ValueError(f"储能放电必须提供上游充电属性：{zone.name}")
            factor = storage_discharge_attributes[zone.name]
            check_factor(factor, zone.name)
            local_carbon[pos] += zone.fixed_discharge_mw * factor.carbon_t_per_mwh
            local_sulfur[pos] += zone.fixed_discharge_mw * factor.sulfur_kg_per_mwh
            local_renewable[pos] += zone.fixed_discharge_mw * factor.renewable_fraction
        served[pos] = zone.demand_mw - row["unserved_mw"]
        other_sink[pos] = zone.fixed_charge_mw + row["spill_mw"]
        if served[pos] < -1e-7:
            raise ValueError("缺供量超过分区负荷")
        throughput = (sum(dispatch.generation_mw.get(unit.name, 0.0)
                          for unit in generators if unit.zone == zone.name) +
                      row["wind_mw"] + row["solar_mw"] + zone.fixed_discharge_mw)
        matrix[pos][pos] += throughput
    for link in links:
        value = dispatch.flows_mw[link.name]
        if abs(value) > link.limit_mw + 1e-7:
            raise ValueError("联络线流量超过额定限额")
        source, target = (link.source, link.target) if value >= 0 else (link.target, link.source)
        amount = abs(value)
        matrix[index[target]][index[target]] += amount
        matrix[index[target]][index[source]] -= amount
    for pos, zone in enumerate(zones):
        # 既无发电也无进口时强度取0，不让零吞吐节点导致矩阵奇异。
        if abs(matrix[pos][pos]) <= 1e-10:
            matrix[pos][pos] = 1.0
    carbon = _linear_solve(matrix, local_carbon)
    sulfur = _linear_solve(matrix, local_sulfur)
    renewable = _linear_solve(matrix, local_renewable)
    outputs = {}
    for pos, zone in enumerate(zones):
        outputs[zone.name] = ZoneAttribute(carbon[pos], sulfur[pos], renewable[pos],
                                           served[pos], carbon[pos] * served[pos],
                                           sulfur[pos] * served[pos],
                                           renewable[pos] * served[pos])
    # 用端含终端负荷、储能充电与弃置；省际输送在全系统求和时抵消。
    carbon_gap = sum(local_carbon) - sum(carbon[i] * (served[i] + other_sink[i])
                                         for i in range(n))
    sulfur_gap = sum(local_sulfur) - sum(sulfur[i] * (served[i] + other_sink[i])
                                         for i in range(n))
    renewable_gap = sum(local_renewable) - sum(renewable[i] * (served[i] + other_sink[i])
                                             for i in range(n))
    return AttributeResult(outputs, carbon_gap, sulfur_gap, renewable_gap)
