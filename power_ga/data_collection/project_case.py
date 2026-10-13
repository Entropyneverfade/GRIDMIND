"""项目数据库接入：保留原库，映射机组、电站、曲线和外送约束。"""

import csv
import math
from calendar import isleap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Tuple

from openpyxl import load_workbook


# 编码来自源表“电站表.类型”；机组表.类型在本库均为0，不能据此分类。
TECHNOLOGIES = {300: "coal", 320: "gas", 373: "hydro", 380: "pumped",
                385: "battery", 390: "wind", 391: "solar", 393: "biomass"}
TECH_LABELS = {"coal": "煤电", "gas": "燃气", "hydro": "常规水电", "pumped": "抽水蓄能",
               "battery": "新型储能", "wind": "风电", "solar": "光伏", "biomass": "生物质"}


@dataclass(frozen=True)
class CasePlant:
    """电站级容量，储能时长是 h；曲线是逐小时单位值。"""
    station_id: int
    name: str
    technology: str
    capacity_mw: float
    min_fraction: float
    variable_cost_yuan_per_mwh: float
    annual_cost_yuan: float
    profile: Tuple[float, ...] = ()
    storage_hours: float = 0.0
    charge_ratio: float = 1.0
    roundtrip_efficiency: float = 1.0
    hydro_monthly_factor: Tuple[float, ...] = (1.0,) * 12


@dataclass(frozen=True)
class ProjectCase:
    """2025存量对比目标年增量的单年规划问题；小时序号0..8759。"""
    base_year: int
    target_year: int
    existing: Tuple[CasePlant, ...]
    candidates: Tuple[CasePlant, ...]
    domestic_load_mw: Tuple[float, ...]
    export_mw: Tuple[float, ...]
    reserve_margin: float
    annual_energy_forecast_gwh: float
    warnings: Tuple[str, ...]
    source_folder: str
    cost_file: str

    @property
    def hours(self):
        """向通用遗传编码器提供候选数量；运行引擎使用原生逐时数组。"""
        return self.domestic_load_mw


def _records(book, sheet):
    """返回非空数据行；该库有重复表头，字段均按已审计列序读取。"""
    return [r for r in list(book[sheet].values)[1:] if r[0] is not None]


def _read_curve(year_folder: Path, name: str, cache: dict):
    """365日×24h展平，禁用插值；闰年校核2月29日是否已省略。"""
    if name in cache:
        return cache[name]
    path = year_folder / "CURVE" / (name + ".xlsx")
    if not path.exists():
        raise FileNotFoundError(f"缺少逐时曲线：{path}")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(book.worksheets[0].values)[1:]
    finally:
        book.close()  # 即使数据无效，也及时释放只读工作簿句柄。
    if year_folder.name.isdecimal() and isleap(int(year_folder.name)):
        year = int(year_folder.name)
        expected = date(year, 1, 1)
        for day, row in enumerate(rows, 1):
            if expected.month == 2 and expected.day == 29:
                expected += timedelta(days=1)  # 8760小时规划年没有闰日。
            label = row[0]
            try:
                if isinstance(label, datetime):
                    actual = label.date()
                elif isinstance(label, date):
                    actual = label
                else:
                    actual = date.fromisoformat(str(label).replace("/", "-"))
            except ValueError as error:
                raise ValueError(f"闰年曲线第{day}日日期标签无效：{path}") from error
            if actual != expected:
                raise ValueError(f"闰年曲线第{day}日应为{expected}，实际为{actual}：{path}")
            expected += timedelta(days=1)
    points = tuple(float(v) for row in rows for v in row[1:25])
    # 负荷、风光、联络线均按“额定MW×逐时单位值”解释；超出1会突破额定功率。
    if len(points) != 8760 or any(not math.isfinite(v) or not 0 <= v <= 1 + 1e-9
                                   for v in points):
        raise ValueError(f"曲线应为8760个0–1范围内的有限单位值：{path}")
    cache[name] = points
    return points


def read_costs(path: Path):
    """核对8类技术费用且拒绝重复行；资本费已年化，不在运行费中重计。"""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"technology", "annual_capital_yuan_per_mw", "variable_yuan_per_mwh"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"成本参数缺少必要列：{sorted(required - set(reader.fieldnames or []))}")
        data = {}
        for line, row in enumerate(reader, 2):
            key = (row["technology"] or "").strip()
            if key not in TECH_LABELS:
                raise ValueError(f"成本参数第{line}行技术类型未知：{key}")
            if key in data:
                raise ValueError(f"成本参数存在重复技术：{key}，第{line}行")
            data[key] = row
    missing = set(TECH_LABELS) - set(data)
    if missing:
        raise ValueError(f"成本参数缺少技术：{sorted(missing)}")
    for key, row in data.items():
        for field in ("annual_capital_yuan_per_mw", "variable_yuan_per_mwh"):
            value = float(row[field])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"成本参数越界：{key}.{field}")
    return data


def _station_units(book):
    """按电站ID连接电站表与机组表，装机=单机容量×有效台数。"""
    stations = {int(r[0]): r for r in _records(book, "电站表")}
    result = {}
    for unit in _records(book, "机组表"):
        station_id = int(unit[3])
        if station_id not in stations or int(unit[2] or 0) != 1:
            continue
        station = stations[station_id]
        if int(station[2] or 0) != 1:
            continue
        kind = int(station[4])
        if kind not in TECHNOLOGIES:
            raise ValueError(f"未映射电站类型 {kind}，电站ID={station_id}")
        mw = float(unit[4] or 0) * float(unit[5] or 0)
        if mw <= 0:
            continue
        if station_id in result:
            raise ValueError(f"电站ID={station_id}存在多个有效机组记录，需补充聚合规则")
        result[station_id] = (station, unit, mw)
    return result


def _hydro_factors(book):
    """水文表中多个情景先取有效、情景编号0；M1..M12是月相对系数。"""
    factors = {}
    for row in _records(book, "水文表"):
        station_id = int(row[3] or 0)
        if int(row[2] or 0) == 1 and int(row[6] or 0) == 0 and station_id not in factors:
            factors[station_id] = tuple(float(x or 0) for x in row[7:19])
    return factors


def _make_plant(station_id, record, mw, year_folder, curves, costs, hydro_factors, candidate):
    """只在储能类型读取效率/时长；风光的“储能比率”是另一物理含义。"""
    station, unit, _ = record
    kind = TECHNOLOGIES[int(station[4])]
    curve_name = station[15]
    profile = _read_curve(year_folder, str(curve_name), curves) if kind in {"wind", "solar"} else ()
    if kind in {"wind", "solar"} and not curve_name:
        raise ValueError(f"风光电站缺少逐时出力曲线：{station[1]}")
    storage_hours = float(unit[8] or 0) if kind in {"pumped", "battery"} else 0.0
    if kind in {"pumped", "battery"} and storage_hours <= 0:
        raise ValueError(f"储能时长必须大于零：{station[1]}")
    efficiency = float(station[8] or 0) if storage_hours else 1.0
    if not 0 < efficiency <= 1:
        raise ValueError(f"储能往返效率越界：{station[1]}")
    charge_ratio = float(station[7]) if storage_hours and station[7] is not None else 1.0
    if not math.isfinite(charge_ratio) or charge_ratio <= 0:
        raise ValueError(f"储能充电功率倍率必须大于零：{station[1]}")
    min_fraction = float(unit[7] or 0) if kind in {"coal", "gas", "biomass"} else 0.0
    if not math.isfinite(min_fraction) or not 0 <= min_fraction <= 1:
        raise ValueError(f"常规机组最小出力比例越界：{station[1]}")
    row = costs[kind]
    return CasePlant(station_id, str(station[1]), kind, mw,
                     min_fraction,
                     float(row["variable_yuan_per_mwh"]),
                     mw * float(row["annual_capital_yuan_per_mw"]) if candidate else 0.0,
                     profile, storage_hours,
                     charge_ratio,
                     efficiency, hydro_factors.get(station_id, (1.0,) * 12))


def load_project_case(source_folder: Path, target_year: int, cost_path: Path) -> ProjectCase:
    """读取五年项目库，基年有效容量为存量，目标年差额构成GA候选。"""
    source_folder, cost_path = source_folder.resolve(), cost_path.resolve()
    base_year = 2025
    if target_year not in range(2025, 2030):
        raise ValueError("当前项目数据库仅覆盖2025–2029")
    costs = read_costs(cost_path)
    base_path = source_folder / str(base_year) / f"{base_year}.xlsx"
    target_folder = source_folder / str(target_year)
    target_path = target_folder / f"{target_year}.xlsx"
    base_book = load_workbook(base_path, read_only=True, data_only=True)
    target_book = load_workbook(target_path, read_only=True, data_only=True)
    base = _station_units(base_book)
    target = _station_units(target_book)
    hydro = _hydro_factors(target_book)
    curves, existing, candidates, warnings = {}, [], [], []
    for station_id, record in sorted(target.items()):
        base_mw = base.get(station_id, (None, None, 0))[2]
        target_mw = record[2]
        if base_mw > target_mw + 1e-6:
            warnings.append(f"电站{station_id}目标年容量低于基年；存量按目标年容量截取")
        keep = min(base_mw, target_mw)
        if keep > 0:
            existing.append(_make_plant(station_id, record, keep, target_folder, curves, costs, hydro, False))
        increment = max(0.0, target_mw - keep)
        if increment > 0:
            candidates.append(_make_plant(station_id, record, increment, target_folder, curves, costs, hydro, True))
    # 按有效电站所属系统ID选择当前单区域；外部系统也可能自带负荷曲线。
    # 单区域引擎不会把其他系统的曲线误并入本地区负荷，更不推断网架潮流。
    system_ids = {int(record[0][2]) for record in target.values()}
    if len(system_ids) != 1:
        raise ValueError("当前单区域模型要求有效电站属于同一个系统ID")
    system_id = system_ids.pop()
    system = next(r for r in _records(target_book, "系统表")
                  if int(r[0]) == system_id and r[14])
    # 一个系统可列多条水平年记录，优先取最接近目标年的非零负荷。
    matching_loads = [r for r in _records(target_book, "负荷表")
                      if int(r[2]) == system_id and float(r[3] or 0) > 0]
    load_row = min(matching_loads,
                   key=lambda r: (abs(int(r[1]) - target_year), int(r[1]) > target_year))
    peak = float(load_row[3])
    annual_forecast = float(load_row[4])
    load_curve = _read_curve(target_folder, str(system[14]), curves)
    domestic = tuple(peak * value for value in load_curve)
    if int(load_row[1]) != target_year:
        warnings.append(f"目标文件为{target_year}，负荷表水平年标签为{load_row[1]}；使用文件年份曲线与该行预测值")
    calculated_gwh = sum(domestic) / 1000
    if abs(calculated_gwh - annual_forecast) / max(annual_forecast, 1) > 0.01:
        warnings.append(f"峰值×负荷曲线得到{calculated_gwh:.1f}GWh，与表内预测{annual_forecast:.1f}GWh不一致；保留峰值及曲线原值")
    lines = {int(r[0]): r for r in _records(target_book, "线路表")}
    export = [0.0] * 8760
    for tie in _records(target_book, "联络表"):
        if int(tie[2] or 0) != 1 or int(tie[5]) != 1 or int(tie[6]) != 0 or not tie[15]:
            continue
        line = lines.get(int(tie[4]))
        if line is None:
            raise ValueError(f"联络线缺少线路ID={tie[4]}")
        # 线路表第9列为额定输送MW，逐时外送=额定MW×联络表曲线单位值。
        rated_mw = float(line[8] or 0)
        profile = _read_curve(target_folder, str(tie[15]), curves)
        export = [a + rated_mw * b for a, b in zip(export, profile)]
    if not candidates:
        warnings.append("目标年相对2025没有新增容量；只执行基线运行模拟")
    base_book.close()
    target_book.close()
    return ProjectCase(base_year, target_year, tuple(existing), tuple(candidates),
                       domestic, tuple(export), float(load_row[5] or 0), annual_forecast,
                       tuple(warnings), str(source_folder), str(cost_path))
